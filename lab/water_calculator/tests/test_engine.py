from __future__ import annotations

import unittest
import sys

from lab.water_calculator.engine import LabInput, TuningProfile, calculate

if sys.version_info >= (3, 10):
    from backend.app.domain.water_balance import (
        WaterBalanceInput as BackendInput,
        calculate as calculate_backend,
    )
else:
    BackendInput = None  # type: ignore[assignment,misc]
    calculate_backend = None  # type: ignore[assignment]


class WaterCalculatorLabTests(unittest.TestCase):
    def setUp(self) -> None:
        self.values = {
            "period_days": 7,
            "start_pot_weight_g": 3800,
            "end_pot_weight_g": 3550,
            "water_added_ml": 500,
            "drainage_ml": 100,
            "target_wet_weight_g": 3800,
            "watering_trigger_weight_g": 3300,
            "max_single_watering_ml": 450,
        }

    @unittest.skipIf(sys.version_info < (3, 10), "백엔드 기준 버전은 Python 3.10 이상이 필요합니다.")
    def test_default_profile_matches_backend_v1(self) -> None:
        assert BackendInput is not None
        assert calculate_backend is not None
        lab_result = calculate(LabInput(**self.values), TuningProfile())
        backend_result = calculate_backend(BackendInput(**self.values))

        comparable_fields = (
            "observation_period_days",
            "storage_change_ml",
            "net_water_added_ml",
            "estimated_water_loss_ml",
            "average_daily_loss_ml",
            "drainage_ratio_percent",
            "refill_to_target_ml",
            "recommended_water_now_ml",
            "estimated_days_until_watering",
            "status",
            "confidence",
        )
        for field in comparable_fields:
            self.assertEqual(getattr(lab_result, field), getattr(backend_result, field), field)

    def test_loss_scale_changes_experimental_loss_only(self) -> None:
        baseline = calculate(LabInput(**self.values), TuningProfile())
        tuned = calculate(
            LabInput(**self.values),
            TuningProfile(name="손실 10% 보정", loss_scale=1.1, version=2),
        )

        self.assertAlmostEqual(
            tuned.estimated_water_loss_ml,
            baseline.estimated_water_loss_ml * 1.1,
            places=2,
        )
        self.assertGreater(tuned.average_daily_loss_ml, baseline.average_daily_loss_ml)

    def test_trigger_margin_must_stay_below_wet_target(self) -> None:
        with self.assertRaisesRegex(ValueError, "마진이 적용된"):
            calculate(
                LabInput(**self.values),
                TuningProfile(name="잘못된 프로필", trigger_margin_g=500),
            )


if __name__ == "__main__":
    unittest.main()
