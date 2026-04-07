from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class PIDCommand:
    device: str
    duration_seconds: int
    direction: str
    reason: str


@dataclass(slots=True)
class PIDSummary:
    enabled: bool
    ec_error: float
    ph_error: float
    commands: list[PIDCommand]
    note: str


@dataclass(slots=True)
class NutrientPIDController:
    target_ec: float = 1.0
    target_ph: float = 6.0
    kp_ec: float = 18.0
    kp_ph: float = 12.0
    min_duration: int = 2
    max_duration: int = 20

    def evaluate(self, current_ec: float | None, current_ph: float | None) -> PIDSummary:
        if current_ec is None or current_ph is None:
            return PIDSummary(
                enabled=False,
                ec_error=0.0,
                ph_error=0.0,
                commands=[],
                note="EC/pH 센서값이 없어 자동 양액 제어를 건너뜁니다.",
            )

        ec_error = self.target_ec - current_ec
        ph_error = self.target_ph - current_ph
        commands: list[PIDCommand] = []

        if abs(ec_error) >= 0.12:
            seconds = max(self.min_duration, min(self.max_duration, int(abs(ec_error) * self.kp_ec)))
            commands.append(
                PIDCommand(
                    device="nutrient_mix",
                    duration_seconds=seconds,
                    direction="increase_ec" if ec_error > 0 else "dilute",
                    reason=f"EC 오차 {ec_error:+.2f}",
                )
            )

        if abs(ph_error) >= 0.25:
            seconds = max(self.min_duration, min(self.max_duration, int(abs(ph_error) * self.kp_ph)))
            commands.append(
                PIDCommand(
                    device="ph_adjust",
                    duration_seconds=seconds,
                    direction="raise_ph" if ph_error > 0 else "lower_ph",
                    reason=f"pH 오차 {ph_error:+.2f}",
                )
            )

        note = "양액 상태가 목표 범위에 가깝습니다."
        if commands:
            note = "EC/pH 편차를 보정하기 위한 펌프 제어를 제안합니다."

        return PIDSummary(
            enabled=True,
            ec_error=round(ec_error, 3),
            ph_error=round(ph_error, 3),
            commands=commands,
            note=note,
        )
