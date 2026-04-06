from __future__ import annotations

import json
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import ttk

from engine.i18n import Translator


@dataclass(slots=True)
class SetupResult:
    farm_location: str
    house_count: int
    variety: str
    cultivation_type: str
    wifi_ssid: str
    wifi_password: str

    def as_config_entries(self) -> dict[str, str]:
        return {
            "farm_location": self.farm_location,
            "house_count": str(self.house_count),
            "variety": self.variety,
            "cultivation_type": self.cultivation_type,
            "wifi_ssid": self.wifi_ssid,
            "wifi_password": self.wifi_password,
        }


def load_profiles(path: Path) -> dict[str, dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def run_setup_wizard(profiles: dict[str, dict], translator: Translator) -> SetupResult:
    if not profiles:
        raise ValueError("regional_profiles.json is empty")

    try:
        root = tk.Tk()
    except tk.TclError:
        first_location = next(iter(profiles))
        return SetupResult(
            farm_location=first_location,
            house_count=3,
            variety="설향",
            cultivation_type="토경",
            wifi_ssid="",
            wifi_password="",
        )

    root.title(translator.t("setup.title"))
    root.geometry("360x300")
    root.resizable(False, False)

    location_var = tk.StringVar(value=next(iter(profiles)))
    house_count_var = tk.StringVar(value="3")
    variety_var = tk.StringVar(value="설향")
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

    add_row(0, translator.t("setup.location"), ttk.Combobox(frame, textvariable=location_var, values=list(profiles.keys()), state="readonly"))
    add_row(1, translator.t("setup.house_count"), ttk.Entry(frame, textvariable=house_count_var))
    add_row(2, translator.t("setup.variety"), ttk.Combobox(frame, textvariable=variety_var, values=["설향", "금실", "매향", "기타"], state="readonly"))
    add_row(3, translator.t("setup.cultivation_type"), ttk.Combobox(frame, textvariable=cultivation_var, values=["토경", "수경"], state="readonly"))
    add_row(4, translator.t("setup.wifi_ssid"), ttk.Entry(frame, textvariable=wifi_ssid_var))
    add_row(5, translator.t("setup.wifi_password"), ttk.Entry(frame, textvariable=wifi_password_var, show="*"))

    def submit() -> None:
        nonlocal result
        result = SetupResult(
            farm_location=location_var.get(),
            house_count=max(1, int(house_count_var.get() or "3")),
            variety=variety_var.get() or "설향",
            cultivation_type=cultivation_var.get() or "토경",
            wifi_ssid=wifi_ssid_var.get().strip(),
            wifi_password=wifi_password_var.get().strip(),
        )
        root.destroy()

    ttk.Button(frame, text=translator.t("setup.submit"), command=submit).grid(row=6, column=0, columnspan=2, pady=(16, 0), sticky="ew")
    root.mainloop()

    if result is None:
        first_location = next(iter(profiles))
        return SetupResult(
            farm_location=first_location,
            house_count=3,
            variety="설향",
            cultivation_type="토경",
            wifi_ssid="",
            wifi_password="",
        )
    return result
