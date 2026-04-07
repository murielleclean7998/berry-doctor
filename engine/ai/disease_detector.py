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

from engine.crop_profile import resolve_data_path
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
    def __init__(self, crop_profile: Any | None = None) -> None:
        self.crop_profile = crop_profile
        self.model_path = self._resolve_model_path()
        self.class_map = self._load_class_map()
        self.pesticide_db = self._load_pesticide_db()
        self.tips = self._load_tips()
        self.session = self._load_session()
        self.community_source = None

    def _resolve_model_path(self) -> Path:
        model_file = getattr(self.crop_profile, "model_file", "berry-disease-v1.onnx")
        path = Path(model_path(model_file))
        if path.exists():
            return path
        if self.crop_profile is None or getattr(self.crop_profile, "crop_type", "strawberry") == "strawberry":
            return Path(model_path("berry-disease-v1.onnx"))
        return path

    def _resolve_data_file(self, key: str, fallback: str) -> Path:
        if self.crop_profile is not None:
            candidate = resolve_data_path(self.crop_profile, key)
            if candidate.exists():
                return candidate
        return Path(data_path(fallback))

    def _load_class_map(self) -> dict[str, str]:
        class_labels_file = getattr(self.crop_profile, "class_labels_file", "class_labels_ko.json")
        candidate = Path(model_path(class_labels_file))
        if candidate.exists():
            return json.loads(candidate.read_text(encoding="utf-8"))
        if self.crop_profile is not None:
            names = dict(getattr(self.crop_profile, "disease_names_ko", {}))
            symptoms = dict(getattr(self.crop_profile, "disease_symptoms_ko", {}))
            payload = {key: names.get(key, key) for key in symptoms}
            payload.setdefault("healthy", "정상")
            return payload
        fallback = Path(model_path("class_labels_ko.json"))
        if fallback.exists():
            return json.loads(fallback.read_text(encoding="utf-8"))
        return {"healthy": "정상"}

    def _load_pesticide_db(self) -> dict[str, Any]:
        path = self._resolve_data_file("pesticide_db", "pesticide_db.json")
        return json.loads(path.read_text(encoding="utf-8"))

    def _load_tips(self) -> list[dict[str, Any]]:
        path = self._resolve_data_file("farmer_tips", "farmer_tips.json")
        return json.loads(path.read_text(encoding="utf-8")).get("tips", [])

    def _load_session(self):
        if ort is None or np is None or not self.model_path.exists() or self.model_path.stat().st_size < 1024:
            return None
        try:
            return ort.InferenceSession(str(self.model_path), providers=["CPUExecutionProvider"])
        except Exception:
            return None

    def _find_pesticide(self, disease_key: str) -> dict[str, Any] | None:
        for entry in self.pesticide_db.get("entries", []):
            if entry.get("disease") == disease_key and entry.get("pesticides"):
                return entry["pesticides"][0]
        return None

    def _find_tip(self, disease_key: str) -> str:
        for entry in self.tips:
            if entry.get("disease") == disease_key:
                return str(entry.get("tip", ""))
        return "증상이 번지기 전에 주변 잎과 과실을 먼저 살피고, 최근 환경 변화도 같이 확인해 주세요."

    def _symptoms(self, disease_key: str) -> str:
        if self.crop_profile is not None:
            mapped = getattr(self.crop_profile, "disease_symptoms_ko", {}).get(disease_key)
            if mapped:
                return mapped
        symptoms = {
            "gray_mold": "꽃이나 과실에 회색 곰팡이성 병반이 보일 수 있어요.",
            "powdery_mildew_leaf": "잎 표면에 하얀 가루처럼 보이는 병반이 생길 수 있어요.",
            "powdery_mildew_fruit": "과실 표면에 하얀 가루가 앉은 듯한 증상이 나타날 수 있어요.",
            "anthracnose": "검거나 타는 듯한 병반이 생기고 퍼지는 속도가 빠를 수 있어요.",
            "angular_leaf_spot": "잎맥 사이로 각진 수침성 병반이 보일 수 있어요.",
            "blossom_blight": "꽃이 갈변하거나 마르며 떨어질 수 있어요.",
            "leaf_spot": "작은 반점이 늘면서 잎이 마르는 증상이 나타날 수 있어요.",
            "healthy": "뚜렷한 병징은 적어 보여요.",
        }
        return symptoms.get(disease_key, "사진만으로 단정하기 어려운 증상일 수 있어요.")

    def _infer_from_filename(self, filename: str) -> tuple[str, float]:
        lowered = filename.lower()
        mapping = {
            "gray": "gray_mold",
            "mold": "gray_mold",
            "anthrac": "anthracnose",
            "powder": "powdery_mildew_leaf",
            "leafspot": "leaf_spot",
            "spot": "leaf_spot",
            "blight": "late_blight",
            "wilt": "bacterial_wilt",
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
