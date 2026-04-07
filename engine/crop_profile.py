from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from engine.paths import data_path


DEFAULT_CROP_TYPE = "strawberry"


@dataclass(slots=True)
class CropProfile:
    crop_type: str
    crop_name_ko: str
    crop_name_en: str
    varieties: list[str]
    default_variety: str
    model_file: str
    class_labels_file: str
    baseline_price_per_kg: int
    market_item_name: str
    signal_keywords: list[str]
    ndvi_thresholds: dict[str, float]
    diseases: dict[str, dict[str, Any]]
    disease_names_ko: dict[str, str]
    disease_symptoms_ko: dict[str, str]
    data_paths: dict[str, str]


def _profiles_dir() -> Path:
    return Path(data_path("crops"))


def _profile_path(crop_type: str) -> Path:
    return _profiles_dir() / f"{crop_type}.json"


def load_crop_profile(crop_type: str = DEFAULT_CROP_TYPE) -> CropProfile:
    profile_path = _profile_path(crop_type)
    if not profile_path.exists():
        profile_path = _profile_path(DEFAULT_CROP_TYPE)
    payload = json.loads(profile_path.read_text(encoding="utf-8"))
    return CropProfile(
        crop_type=str(payload["crop_type"]),
        crop_name_ko=str(payload["crop_name_ko"]),
        crop_name_en=str(payload["crop_name_en"]),
        varieties=[str(item) for item in payload.get("varieties", [])],
        default_variety=str(payload.get("default_variety") or ""),
        model_file=str(payload.get("model_file") or ""),
        class_labels_file=str(payload.get("class_labels_file") or ""),
        baseline_price_per_kg=int(payload.get("baseline_price_per_kg", 0) or 0),
        market_item_name=str(payload.get("market_item_name") or ""),
        signal_keywords=[str(item) for item in payload.get("signal_keywords", [])],
        ndvi_thresholds={str(key): float(value) for key, value in (payload.get("ndvi_thresholds") or {}).items()},
        diseases={str(key): dict(value) for key, value in (payload.get("diseases") or {}).items()},
        disease_names_ko={str(key): str(value) for key, value in (payload.get("disease_names_ko") or {}).items()},
        disease_symptoms_ko={str(key): str(value) for key, value in (payload.get("disease_symptoms_ko") or {}).items()},
        data_paths={str(key): str(value) for key, value in (payload.get("data_paths") or {}).items()},
    )


def resolve_data_path(profile: CropProfile, key: str) -> Path:
    relative = profile.data_paths.get(key, f"{key}.json")
    return Path(data_path(relative))


def crop_options() -> list[tuple[str, str]]:
    options: list[tuple[str, str]] = []
    for path in sorted(_profiles_dir().glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if "crop_type" not in payload or "crop_name_ko" not in payload:
            continue
        profile = load_crop_profile(path.stem)
        options.append((profile.crop_type, profile.crop_name_ko))
    return options or [(DEFAULT_CROP_TYPE, "딸기")]
