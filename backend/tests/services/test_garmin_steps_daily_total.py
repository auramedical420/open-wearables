"""Test that Garmin dailies webhook saves steps as steps_daily_total, not steps."""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.models import DataPointSeries
from app.repositories.data_point_series_repository import DataPointSeriesRepository
from app.repositories.user_connection_repository import UserConnectionRepository
from app.schemas.series_types import SeriesType, get_series_type_id
from app.services.providers.garmin.data_247 import Garmin247Data
from app.services.providers.garmin.oauth import GarminOAuth
from tests.factories import DataPointSeriesFactory, DataSourceFactory


class TestDailiesStepsSeries:
    """Verify _build_dailies_samples uses steps_daily_total for steps."""

    @pytest.fixture
    def garmin_247(self) -> Garmin247Data:
        """Create Garmin247Data instance for testing."""
        connection_repo = UserConnectionRepository()
        oauth = GarminOAuth(
            user_repo=MagicMock(),
            connection_repo=connection_repo,
            provider_name="garmin",
            api_base_url="https://apis.garmin.com",
        )
        return Garmin247Data(
            provider_name="garmin",
            api_base_url="https://apis.garmin.com",
            oauth=oauth,
        )

    def test_dailies_steps_use_daily_total_type(self, garmin_247: Garmin247Data) -> None:
        """Steps from dailies webhook should be saved as steps_daily_total, not steps."""
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

        samples = garmin_247._build_dailies_samples(user_id, normalized)

        # Find the steps sample
        steps_samples = [s for s in samples if s.series_type == SeriesType.steps_daily_total]
        assert len(steps_samples) == 1, f"Expected 1 steps_daily_total sample, got {len(steps_samples)}"
        assert steps_samples[0].value == Decimal("3392")

        # Ensure no sample uses the old SeriesType.steps
        old_steps = [s for s in samples if s.series_type == SeriesType.steps]
        assert len(old_steps) == 0, "Dailies should NOT save as SeriesType.steps (epochs do that)"


class TestActivityAggregateStepsPriority:
    """Activity aggregates should prefer steps_daily_total over epoch SUM(steps)."""

    @pytest.fixture
    def repo(self) -> DataPointSeriesRepository:
        return DataPointSeriesRepository(DataPointSeries)

    def test_prefers_daily_total_over_epoch_sum(self, db: Session, repo: DataPointSeriesRepository) -> None:
        """When both steps and steps_daily_total exist, use steps_daily_total."""
        user_id = uuid4()
        data_source = DataSourceFactory(user_id=user_id, source="garmin")

        test_date = datetime(2026, 2, 20, 3, 0, 0, tzinfo=timezone.utc)  # midnight BRT

        # Epoch steps: data points summing to 3072 (imprecise)
        steps_type_id = get_series_type_id(SeriesType.steps)
        for i in range(96):
            ts = test_date + timedelta(minutes=15 * i)
            DataPointSeriesFactory(
                data_source=data_source,
                series_type_definition_id=steps_type_id,
                recorded_at=ts,
                value=32,  # 32 * 96 = 3072
            )

        # Daily total: 3392 (accurate, from Garmin dailies)
        daily_total_type_id = get_series_type_id(SeriesType.steps_daily_total)
        DataPointSeriesFactory(
            data_source=data_source,
            series_type_definition_id=daily_total_type_id,
            recorded_at=test_date,
            value=3392,
        )

        db.flush()

        results = repo.get_daily_activity_aggregates(
            db_session=db,
            user_id=user_id,
            start_date=date(2026, 2, 20),
            end_date=date(2026, 2, 21),
        )

        assert len(results) == 1
        # Should use daily total (3392), not epoch sum (3072)
        assert results[0]["steps_sum"] == 3392

    def test_falls_back_to_epoch_sum_when_no_daily_total(self, db: Session, repo: DataPointSeriesRepository) -> None:
        """When only epoch steps exist (no daily total), use SUM(steps) as before."""
        user_id = uuid4()
        data_source = DataSourceFactory(user_id=user_id, source="garmin")

        test_date = datetime(2026, 2, 20, 12, 0, 0, tzinfo=timezone.utc)
        steps_type_id = get_series_type_id(SeriesType.steps)

        DataPointSeriesFactory(
            data_source=data_source,
            series_type_definition_id=steps_type_id,
            recorded_at=test_date,
            value=5000,
        )

        db.flush()

        results = repo.get_daily_activity_aggregates(
            db_session=db,
            user_id=user_id,
            start_date=date(2026, 2, 20),
            end_date=date(2026, 2, 21),
        )

        assert len(results) == 1
        assert results[0]["steps_sum"] == 5000
