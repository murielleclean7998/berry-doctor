from __future__ import annotations

from typing import Any

try:
    import numpy as np
except Exception:  # pragma: no cover
    np = None


def _mean(values: Any) -> float:
    if np is not None:
        return float(np.asarray(values, dtype=float).mean())
    flat = [float(item) for row in values for item in (row if isinstance(row, (list, tuple)) else [row])]
    return sum(flat) / len(flat) if flat else 0.0


def calc_ndvi(red, nir):
    if np is not None:
        red_arr = np.asarray(red, dtype=float)
        nir_arr = np.asarray(nir, dtype=float)
        return (nir_arr - red_arr) / (nir_arr + red_arr + 1e-10)
    return [[(float(n) - float(r)) / (float(n) + float(r) + 1e-10) for r, n in zip(red_row, nir_row)] for red_row, nir_row in zip(red, nir)]


def calc_ndwi(nir, swir):
    if np is not None:
        nir_arr = np.asarray(nir, dtype=float)
        swir_arr = np.asarray(swir, dtype=float)
        return (nir_arr - swir_arr) / (nir_arr + swir_arr + 1e-10)
    return [[(float(n) - float(s)) / (float(n) + float(s) + 1e-10) for n, s in zip(nir_row, swir_row)] for nir_row, swir_row in zip(nir, swir)]


def calc_gndvi(green, nir):
    if np is not None:
        green_arr = np.asarray(green, dtype=float)
        nir_arr = np.asarray(nir, dtype=float)
        return (nir_arr - green_arr) / (nir_arr + green_arr + 1e-10)
    return [[(float(n) - float(g)) / (float(n) + float(g) + 1e-10) for g, n in zip(green_row, nir_row)] for green_row, nir_row in zip(green, nir)]


def mean_value(values: Any) -> float:
    return _mean(values)


def min_value(values: Any) -> float:
    if np is not None:
        return float(np.asarray(values, dtype=float).min())
    flat = [float(item) for row in values for item in (row if isinstance(row, (list, tuple)) else [row])]
    return min(flat) if flat else 0.0


def max_value(values: Any) -> float:
    if np is not None:
        return float(np.asarray(values, dtype=float).max())
    flat = [float(item) for row in values for item in (row if isinstance(row, (list, tuple)) else [row])]
    return max(flat) if flat else 0.0


def index_to_grade(
    value: float,
    crop: str = "strawberry",  # noqa: ARG001
    thresholds: dict[str, float] | None = None,
) -> dict[str, str | None]:
    value = round(float(value), 3)
    thresholds = thresholds or {"good": 0.7, "normal": 0.5, "caution": 0.3}
    if value >= float(thresholds.get("good", 0.7)):
        return {"grade": "좋음", "emoji": "🟢", "action": None}
    if value >= float(thresholds.get("normal", 0.5)):
        return {"grade": "보통", "emoji": "🟡", "action": None}
    if value >= float(thresholds.get("caution", 0.3)):
        return {"grade": "주의", "emoji": "🟠", "action": "확인 필요"}
    return {"grade": "위험", "emoji": "🔴", "action": "즉시 점검"}
