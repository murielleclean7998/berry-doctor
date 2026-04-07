from __future__ import annotations

import io
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import numpy as np
except Exception:  # pragma: no cover - dependency may be missing during authoring
    np = None

try:
    import onnxruntime as ort
except Exception:  # pragma: no cover - dependency may be missing during authoring
    ort = None

from PIL import Image

from engine.paths import data_path, model_path


@dataclass(slots=True)
class DiagnosisResult:
    label: str
    label_ko: str
    confidence: float
    symptoms: str
    pesticide: dict[str, Any] | None
    tip: str
    model_used: str


class DiseaseDetector:
    def __init__(self) -> None:
        self.model_path = Path(model_path("berry-disease-v1.onnx"))
        self.class_map = json.loads(Path(model_path("class_labels_ko.json")).read_text(encoding="utf-8"))
        self.pesticide_db = json.loads(Path(data_path("pesticide_db.json")).read_text(encoding="utf-8"))
        self.tips = json.loads(Path(data_path("farmer_tips.json")).read_text(encoding="utf-8"))["tips"]
        self.session = self._load_session()
        self.community_source = None

    def _load_session(self):
        if ort is None or np is None or not self.model_path.exists() or self.model_path.stat().st_size < 1024:
            return None
        try:
            return ort.InferenceSession(str(self.model_path), providers=["CPUExecutionProvider"])
        except Exception:
            return None

    def _find_pesticide(self, disease_key: str) -> dict[str, Any] | None:
        for entry in self.pesticide_db["entries"]:
            if entry["disease"] == disease_key and entry["pesticides"]:
                return entry["pesticides"][0]
        return None

    def _find_tip(self, disease_key: str) -> str:
        for entry in self.tips:
            if entry.get("disease") == disease_key:
                return entry["tip"]
        return "증상이 번지기 전에 의심 부위를 빨리 떼어내고 환기 시간을 먼저 확보해 주세요."

    def _symptoms(self, disease_key: str) -> str:
        symptoms = {
            "gray_mold": "꽃이나 과실에 회색 곰팡이성 병반이 보일 수 있어요.",
            "powdery_mildew_leaf": "잎 표면에 하얀 가루처럼 보이는 병반이 생길 수 있어요.",
            "powdery_mildew_fruit": "과실 표면에 흰가루처럼 덮이는 증상이 나타날 수 있어요.",
            "anthracnose": "검거나 움푹 꺼지는 병반이 생기고 번지는 속도가 빠를 수 있어요.",
            "angular_leaf_spot": "잎맥 사이로 각진 수침상 병반이 보일 수 있어요.",
            "blossom_blight": "꽃이 갈변하거나 마르며 떨어질 수 있어요.",
            "leaf_spot": "작은 반점이 퍼지며 잎이 마르는 양상이 나타날 수 있어요.",
            "healthy": "뚜렷한 병징은 상대적으로 적어 보여요."
        }
        return symptoms.get(disease_key, "사진만으로 단정하기 어려운 증상이 섞여 있어요.")

    def _infer_from_filename(self, filename: str) -> tuple[str, float]:
        lowered = filename.lower()
        mapping = {
            "gray": "gray_mold",
            "mold": "gray_mold",
            "anthrac": "anthracnose",
            "powder": "powdery_mildew_leaf",
            "leafspot": "leaf_spot",
            "spot": "leaf_spot",
            "healthy": "healthy",
        }
        for key, value in mapping.items():
            if key in lowered:
                return value, 66.0
        return "healthy", 58.0

    def _heuristic(self, image: Image.Image, filename: str) -> tuple[str, float]:
        label, confidence = self._infer_from_filename(filename)
        if np is None:
            return label, confidence
        pixels = np.asarray(image.resize((128, 128)).convert("RGB"), dtype=np.float32)
        brightness = float(pixels.mean())
        red_bias = float(pixels[..., 0].mean() - pixels[..., 1].mean())
        if brightness < 95:
            return "gray_mold", 63.0
        if red_bias < -8:
            return "powdery_mildew_leaf", 60.0
        if brightness > 165 and red_bias > 10:
            return "healthy", 62.0
        return label, confidence

    def _preprocess(self, image: Image.Image) -> Any:
        array = np.asarray(image.resize((640, 640)).convert("RGB"), dtype=np.float32) / 255.0
        array = np.transpose(array, (2, 0, 1))[None, ...]
        return array

    def _parse_detection_output(self, output: Any) -> tuple[str, float]:
        scores = np.asarray(output)
        if scores.ndim == 3:
            scores = scores[0]
        if scores.ndim == 2 and scores.shape[0] in (84, 85) and scores.shape[1] > scores.shape[0]:
            scores = scores.T

        label_keys = list(self.class_map.keys())

        if scores.ndim == 1:
            index = int(scores.argmax())
            confidence = float(scores[index] * 100)
            return label_keys[index] if index < len(label_keys) else "healthy", confidence

        if scores.ndim != 2:
            raise RuntimeError("Unsupported ONNX output shape")

        best_label = "healthy"
        best_conf = 0.0
        for row in scores:
            if row.shape[0] < 4 + len(label_keys):
                continue
            if row.shape[0] == 5 + len(label_keys):
                objectness = float(row[4])
                class_scores = row[5:5 + len(label_keys)]
            else:
                objectness = 1.0
                class_scores = row[4:4 + len(label_keys)]
            class_idx = int(np.asarray(class_scores).argmax())
            confidence = float(class_scores[class_idx] * objectness * 100)
            if confidence > best_conf:
                best_conf = confidence
                best_label = label_keys[class_idx] if class_idx < len(label_keys) else "healthy"

        if best_conf <= 0:
            raise RuntimeError("No confident detection found")
        return best_label, best_conf

    def _onnx_predict(self, image: Image.Image) -> tuple[str, float]:
        if self.session is None or np is None:
            raise RuntimeError("Model unavailable")
        input_name = self.session.get_inputs()[0].name
        outputs = self.session.run(None, {input_name: self._preprocess(image)})
        return self._parse_detection_output(outputs[0])

    def analyze_bytes(self, image_bytes: bytes, filename: str = "upload.jpg", context: dict[str, Any] | None = None) -> DiagnosisResult:
        image = Image.open(io.BytesIO(image_bytes))
        model_used = "heuristic"
        try:
            label, confidence = self._onnx_predict(image)
            model_used = "onnx"
        except Exception:
            label, confidence = self._heuristic(image, filename)
        pesticide = self._find_pesticide(label)
        result = DiagnosisResult(
            label=label,
            label_ko=self.class_map.get(label, label),
            confidence=round(confidence, 1),
            symptoms=self._symptoms(label),
            pesticide=pesticide,
            tip=self._find_tip(label),
            model_used=model_used,
        )
        if self.community_source is not None and result.confidence >= 70:
            try:
                self.community_source.on_local_detection(result, context or {})
            except Exception:
                pass
        return result
