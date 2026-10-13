import asyncio
import datetime as dt
from collections.abc import Generator
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, patch

import homeassistant.util.dt as dt_util
import pytest
from homeassistant.components.alarm_control_panel.const import AlarmControlPanelState
from homeassistant.components.calendar import CalendarEntity
from homeassistant.core import HomeAssistant, State
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.autoarm.config_flow import (
    CONF_CALENDAR_ARMED_END_MODE,
    CONF_CALENDAR_ENTITIES,
    CONF_OCCUPANCY_DEFAULT_AFTER_BEDTIME,
    CONF_OCCUPANCY_DEFAULT_DAY,
    CONF_OCCUPANCY_DEFAULT_NIGHT,
    CONF_PERSON_ENTITIES,
    CONF_SUNRISE_TRIGGER,
    CONF_UNOCCUPIED_DELAY,
    CONF_USE_ALARM_SERVICE,
)
from custom_components.autoarm.const import (
    CONF_ALARM_PANEL,
    DOMAIN,
    TRIGGER_ON,
    YAML_DATA_KEY,
    ChangeSource,
)
from custom_components.autoarm.notifier import Notifier

if TYPE_CHECKING:
    from freezegun.api import FrozenDateTimeFactory

PANEL = "alarm_panel.testing"
BEDTIME = "binary_sensor.bedtime"
BEDTIME_ATTRS: dict[str, Any] = {"friendly_name": "Bedtime"}

ENTRY_OPTIONS: dict[str, Any] = {
    # leaving home is acted on straight away
    CONF_UNOCCUPIED_DELAY: 0,
    CONF_CALENDAR_ENTITIES: [],
    CONF_PERSON_ENTITIES: ["person.house_owner", "person.tenant"],
    CONF_OCCUPANCY_DEFAULT_DAY: "armed_home",
    CONF_OCCUPANCY_DEFAULT_NIGHT: None,
    CONF_USE_ALARM_SERVICE: True,
    "time_of_day_armed_night": [BEDTIME],
}
# the documented recipe: bedtime sensor, a calendar for vacations and time away, and disarmed by day, armed home by night
RECIPE_OPTIONS: dict[str, Any] = {
    CONF_CALENDAR_ENTITIES: ["calendar.testing_calendar"],
    CONF_OCCUPANCY_DEFAULT_DAY: "disarmed",
    CONF_OCCUPANCY_DEFAULT_NIGHT: "armed_home",
}
# the same without the calendar, for bedtime alone
BEDTIME_OPTIONS: dict[str, Any] = {**RECIPE_OPTIONS, CONF_CALENDAR_ENTITIES: []}


@pytest.fixture(autouse=True)
def no_sun_listeners() -> Generator[None]:
    """Sunrise and sunset are called by the tests, as the real listeners fire as the clock is moved past them"""
    with (
        patch("custom_components.autoarm.autoarming.async_track_sunrise", return_value=lambda: None),
        patch("custom_components.autoarm.autoarming.async_track_sunset", return_value=lambda: None),
    ):
        yield


async def _setup_entry(hass: HomeAssistant, options: dict[str, Any] | None = None) -> MockConfigEntry:
    hass.data[YAML_DATA_KEY] = {}
    entry = MockConfigEntry(
        domain=DOMAIN, title="Auto Arm", data={CONF_ALARM_PANEL: PANEL}, options={**ENTRY_OPTIONS, **(options or {})}
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def _bedtime(hass: HomeAssistant, state: str) -> None:
    hass.states.async_set(BEDTIME, state, BEDTIME_ATTRS)
    await hass.async_block_till_done()


def _clock(freezer: FrozenDateTimeFactory, hour: int, minute: int = 0, day: int = 12) -> None:
    freezer.move_to(dt_util.as_utc(dt.datetime(2026, 10, day, hour, minute, tzinfo=dt_util.get_default_time_zone())))


def panel_state(hass: HomeAssistant) -> str | None:
    state = hass.states.get(PANEL)
    return state.state if state else None


async def test_recipe_bedtime_with_sun(
    local_calendar: CalendarEntity, hass: HomeAssistant, mock_notify: Any, freezer: FrozenDateTimeFactory
) -> None:
    """Armed home from sunset to bedtime, armed night for bedtime, then armed home again until the sun is up"""
    _clock(freezer, 17)
    hass.states.async_set("person.tenant", "home")
    hass.states.async_set("sun.sun", "above_horizon")
    hass.states.async_set(BEDTIME, "off", BEDTIME_ATTRS)
    entry = await _setup_entry(hass, RECIPE_OPTIONS)
    armer = entry.runtime_data
    assert panel_state(hass) == AlarmControlPanelState.DISARMED

    _clock(freezer, 18)
    hass.states.async_set("sun.sun", "below_horizon")
    await armer.on_sunset()
    assert panel_state(hass) == AlarmControlPanelState.ARMED_HOME

    _clock(freezer, 23)
    await _bedtime(hass, "on")
    assert panel_state(hass) == AlarmControlPanelState.ARMED_NIGHT

    # an early summer sunrise doesn't cut bedtime short, and bedtime then ends in daylight
    _clock(freezer, 5, day=13)
    hass.states.async_set("sun.sun", "above_horizon")
    await armer.on_sunrise()
    assert panel_state(hass) == AlarmControlPanelState.ARMED_NIGHT
    _clock(freezer, 7, day=13)
    await _bedtime(hass, "off")
    assert panel_state(hass) == AlarmControlPanelState.DISARMED

    # and the next evening is armed home again, with bedtime having ended earlier today
    _clock(freezer, 18, day=13)
    hass.states.async_set("sun.sun", "below_horizon")
    await armer.on_sunset()
    assert panel_state(hass) == AlarmControlPanelState.ARMED_HOME


async def test_recipe_bedtime_ending_before_sunrise(
    hass: HomeAssistant, mock_notify: Any, freezer: FrozenDateTimeFactory
) -> None:
    """Bedtime ending in the dark goes to the state for after bedtime, and sunrise then works the state out again"""
    _clock(freezer, 23)
    hass.states.async_set("person.tenant", "home")
    hass.states.async_set("sun.sun", "below_horizon")
    hass.states.async_set(BEDTIME, "on", BEDTIME_ATTRS)
    entry = await _setup_entry(hass, {**BEDTIME_OPTIONS, CONF_OCCUPANCY_DEFAULT_NIGHT: "armed_night"})
    armer = entry.runtime_data
    assert panel_state(hass) == AlarmControlPanelState.ARMED_NIGHT

    _clock(freezer, 7, day=13)
    await _bedtime(hass, "off")
    assert panel_state(hass) == AlarmControlPanelState.ARMED_HOME

    # someone else coming home before sunrise changes nothing
    hass.states.async_set("person.house_owner", "home")
    await hass.async_block_till_done()
    assert panel_state(hass) == AlarmControlPanelState.ARMED_HOME

    # sunrise, seen ahead of the sun entity changing state
    _clock(freezer, 7, 40, day=13)
    assert await armer.sun_trigger_active(sunrise=True)
    await armer.on_sunrise()
    assert panel_state(hass) == AlarmControlPanelState.DISARMED
    assert armer.last_change.source == ChangeSource.SUNRISE

    # and after sunset it's the evening before bedtime, not after it
    _clock(freezer, 18, day=13)
    hass.states.async_set("sun.sun", "above_horizon")
    hass.states.async_set("sun.sun", "below_horizon")
    await armer.on_sunset()
    assert panel_state(hass) == AlarmControlPanelState.ARMED_NIGHT


async def test_recipe_disarmed_after_bedtime(hass: HomeAssistant, mock_notify: Any, freezer: FrozenDateTimeFactory) -> None:
    _clock(freezer, 23)
    hass.states.async_set("person.tenant", "home")
    hass.states.async_set("sun.sun", "below_horizon")
    hass.states.async_set(BEDTIME, "on", BEDTIME_ATTRS)
    await _setup_entry(hass, {**BEDTIME_OPTIONS, CONF_OCCUPANCY_DEFAULT_AFTER_BEDTIME: "disarmed"})

    _clock(freezer, 7, day=13)
    await _bedtime(hass, "off")

    assert panel_state(hass) == AlarmControlPanelState.DISARMED


async def test_bedtime_at_any_time_of_day(hass: HomeAssistant, mock_notify: Any, freezer: FrozenDateTimeFactory) -> None:
    """A shift worker's bedtime is armed night in daylight, with sunset ignored during it"""
    _clock(freezer, 9)
    hass.states.async_set("person.tenant", "home")
    hass.states.async_set("sun.sun", "above_horizon")
    hass.states.async_set(BEDTIME, "off", BEDTIME_ATTRS)
    entry = await _setup_entry(hass, BEDTIME_OPTIONS)
    armer = entry.runtime_data
    assert panel_state(hass) == AlarmControlPanelState.DISARMED

    await _bedtime(hass, "on")
    assert panel_state(hass) == AlarmControlPanelState.ARMED_NIGHT

    _clock(freezer, 16)
    hass.states.async_set("sun.sun", "below_horizon")
    await armer.on_sunset()
    assert panel_state(hass) == AlarmControlPanelState.ARMED_NIGHT

    # ending after dark, there's no evening before the next bedtime
    _clock(freezer, 17)
    await _bedtime(hass, "off")
    assert panel_state(hass) == AlarmControlPanelState.ARMED_HOME
    assert armer.after_bedtime()


async def test_bedtime_cancelled_when_everyone_leaves(hass: HomeAssistant, mock_notify: Any) -> None:
    hass.states.async_set("person.tenant", "home")
    hass.states.async_set("sun.sun", "below_horizon")
    hass.states.async_set(BEDTIME, "on", BEDTIME_ATTRS)
    await _setup_entry(hass, BEDTIME_OPTIONS)
    assert panel_state(hass) == AlarmControlPanelState.ARMED_NIGHT

    hass.states.async_set("person.tenant", "not_home")
    await hass.async_block_till_done()
    assert panel_state(hass) == AlarmControlPanelState.ARMED_AWAY

    hass.states.async_set("person.tenant", "home")
    await hass.async_block_till_done()
    assert panel_state(hass) == AlarmControlPanelState.ARMED_NIGHT


async def test_sun_triggers_ahead_of_sun_entity(hass: HomeAssistant, mock_notify: Any) -> None:
    """Sunrise and sunset can be seen before the sun entity changes state, and aren't taken for the night or day before"""
    hass.states.async_set("person.tenant", "home")
    hass.states.async_set("sun.sun", "below_horizon")
    entry = await _setup_entry(hass, {**BEDTIME_OPTIONS, "time_of_day_armed_night": []})
    armer = entry.runtime_data
    assert panel_state(hass) == AlarmControlPanelState.ARMED_NIGHT

    await armer.on_sunrise()
    assert panel_state(hass) == AlarmControlPanelState.DISARMED

    hass.states.async_set("sun.sun", "above_horizon")
    await armer.on_sunset()
    assert panel_state(hass) == AlarmControlPanelState.ARMED_NIGHT


async def test_armed_night_from_evening_with_no_bedtime(
    local_calendar: CalendarEntity, hass: HomeAssistant, mock_notify: Any
) -> None:
    """The night is armed night unless a bedtime sensor, or a calendar event today, is going to set it"""
    hass.states.async_set("person.tenant", "home")
    hass.states.async_set("sun.sun", "below_horizon")
    entry = await _setup_entry(hass, {**RECIPE_OPTIONS, "time_of_day_armed_night": []})
    armer = entry.runtime_data
    assert not await armer.armed_night_programmed()
    assert panel_state(hass) == AlarmControlPanelState.ARMED_NIGHT

    start_of_day = dt_util.start_of_local_day()
    await local_calendar.async_create_event(
        dtstart=start_of_day + dt.timedelta(hours=23, minutes=58),
        dtend=start_of_day + dt.timedelta(hours=23, minutes=59),
        summary="Armed Night",
    )
    assert await armer.armed_night_programmed()
    hass.states.async_set(PANEL, "disarmed")
    await hass.services.async_call(DOMAIN, "reset_state", blocking=True)
    assert panel_state(hass) == AlarmControlPanelState.ARMED_HOME


async def test_recipe_bedtime_left_on_during_vacation(
    local_calendar: CalendarEntity, hass: HomeAssistant, mock_notify: Any
) -> None:
    hass.states.async_set("person.tenant", "not_home")
    hass.states.async_set("sun.sun", "below_horizon")
    hass.states.async_set(BEDTIME, "off", BEDTIME_ATTRS)
    start_of_day = dt_util.start_of_local_day()
    await local_calendar.async_create_event(
        dtstart=start_of_day, dtend=start_of_day + dt.timedelta(days=1) - dt.timedelta(seconds=1), summary="Vacation"
    )
    entry = await _setup_entry(hass, RECIPE_OPTIONS)
    assert panel_state(hass) == AlarmControlPanelState.ARMED_VACATION

    await _bedtime(hass, "on")
    assert panel_state(hass) == AlarmControlPanelState.ARMED_VACATION

    await hass.services.async_call(DOMAIN, "reset_state", blocking=True)
    assert panel_state(hass) == AlarmControlPanelState.ARMED_VACATION

    await _bedtime(hass, "off")
    assert panel_state(hass) == AlarmControlPanelState.ARMED_VACATION
    assert entry.runtime_data.last_change.source == ChangeSource.CALENDAR


async def test_recipe_away_event_ending_during_bedtime(
    local_calendar: CalendarEntity, hass: HomeAssistant, mock_notify: Any
) -> None:
    hass.states.async_set("person.tenant", "home")
    hass.states.async_set("sun.sun", "below_horizon")
    hass.states.async_set(BEDTIME, "off", BEDTIME_ATTRS)
    await local_calendar.async_create_event(
        dtstart=dt_util.start_of_local_day(), dtend=dt_util.now() + dt.timedelta(seconds=2), summary="Away"
    )
    entry = await _setup_entry(hass, RECIPE_OPTIONS)
    assert panel_state(hass) == AlarmControlPanelState.ARMED_AWAY

    await _bedtime(hass, "on")
    assert panel_state(hass) == AlarmControlPanelState.ARMED_AWAY

    await asyncio.sleep(3)
    await hass.async_block_till_done()
    assert panel_state(hass) == AlarmControlPanelState.ARMED_NIGHT
    assert entry.runtime_data.last_change.source == ChangeSource.TOD


async def test_recipe_out_at_bedtime_and_home_later(
    local_calendar: CalendarEntity, hass: HomeAssistant, mock_notify: Any
) -> None:
    hass.states.async_set("person.house_owner", "not_home")
    hass.states.async_set("person.tenant", "not_home")
    hass.states.async_set("sun.sun", "below_horizon")
    hass.states.async_set(BEDTIME, "off", BEDTIME_ATTRS)
    await _setup_entry(hass, RECIPE_OPTIONS)
    assert panel_state(hass) == AlarmControlPanelState.ARMED_AWAY

    await _bedtime(hass, "on")
    assert panel_state(hass) == AlarmControlPanelState.ARMED_AWAY

    hass.states.async_set("person.tenant", "home")
    await hass.async_block_till_done()
    assert panel_state(hass) == AlarmControlPanelState.ARMED_NIGHT

    hass.states.async_set("person.tenant", "not_home")
    await hass.async_block_till_done()
    assert panel_state(hass) == AlarmControlPanelState.ARMED_AWAY

    await _bedtime(hass, "off")
    assert panel_state(hass) == AlarmControlPanelState.ARMED_AWAY


async def test_sensor_turning_on_arms_with_tod_source_and_context(hass: HomeAssistant, mock_notify: Any) -> None:
    hass.states.async_set("person.tenant", "home")
    hass.states.async_set("sun.sun", "above_horizon")
    hass.states.async_set(BEDTIME, "off", BEDTIME_ATTRS)
    entry = await _setup_entry(hass)
    assert panel_state(hass) == AlarmControlPanelState.ARMED_HOME
    triggered: list[Any] = []
    hass.bus.async_listen("autoarm_triggered", triggered.append)

    await _bedtime(hass, "on")

    assert panel_state(hass) == AlarmControlPanelState.ARMED_NIGHT
    assert entry.runtime_data.last_change.source == ChangeSource.TOD
    sensor_state: State | None = hass.states.get(BEDTIME)
    assert sensor_state is not None
    assert len(triggered) == 1
    assert triggered[0].data["source"] == "tod"
    assert triggered[0].data["summary"] == "Bedtime"
    assert triggered[0].context.parent_id == sensor_state.context.id
    last_calc: State | None = hass.states.get("sensor.autoarm_last_calculation")
    assert last_calc is not None


async def test_sensor_on_at_startup_arms(hass: HomeAssistant, mock_notify: Any) -> None:
    hass.states.async_set("person.tenant", "home")
    hass.states.async_set("sun.sun", "above_horizon")
    hass.states.async_set(PANEL, "disarmed")
    hass.states.async_set(BEDTIME, "on", BEDTIME_ATTRS)

    await _setup_entry(hass)

    assert panel_state(hass) == AlarmControlPanelState.ARMED_NIGHT


async def test_sensor_appearing_after_startup_arms(hass: HomeAssistant, mock_notify: Any) -> None:
    hass.states.async_set("person.tenant", "home")
    hass.states.async_set("sun.sun", "above_horizon")
    await _setup_entry(hass)

    await _bedtime(hass, "on")

    assert panel_state(hass) == AlarmControlPanelState.ARMED_NIGHT


async def test_sunrise_ignored_while_sensor_on(hass: HomeAssistant, mock_notify: Any) -> None:
    hass.states.async_set("person.tenant", "home")
    hass.states.async_set("sun.sun", "below_horizon")
    hass.states.async_set(BEDTIME, "on", BEDTIME_ATTRS)
    entry = await _setup_entry(hass, {CONF_SUNRISE_TRIGGER: TRIGGER_ON})

    hass.states.async_set("sun.sun", "above_horizon")
    await entry.runtime_data.on_sunrise()

    assert panel_state(hass) == AlarmControlPanelState.ARMED_NIGHT
    last_calc: State | None = hass.states.get("sensor.autoarm_last_calculation")
    assert last_calc is not None
    assert last_calc.attributes["reset_decision"] == "ignore_for_active_time_of_day"


async def test_reset_returns_to_sensor_state(hass: HomeAssistant, mock_notify: Any) -> None:
    hass.states.async_set("person.tenant", "home")
    hass.states.async_set("sun.sun", "above_horizon")
    hass.states.async_set(BEDTIME, "on", BEDTIME_ATTRS)
    await _setup_entry(hass)
    hass.states.async_set(PANEL, "disarmed")
    await hass.async_block_till_done()

    await hass.services.async_call(DOMAIN, "reset_state", blocking=True)

    assert panel_state(hass) == AlarmControlPanelState.ARMED_NIGHT


async def test_time_of_day_is_not_a_calendar_day(hass: HomeAssistant, mock_notify: Any) -> None:
    entry = await _setup_entry(hass)

    assert not await entry.runtime_data.has_diurnal_calendar_event_today()
    assert await entry.runtime_data.sun_trigger_active(sunrise=False)


async def test_sensor_turning_off_with_fixed_end_mode(hass: HomeAssistant, mock_notify: Any) -> None:
    hass.states.async_set("person.tenant", "home")
    hass.states.async_set("sun.sun", "above_horizon")
    hass.states.async_set(BEDTIME, "on", BEDTIME_ATTRS)
    entry = await _setup_entry(hass, {CONF_CALENDAR_ARMED_END_MODE: "armed_vacation"})

    await _bedtime(hass, "off")

    assert panel_state(hass) == AlarmControlPanelState.ARMED_VACATION
    assert entry.runtime_data.last_change.source == ChangeSource.TOD


async def test_sensor_turning_off_by_occupancy_and_sun(hass: HomeAssistant, mock_notify: Any) -> None:
    hass.states.async_set("person.tenant", "home")
    hass.states.async_set("sun.sun", "below_horizon")
    hass.states.async_set(BEDTIME, "on", BEDTIME_ATTRS)
    entry = await _setup_entry(hass, {CONF_CALENDAR_ARMED_END_MODE: "auto_sun", CONF_OCCUPANCY_DEFAULT_NIGHT: "armed_home"})
    armer = entry.runtime_data
    armer.notifier = AsyncMock(spec=Notifier)
    assert panel_state(hass) == AlarmControlPanelState.ARMED_NIGHT

    await _bedtime(hass, "off")

    assert panel_state(hass) == AlarmControlPanelState.ARMED_HOME
    # the reset names the sensor, for the notification
    assert armer.last_change.context["summary"] == "Bedtime"
    armer.notifier.notify.assert_called_once()
    assert armer.notifier.notify.call_args.kwargs["source_name"] == "Bedtime"


async def test_sensor_turning_off_in_manual_mode_restores_previous_state(hass: HomeAssistant, mock_notify: Any) -> None:
    hass.states.async_set("person.tenant", "home")
    hass.states.async_set("sun.sun", "above_horizon")
    hass.states.async_set(BEDTIME, "off", BEDTIME_ATTRS)
    await _setup_entry(hass, {CONF_CALENDAR_ARMED_END_MODE: "manual"})
    assert panel_state(hass) == AlarmControlPanelState.ARMED_HOME

    await _bedtime(hass, "on")
    assert panel_state(hass) == AlarmControlPanelState.ARMED_NIGHT
    await _bedtime(hass, "off")

    assert panel_state(hass) == AlarmControlPanelState.ARMED_HOME


async def test_unavailable_sensor_ends_period(hass: HomeAssistant, mock_notify: Any) -> None:
    hass.states.async_set("person.tenant", "home")
    hass.states.async_set("sun.sun", "above_horizon")
    hass.states.async_set(BEDTIME, "on", BEDTIME_ATTRS)
    entry = await _setup_entry(hass)
    assert panel_state(hass) == AlarmControlPanelState.ARMED_NIGHT

    await _bedtime(hass, "unavailable")

    assert panel_state(hass) == AlarmControlPanelState.ARMED_HOME
    assert entry.runtime_data.active_time_of_day() is None

    # and nothing more to end when it comes back off
    hass.states.async_set(PANEL, "disarmed")
    await _bedtime(hass, "off")
    assert panel_state(hass) == AlarmControlPanelState.DISARMED


async def test_removed_sensor_ends_period(hass: HomeAssistant, mock_notify: Any) -> None:
    hass.states.async_set("person.tenant", "home")
    hass.states.async_set("sun.sun", "above_horizon")
    hass.states.async_set(BEDTIME, "on", BEDTIME_ATTRS)
    await _setup_entry(hass)

    hass.states.async_remove(BEDTIME)
    await hass.async_block_till_done()

    assert panel_state(hass) == AlarmControlPanelState.ARMED_HOME


async def test_second_sensor_takes_over_when_first_ends(hass: HomeAssistant, mock_notify: Any) -> None:
    hass.states.async_set("person.tenant", "home")
    hass.states.async_set("sun.sun", "above_horizon")
    hass.states.async_set(BEDTIME, "on", BEDTIME_ATTRS)
    hass.states.async_set("binary_sensor.evening", "on")
    await _setup_entry(hass, {"time_of_day_armed_home": ["binary_sensor.evening"]})
    assert panel_state(hass) == AlarmControlPanelState.ARMED_NIGHT

    await _bedtime(hass, "off")

    assert panel_state(hass) == AlarmControlPanelState.ARMED_HOME


async def test_sensor_ignored_after_unload(hass: HomeAssistant, mock_notify: Any) -> None:
    hass.states.async_set("person.tenant", "home")
    hass.states.async_set("sun.sun", "above_horizon")
    hass.states.async_set(BEDTIME, "off", BEDTIME_ATTRS)
    entry = await _setup_entry(hass)
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    await _bedtime(hass, "on")

    assert panel_state(hass) == AlarmControlPanelState.ARMED_HOME
