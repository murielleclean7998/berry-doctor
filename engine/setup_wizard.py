from __future__ import annotations

import json
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import ttk

from engine.crop_profile import DEFAULT_CROP_TYPE, crop_options, load_crop_profile
from engine.i18n import Translator


@dataclass(slots=True)
class SetupResult:
    farm_location: str
    house_count: int
    variety: str
    cultivation_type: str
    wifi_ssid: str
    wifi_password: str
    crop_type: str = DEFAULT_CROP_TYPE

    def as_config_entries(self) -> dict[str, str]:
        return {
            "farm_location": self.farm_location,
            "house_count": str(self.house_count),
            "variety": self.variety,
            "crop_type": self.crop_type,
            "cultivation_type": self.cultivation_type,
            "wifi_ssid": self.wifi_ssid,
            "wifi_password": self.wifi_password,
        }


def load_profiles(path: Path) -> dict[str, dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def run_setup_wizard(profiles: dict[str, dict], translator: Translator) -> SetupResult:
    if not profiles:
        raise ValueError("regional_profiles.json is empty")

    default_crop = load_crop_profile(DEFAULT_CROP_TYPE)
    first_location = next(iter(profiles))
    available_crops = crop_options()
    crop_type_by_label = {label: crop_type for crop_type, label in available_crops}
    label_by_crop_type = {crop_type: label for crop_type, label in available_crops}
    default_crop_label = label_by_crop_type.get(DEFAULT_CROP_TYPE, default_crop.crop_name_ko)

    try:
        root = tk.Tk()
    except tk.TclError:
        return SetupResult(
            farm_location=first_location,
            house_count=3,
            variety=default_crop.default_variety,
            cultivation_type="토경",
            wifi_ssid="",
            wifi_password="",
            crop_type=DEFAULT_CROP_TYPE,
        )

    root.title(translator.t("setup.title"))
    root.geometry("380x360")
    root.resizable(False, False)

    location_var = tk.StringVar(value=first_location)
    house_count_var = tk.StringVar(value="3")
    crop_label_var = tk.StringVar(value=default_crop_label)
    variety_var = tk.StringVar(value=default_crop.default_variety)
    cultivation_var = tk.StringVar(value="토경")
    wifi_ssid_var = tk.StringVar()
    wifi_password_var = tk.StringVar()
    result: SetupResult | None = None

    frame = ttk.Frame(root, padding=16)
    frame.pack(fill="both", expand=True)
    frame.columnconfigure(1, weight=1)

    def add_row(row: int, label: str, widget: tk.Widget) -> None:
        ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", pady=4)
        widget.grid(row=row, column=1, sticky="ew", pady=4)

    location_widget = ttk.Combobox(frame, textvariable=location_var, values=list(profiles.keys()), state="readonly")
    crop_widget = ttk.Combobox(frame, textvariable=crop_label_var, values=list(crop_type_by_label.keys()), state="readonly")
    variety_widget = ttk.Combobox(frame, textvariable=variety_var, values=default_crop.varieties, state="readonly")

    def update_varieties(*_args) -> None:
        selected_crop = crop_type_by_label.get(crop_label_var.get(), DEFAULT_CROP_TYPE)
        crop_profile = load_crop_profile(selected_crop)
        values = crop_profile.varieties or [crop_profile.default_variety]
        variety_widget.configure(values=values)
        if variety_var.get() not in values:
            variety_var.set(crop_profile.default_variety or values[0])

    crop_label_var.trace_add("write", update_varieties)

    add_row(0, translator.t("setup.location"), location_widget)
    add_row(1, translator.t("setup.house_count"), ttk.Entry(frame, textvariable=house_count_var))
    add_row(2, translator.t("setup.crop_type"), crop_widget)
    add_row(3, translator.t("setup.variety"), variety_widget)
    add_row(4, translator.t("setup.cultivation_type"), ttk.Combobox(frame, textvariable=cultivation_var, values=["토경", "수경"], state="readonly"))
    add_row(5, translator.t("setup.wifi_ssid"), ttk.Entry(frame, textvariable=wifi_ssid_var))
    add_row(6, translator.t("setup.wifi_password"), ttk.Entry(frame, textvariable=wifi_password_var, show="*"))

    def submit() -> None:
        nonlocal result
        selected_crop = crop_type_by_label.get(crop_label_var.get(), DEFAULT_CROP_TYPE)
        crop_profile = load_crop_profile(selected_crop)
        result = SetupResult(
            farm_location=location_var.get(),
            house_count=max(1, int(house_count_var.get() or "3")),
            variety=variety_var.get() or crop_profile.default_variety,
            cultivation_type=cultivation_var.get() or "토경",
            wifi_ssid=wifi_ssid_var.get().strip(),
            wifi_password=wifi_password_var.get().strip(),
            crop_type=selected_crop,
        )
        root.destroy()

    ttk.Button(frame, text=translator.t("setup.submit"), command=submit).grid(row=7, column=0, columnspan=2, pady=(16, 0), sticky="ew")
    root.mainloop()

    if result is None:
        return SetupResult(
            farm_location=first_location,
            house_count=3,
            variety=default_crop.default_variety,
            cultivation_type="토경",
            wifi_ssid="",
            wifi_password="",
            crop_type=DEFAULT_CROP_TYPE,
        )
    return result
