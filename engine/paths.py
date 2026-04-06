from __future__ import annotations

import sys
from pathlib import Path


def app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent.parent


def data_path(*parts: str) -> Path:
    return app_root().joinpath("data", *parts)


def model_path(*parts: str) -> Path:
    return app_root().joinpath("models", *parts)


def i18n_path(*parts: str) -> Path:
    return app_root().joinpath("i18n", *parts)


def bin_path(*parts: str) -> Path:
    return app_root().joinpath("bin", *parts)


def writable_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent
