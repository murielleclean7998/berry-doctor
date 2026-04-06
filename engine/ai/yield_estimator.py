from __future__ import annotations


class YieldEstimator:
    def estimate(self, *_args, **_kwargs) -> dict:
        return {"enabled": False, "message": "Phase 3 이후에 활성화됩니다."}
