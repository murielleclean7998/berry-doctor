from __future__ import annotations

from pathlib import Path

from setuptools import find_packages, setup


ROOT = Path(__file__).parent


def pyinstaller_args() -> list[str]:
    return [
        "--onefile",
        "--windowed",
        "--name",
        "딸기박사",
        "--add-data",
        "models;models",
        "--add-data",
        "data;data",
        "--add-data",
        "i18n;i18n",
        "--add-binary",
        "bin\\mosquitto\\mosquitto.exe;bin\\mosquitto",
    ]


setup(
    name="berry-doctor",
    version="0.1.0",
    description="Phase 0 MVP for BerryDoctor smart strawberry farm assistant",
    long_description=(ROOT / "README.md").read_text(encoding="utf-8"),
    long_description_content_type="text/markdown",
    packages=find_packages(exclude=("tests", "firmware", "docs")),
    include_package_data=True,
    python_requires=">=3.11",
)
