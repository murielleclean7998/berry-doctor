from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from engine.db.sqlite import SQLiteRepository
from engine.satellite.indices import index_to_grade


@dataclass(slots=True)
class FarmTimeline:
    repository: SQLiteRepository

    def generate_season_summary(self, house_id: int, season: str | None = None) -> dict[str, Any]:
        rows = self.repository.recent_satellite_logs(limit=24, house_id=house_id)
        month_scores: dict[str, list[float]] = {}
        for row in rows:
            capture = str(row.get("capture_date") or "")
            month_key = capture[:7]
            month_scores.setdefault(month_key, []).append(float(row.get("ndvi_mean") or 0.0))

        monthly = []
        for month_key in sorted(month_scores):
            avg = sum(month_scores[month_key]) / len(month_scores[month_key])
            grade = index_to_grade(avg)
            monthly.append({"month": month_key, "average": round(avg, 3), "grade": grade["grade"], "emoji": grade["emoji"]})

        best = max(monthly, key=lambda item: item["average"], default={"month": "-", "average": 0.0, "grade": "기록 없음"})
        latest = rows[0] if rows else None
        year_compare = float(latest.get("change_vs_year") or 0.0) if latest else 0.0
        return {
            "house_id": house_id,
            "season": season or f"{date.today().year - 1}~{date.today().year}",
            "monthly": monthly,
            "best_month": best["month"],
            "year_compare": year_compare,
            "message": self.build_message(house_id, monthly, best, year_compare),
        }

    def build_message(self, house_id: int, monthly: list[dict[str, Any]], best: dict[str, Any], year_compare: float) -> str:
        if not monthly:
            return f"{house_id}동 위성 기록이 아직 충분하지 않아요.\n위성은 바깥에서 본 참고 정보예요."
        lines = [f"📅 {house_id}동 시즌 기록", "위성은 바깥에서 본 참고 정보예요."]
        for item in monthly[-7:]:
            lines.append(f"{item['month']} {item['emoji']} {item['grade']}")
        lines.append(f"가장 좋았던 시기: {best['month']}")
        lines.append(f"작년 같은 때와 비교: {year_compare:+.2f}")
        return "\n".join(lines)
