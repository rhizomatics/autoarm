import asyncio
import datetime as dt
from collections.abc import AsyncGenerator

import homeassistant.util.dt as dt_util
import pytest
from homeassistant.components.alarm_control_panel.const import AlarmControlPanelState
from homeassistant.components.calendar import CalendarEntity
from homeassistant.core import HomeAssistant

from custom_components.autoarm.autoarming import AlarmArmer, Intervention
from custom_components.autoarm.const import ChangeSource

TEST_PANEL = "alarm_control_panel.test_panel"


@pytest.fixture
async def autoarmer(hass: HomeAssistant) -> AsyncGenerator[AlarmArmer]:
    uut = AlarmArmer(hass, TEST_PANEL, occupancy={"entity_id": ["person.tester_bob"]})
    await uut.initialize()
    yield uut
    uut.shutdown()


@pytest.fixture
def day(hass: HomeAssistant) -> None:
    hass.states.async_set("sun.sun", "above_horizon")


@pytest.fixture
def night(hass: HomeAssistant) -> None:
    hass.states.async_set("sun.sun", "below_horizon")


@pytest.fixture
def occupied(hass: HomeAssistant) -> None:
    hass.states.async_set("person.tester_bob", "home")


@pytest.fixture
def unoccupied(hass: HomeAssistant) -> None:
    hass.states.async_set("person.tester_bob", "away")


async def test_arm_preserves_panel_attributes(autoarmer: AlarmArmer, hass: HomeAssistant) -> None:
    hass.states.async_set(entity_id=TEST_PANEL, new_state="disarmed", attributes={"icon": "mdi:alarm-panel"})
    await autoarmer.arm(AlarmControlPanelState.ARMED_VACATION)
    assert hass.states.get(TEST_PANEL).attributes.get("icon") == "mdi:alarm-panel"  # type:ignore[attr-defined]


async def test_vacation_day_occupied(autoarmer: AlarmArmer, day: None, occupied: None) -> None:  # noqa: ARG001
    await autoarmer.arm(AlarmControlPanelState.ARMED_VACATION)
    assert autoarmer.determine_state() == AlarmControlPanelState.ARMED_VACATION


async def test_vacation_day_unoccupied(autoarmer: AlarmArmer, day: None, unoccupied: None) -> None:  # noqa: ARG001
    await autoarmer.arm(AlarmControlPanelState.ARMED_VACATION)
    assert autoarmer.determine_state() == AlarmControlPanelState.ARMED_VACATION


def test_occupied_day_armed_default(autoarmer: AlarmArmer, day: None, occupied: None) -> None:  # noqa: ARG001
    assert autoarmer.determine_state() == AlarmControlPanelState.ARMED_HOME


def test_occupied_day_disarmed_default(autoarmer: AlarmArmer, day: None, occupied: None) -> None:  # noqa: ARG001
    autoarmer.occupied_defaults["day"] = AlarmControlPanelState.DISARMED
    assert autoarmer.determine_state() == AlarmControlPanelState.DISARMED


def test_occupied_night(autoarmer: AlarmArmer, night: None, occupied: None) -> None:  # noqa: ARG001
    assert autoarmer.determine_state() == AlarmControlPanelState.ARMED_NIGHT


def test_unoccupied_day(autoarmer: AlarmArmer, day: None, unoccupied: None) -> None:  # noqa: ARG001
    assert autoarmer.determine_state() == AlarmControlPanelState.ARMED_AWAY


def test_unoccupied_night(autoarmer: AlarmArmer, night: None, unoccupied: None) -> None:  # noqa: ARG001
    assert autoarmer.determine_state() == AlarmControlPanelState.ARMED_AWAY


def test_not_occupied(hass: HomeAssistant, autoarmer: AlarmArmer) -> None:
    hass.states.async_set("person.tester_bob", "away")
    assert autoarmer.is_occupied() is False


def test_occupied(hass: HomeAssistant, autoarmer: AlarmArmer) -> None:
    hass.states.async_set("person.tester_bob", "home")
    assert autoarmer.is_occupied() is True


async def test_day(hass: HomeAssistant, autoarmer: AlarmArmer) -> None:
    hass.states.async_set("sun.sun", "above_horizon")
    await hass.async_block_till_done()
    assert autoarmer.is_night() is False


async def test_on_sunset(autoarmer: AlarmArmer) -> None:
    await autoarmer.arm(AlarmControlPanelState.PENDING)
    await autoarmer.on_sunset()
    assert autoarmer.armed_state() != AlarmControlPanelState.PENDING


async def test_on_sunrise(autoarmer: AlarmArmer) -> None:
    await autoarmer.arm(AlarmControlPanelState.PENDING)
    assert autoarmer.armed_state() == AlarmControlPanelState.PENDING
    await autoarmer.on_sunrise()
    assert autoarmer.armed_state() != AlarmControlPanelState.PENDING


async def test_on_sunrise_with_cutoff_active_no_interventions(
    autoarmer: AlarmArmer,
    hass: HomeAssistant,
) -> None:
    await autoarmer.arm(AlarmControlPanelState.PENDING)
    await hass.async_block_till_done()
    autoarmer.sunrise_cutoff = (dt_util.now() + dt.timedelta(seconds=2)).time()
    autoarmer.interventions = []
    await autoarmer.on_sunrise()
    await hass.async_block_till_done()
    # wait for delayed_reset
    await asyncio.sleep(2)
    assert autoarmer.armed_state() != AlarmControlPanelState.PENDING


async def test_on_sunrise_with_intervention_before_cutoff(
    autoarmer: AlarmArmer,
    hass: HomeAssistant,
) -> None:
    await autoarmer.arm(AlarmControlPanelState.ARMED_AWAY)
    autoarmer.sunrise_cutoff = (dt_util.now() + dt.timedelta(seconds=2)).time()
    await autoarmer.on_sunrise()
    hass.states.async_set(TEST_PANEL, "pending")
    await hass.async_block_till_done()
    # wait for delayed_reset
    await asyncio.sleep(2)
    assert autoarmer.armed_state() == AlarmControlPanelState.PENDING


async def test_manual_disarmed_ignores_occupied_night(hass: HomeAssistant, autoarmer: AlarmArmer) -> None:
    hass.states.async_set("person.tester_bob", "home")
    await hass.async_block_till_done()
    hass.states.async_set(TEST_PANEL, "disarmed")
    await hass.async_block_till_done()
    hass.states.async_set("sun.sun", "below_horizon")
    await hass.async_block_till_done()
    assert await autoarmer.reset_armed_state(source=ChangeSource.SUNSET) == "disarmed"


async def test_manual_disarmed_ignores_occupied_day(hass: HomeAssistant, autoarmer: AlarmArmer) -> None:
    hass.states.async_set("person.tester_bob", "home")
    await hass.async_block_till_done()
    hass.states.async_set(TEST_PANEL, "disarmed")
    await hass.async_block_till_done()
    hass.states.async_set("sun.sun", "above_horizon")
    assert await autoarmer.reset_armed_state(source=ChangeSource.SUNRISE) == "disarmed"


async def test_unforced_reset_leaves_disarmed(hass: HomeAssistant, autoarmer: AlarmArmer) -> None:
    hass.states.async_set("sun.sun", "above_horizon")
    hass.states.async_set("person.tester_bob", "home")
    await hass.async_block_till_done()
    hass.states.async_set(TEST_PANEL, "disarmed")
    await hass.async_block_till_done()
    assert await autoarmer.reset_armed_state() == "disarmed"


async def test_disarmed_intervention_overridden_by_occupancy(hass: HomeAssistant, autoarmer: AlarmArmer) -> None:
    hass.states.async_set("sun.sun", "above_horizon")
    hass.states.async_set("person.tester_bob", "not_home")
    hass.states.async_set(TEST_PANEL, "disarmed")
    await hass.async_block_till_done()
    assert await autoarmer.reset_armed_state() == "armed_away"


async def test_forced_reset_sets_armed_home_from_disarmed(hass: HomeAssistant, autoarmer: AlarmArmer) -> None:
    hass.states.async_set("sun.sun", "above_horizon")
    hass.states.async_set("person.tester_bob", "home")
    hass.states.async_set(TEST_PANEL, "disarmed")
    await hass.async_block_till_done()
    assert await autoarmer.reset_armed_state(Intervention(dt_util.now(), ChangeSource.BUTTON, None)) == "armed_home"


async def test_reset_sets_disarmed_from_unknown(hass: HomeAssistant, autoarmer: AlarmArmer) -> None:
    hass.states.async_set("sun.sun", "above_horizon")
    hass.states.async_set("person.tester_bob", "home")
    hass.states.async_set(TEST_PANEL, "unknown")
    await hass.async_block_till_done()
    assert await autoarmer.reset_armed_state() == "armed_home"


async def test_reset_armed_state_uses_daytime_default(hass: HomeAssistant) -> None:
    autoarmer = AlarmArmer(
        hass, TEST_PANEL, occupancy={"default_state": {"day": "disarmed"}, "entity_id": ["person.tester_bob"]}
    )
    await autoarmer.initialize()
    hass.states.async_set("sun.sun", "above_horizon")
    hass.states.async_set("person.tester_bob", "home")
    hass.states.async_set(TEST_PANEL, "unknown")
    await hass.async_block_till_done()
    assert await autoarmer.reset_armed_state() == "disarmed"


async def test_housekeeping_prunes_calendar_events(hass: HomeAssistant, local_calendar: CalendarEntity) -> None:
    await local_calendar.async_create_event(
        dtstart=dt_util.now() - dt.timedelta(minutes=5),
        dtend=dt_util.now() + dt.timedelta(seconds=2),
        summary="Testing Day",
    )

    autoarmer = AlarmArmer(
        hass,
        TEST_PANEL,
        occupancy={"default_state": {"day": "disarmed"}, "entity_id": ["person.tester_bob"]},
        calendars=[{"entity_id": "calendar.testing_calendar", "state_patterns": {"disarmed": ".*"}}],
    )
    await autoarmer.initialize()
    cal_event = autoarmer.active_calendar_event()
    assert cal_event is not None
    assert cal_event.summary == "Testing Day"

    await asyncio.sleep(2)
    await autoarmer.housekeeping(dt_util.now())
    assert autoarmer.active_calendar_event() is None


async def test_housekeeping_leaves_new_interventions(hass: HomeAssistant) -> None:
    autoarmer = AlarmArmer(hass, TEST_PANEL)
    await autoarmer.initialize()
    hass.states.async_set(TEST_PANEL, "disarmed")
    await hass.async_block_till_done()
    assert len(autoarmer.interventions) > 0

    await autoarmer.housekeeping(dt_util.now())
    assert len(autoarmer.interventions) > 0


async def test_housekeeping_prunes_old_interventions(hass: HomeAssistant) -> None:
    autoarmer = AlarmArmer(hass, TEST_PANEL)
    await autoarmer.initialize()
    hass.states.async_set(TEST_PANEL, "disarmed")
    await hass.async_block_till_done()
    assert len(autoarmer.interventions) > 0
    autoarmer.intervention_ttl = 0

    await autoarmer.housekeeping(dt_util.now())
    assert len(autoarmer.interventions) == 0


async def test_notify_skipped_when_no_service(hass: HomeAssistant) -> None:
    """Test that notification is skipped when no service is configured."""
    armer = AlarmArmer(hass, TEST_PANEL, notify={})
    calls: list[dict] = []

    def mock_handler(call) -> None:  # noqa: ANN001
        calls.append({"service": call.service, "data": dict(call.data)})

    hass.services.async_register("notify", "test_service", mock_handler)
    await armer.notify(ChangeSource.BUTTON, "Test message")
    # No service configured, so handler should not be called
    assert len(calls) == 0


async def test_notify_calls_service(hass: HomeAssistant) -> None:
    """Test that notify calls hass.services.async_call with correct parameters."""
    notify_config = {
        "common": {"service": "notify.test_service"},
    }
    armer = AlarmArmer(hass, TEST_PANEL, notify=notify_config)
    calls: list[dict] = []

    async def mock_handler(call) -> None:  # noqa: ANN001
        calls.append({"service": call.service, "data": dict(call.data)})

    hass.services.async_register("notify", "test_service", mock_handler)
    await armer.notify(ChangeSource.BUTTON, "Test message")

    assert len(calls) == 1
    assert calls[0]["data"]["message"] == "Test message"
    assert calls[0]["data"]["title"] == "Alarm Auto Arming"


async def test_notify_with_custom_title(hass: HomeAssistant) -> None:
    """Test that notify uses custom title when provided."""
    notify_config = {
        "common": {"service": "notify.test_service"},
    }
    armer = AlarmArmer(hass, TEST_PANEL, notify=notify_config)
    calls: list[dict] = []

    async def mock_handler(call) -> None:  # noqa: ANN001
        calls.append({"service": call.service, "data": dict(call.data)})

    hass.services.async_register("notify", "test_service", mock_handler)
    await armer.notify(ChangeSource.BUTTON, "Test message", title="Custom Title")

    assert len(calls) == 1
    assert calls[0]["data"]["title"] == "Custom Title"


async def test_notify_profile_merging(hass: HomeAssistant) -> None:
    """Test that selected profile is merged with common profile."""
    notify_config = {
        "common": {"service": "notify.common_service", "data": {"priority": "low"}},
        "quiet": {"service": "notify.quiet_service", "source": [ChangeSource.BUTTON], "data": {"sound": "none"}},
    }
    armer = AlarmArmer(hass, TEST_PANEL, notify=notify_config)
    calls: list[dict] = []

    async def mock_handler(call) -> None:  # noqa: ANN001
        calls.append({"service": call.service, "data": dict(call.data)})

    hass.services.async_register("notify", "quiet_service", mock_handler)
    await armer.notify(ChangeSource.BUTTON, "Test message")

    assert len(calls) == 1
    # Data should have both priority from common and sound from quiet
    assert calls[0]["data"]["data"]["priority"] == "low"
    assert calls[0]["data"]["data"]["sound"] == "none"


async def test_notify_source_replacement(hass: HomeAssistant) -> None:
    """Test that source is set in data when data['source'] is None."""
    notify_config = {
        "common": {"service": "notify.test_service", "data": {"source": None}},
    }
    armer = AlarmArmer(hass, TEST_PANEL, notify=notify_config)
    calls: list[dict] = []

    async def mock_handler(call) -> None:  # noqa: ANN001
        calls.append({"service": call.service, "data": dict(call.data)})

    hass.services.async_register("notify", "test_service", mock_handler)
    await armer.notify(ChangeSource.ALARM_PANEL, "Test message")

    assert len(calls) == 1
    assert calls[0]["data"]["data"]["source"] == ChangeSource.ALARM_PANEL


async def test_notify_supernotify_scenario(hass: HomeAssistant) -> None:
    """Test that supernotify scenarios are added to data when configured."""
    notify_config = {
        "common": {"service": "notify.test_service", "supernotify": True, "scenario": ["urgent"]},
    }
    armer = AlarmArmer(hass, TEST_PANEL, notify=notify_config)
    calls: list[dict] = []

    async def mock_handler(call) -> None:  # noqa: ANN001
        calls.append({"service": call.service, "data": dict(call.data)})

    hass.services.async_register("notify", "test_service", mock_handler)
    await armer.notify(ChangeSource.BUTTON, "Test message")

    assert len(calls) == 1
    assert calls[0]["data"]["data"]["apply_scenarios"] == ["urgent"]


async def test_notify_exception_records_runtime_error(hass: HomeAssistant) -> None:
    """Test that exceptions during notify call record_runtime_error."""
    # Use a non-existent service to trigger ServiceNotFound exception
    notify_config = {
        "common": {"service": "notify.nonexistent_service"},
    }
    armer = AlarmArmer(hass, TEST_PANEL, notify=notify_config)
    initial_failures = armer.failures

    # Don't register the service - this should cause an exception
    await armer.notify(ChangeSource.BUTTON, "Test message")

    assert armer.failures == initial_failures + 1


async def test_notify_strips_notify_prefix_from_service(hass: HomeAssistant) -> None:
    """Test that 'notify.' prefix is stripped from service name."""
    notify_config = {
        "common": {"service": "notify.mobile_app"},
    }
    armer = AlarmArmer(hass, TEST_PANEL, notify=notify_config)
    calls: list[dict] = []

    async def mock_handler(call) -> None:  # noqa: ANN001
        calls.append({"service": call.service, "data": dict(call.data)})

    hass.services.async_register("notify", "mobile_app", mock_handler)
    await armer.notify(ChangeSource.BUTTON, "Test message")

    assert len(calls) == 1
    assert calls[0]["service"] == "mobile_app"
