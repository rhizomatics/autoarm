import datetime as dt
import re
from unittest.mock import Mock

from custom_components.autoarm.const import ChangeSource
from custom_components.autoarm.helpers import (
    AppHealthTracker,
    ExtendedExtendedJSONEncoder,
    change_source_as_enum,
    deobjectify,
    safe_state,
)


def test_change_source_as_enum_none() -> None:
    assert change_source_as_enum(None) is None


def test_change_source_as_enum_valid() -> None:
    assert change_source_as_enum("alarm_panel") == ChangeSource.ALARM_PANEL


def test_change_source_as_enum_invalid() -> None:
    assert change_source_as_enum("not_a_source") is None


def test_safe_state_exception() -> None:
    bad_state = Mock()
    bad_state.state = property(lambda _self: (_ for _ in ()).throw(RuntimeError("bad")))
    type(bad_state).state = property(lambda _self: (_ for _ in ()).throw(RuntimeError("bad")))
    assert safe_state(bad_state) is None


def test_deobjectify_datetime() -> None:
    now = dt.datetime(2024, 1, 15, 10, 0, 0, tzinfo=dt.UTC)
    result = deobjectify(now)
    assert result == now.isoformat()


def test_deobjectify_no_as_dict() -> None:
    class Opaque:
        def __repr__(self) -> str:
            return "opaque"

    result = deobjectify(Opaque())
    assert isinstance(result, str)


def test_extended_json_encoder_regex() -> None:
    encoder = ExtendedExtendedJSONEncoder()
    pattern = re.compile(r"\d+")
    result = encoder.default(pattern)
    assert r"\d+" in result


def test_extended_json_encoder_timedelta() -> None:
    encoder = ExtendedExtendedJSONEncoder()
    result = encoder.default(dt.timedelta(seconds=30))
    assert "30 seconds" in result


def test_extended_json_encoder_time() -> None:
    encoder = ExtendedExtendedJSONEncoder()
    result = encoder.default(dt.time(1, 10, 30, 101, dt.UTC))
    assert result == "01:10:30.000101+00:00"


def test_app_health_tracker_records_runtime_error(hass) -> None:  # noqa: ANN001
    tracker = AppHealthTracker(hass)
    assert tracker.failures == 0
    tracker.record_runtime_error()
    assert tracker.failures == 1
