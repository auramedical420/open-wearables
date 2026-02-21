"""Test that Garmin dailies webhook saves steps as steps_daily_total, not steps."""

from decimal import Decimal
from uuid import uuid4

from app.schemas.series_types import SeriesType
from app.services.providers.garmin.data_247 import Garmin247Service


class TestDailiesStepsSeries:
    """Verify _build_dailies_samples uses steps_daily_total for steps."""

    def test_dailies_steps_use_daily_total_type(self):
        """Steps from dailies webhook should be saved as steps_daily_total, not steps."""
        service = Garmin247Service()
        user_id = uuid4()

        normalized = {
            "calendar_date": "2026-02-20",
            "start_time_seconds": 1740009600,
            "steps": 3392,
            "active_calories": 250,
            "resting_heart_rate": 59,
            "floors_climbed": 5,
            "distance_meters": 2500.0,
            "garmin_summary_id": "test-summary-123",
        }

        samples = service._build_dailies_samples(user_id, normalized)

        # Find the steps sample
        steps_samples = [s for s in samples if s.series_type == SeriesType.steps_daily_total]
        assert len(steps_samples) == 1, f"Expected 1 steps_daily_total sample, got {len(steps_samples)}"
        assert steps_samples[0].value == Decimal("3392")

        # Ensure no sample uses the old SeriesType.steps
        old_steps = [s for s in samples if s.series_type == SeriesType.steps]
        assert len(old_steps) == 0, "Dailies should NOT save as SeriesType.steps (epochs do that)"
