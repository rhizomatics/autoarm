import asyncio
import datetime as dt
from typing import TYPE_CHECKING

import homeassistant.util.dt as dt_util
from homeassistant.components.alarm_control_panel.const import AlarmControlPanelState
from homeassistant.const import CONF_ENTITY_ID
from homeassistant.setup import async_setup_component

from custom_components.autoarm.const import (
    CONF_ALARM_PANEL,
    CONF_AUTO_ARM,
    CONF_CALENDAR_CONTROL,
    CONF_CALENDAR_EVENT_STATES,
    CONF_CALENDAR_NO_EVENT,
    CONF_CALENDAR_POLL_INTERVAL,
    CONF_CALENDARS,
    CONF_OCCUPANTS,
    DOMAIN,
)

if TYPE_CHECKING:
    from homeassistant.components.calendar import CalendarEvent
    from homeassistant.helpers.typing import ConfigType
from homeassistant.components.calendar import CalendarEntity
from homeassistant.core import HomeAssistant, State

CONFIG = {
    DOMAIN: {
        CONF_ALARM_PANEL: "alarm_panel.testing",
        CONF_AUTO_ARM: True,
        CONF_OCCUPANTS: ["person.house_owner", "person.tenant"],
        CONF_CALENDAR_CONTROL: {
            CONF_CALENDAR_NO_EVENT: "auto",
            CONF_CALENDARS: [
                {
                    CONF_ENTITY_ID: "calendar.testing_calendar",
                    CONF_CALENDAR_POLL_INTERVAL: 10,
                    CONF_CALENDAR_EVENT_STATES: {"armed_away": ["Away"], "armed_vacation": ["Holiday.*"]},
                }
            ],
        },
    }
}


def panel_state(hass: HomeAssistant) -> AlarmControlPanelState | None:
    state = hass.states.get("alarm_panel.testing")
    if state is None:
        return None
    if state.state in AlarmControlPanelState:
        return AlarmControlPanelState(state.state)
    return None


async def test_fragile_calendar_fixture(local_calendar: CalendarEntity, hass: HomeAssistant) -> None:
    # not testing autoarm, just making sure can setup test calendars ok

    await hass.services.async_call(
        "calendar",
        "create_event",
        {
            "start_date_time": "2020-10-10T18:00:00+00:00",
            "end_date_time": "2020-10-10T23:00:00+00:00",
            "summary": "Arming Party",
            "location": "Test Location",
        },
        target={"entity_id": "calendar.testing_calendar"},
        blocking=True,
    )
    await hass.async_block_till_done()

    events: list[CalendarEvent] = await local_calendar.async_get_events(
        hass=hass,
        start_date=dt.datetime(2020, 10, 10, 9, 0, 0, tzinfo=dt.UTC),
        end_date=dt.datetime(2020, 10, 10, 23, 59, 59, tzinfo=dt.UTC),
    )
    assert len(events) == 1
    assert events[0].summary == "Arming Party"


async def test_calendar_live_event(local_calendar: CalendarEntity, hass: HomeAssistant) -> None:
    start_of_day = dt_util.start_of_local_day()
    end_of_day = start_of_day + dt.timedelta(days=1) - dt.timedelta(seconds=1)
    await local_calendar.async_create_event(
        dtstart=start_of_day,
        dtend=end_of_day,
        summary="Holidays in Bahamas!!",
    )
    hass.states.async_set("alarm_panel.testing", "armed_away")
    assert await async_setup_component(hass, "autoarm", CONFIG)
    await hass.async_block_till_done()

    assert panel_state(hass) == AlarmControlPanelState.ARMED_VACATION
    last_event: State | None = hass.states.get("autoarm.last_calendar_event")
    assert last_event is not None
    assert last_event.attributes["calendar"] == "calendar.testing_calendar"
    assert last_event.attributes["summary"] == "Holidays in Bahamas!!"


async def test_calendar_dead_events(local_calendar: CalendarEntity, hass: HomeAssistant) -> None:

    await local_calendar.async_create_event(
        dtstart=dt_util.now() - dt.timedelta(hours=1),
        dtend=dt_util.now() - dt.timedelta(seconds=1),
        summary="Holidays in Bahamas!!",
    )
    await local_calendar.async_create_event(
        dtstart=dt_util.now() + dt.timedelta(minutes=2),
        dtend=dt_util.now() + dt.timedelta(minutes=10),
        summary="Holidays in Bahamas!!",
    )
    hass.states.async_set("alarm_panel.testing", "armed_away")
    assert await async_setup_component(hass, "autoarm", CONFIG)
    await hass.async_block_till_done()

    assert panel_state(hass) == AlarmControlPanelState.ARMED_AWAY


async def test_calendar_near_future_event(local_calendar: CalendarEntity, hass: HomeAssistant) -> None:
    start = dt_util.now() + dt.timedelta(seconds=2)
    end = start + dt.timedelta(days=1) - dt.timedelta(seconds=1)
    await local_calendar.async_create_event(
        dtstart=start,
        dtend=end,
        summary="Holidays in Bahamas!!",
    )
    hass.states.async_set("alarm_panel.testing", "armed_away")
    assert await async_setup_component(hass, "autoarm", CONFIG)
    await hass.async_block_till_done()
    await asyncio.sleep(2)

    assert panel_state(hass) == AlarmControlPanelState.ARMED_VACATION


async def test_calendar_event_ending_shortly(local_calendar: CalendarEntity, hass: HomeAssistant) -> None:
    hass.states.async_set("person.tenant", "home", {"friendly_name": "Jill"})

    start: dt.datetime = dt_util.start_of_local_day()
    end: dt.datetime = dt_util.now() + dt.timedelta(seconds=2)
    await local_calendar.async_create_event(
        dtstart=start,
        dtend=end,
        summary="Holidays in Bahamas!!",
    )
    hass.states.async_set("alarm_panel.testing", "armed_away")
    assert await async_setup_component(hass, "autoarm", CONFIG)
    await hass.async_block_till_done()
    assert panel_state(hass) == AlarmControlPanelState.ARMED_VACATION
    await asyncio.sleep(3)

    assert panel_state(hass) in (AlarmControlPanelState.ARMED_HOME, AlarmControlPanelState.ARMED_NIGHT)


async def test_calendar_event_ending_fixed_mode(local_calendar: CalendarEntity, hass: HomeAssistant) -> None:
    hass.states.async_set("person.tenant", "home", {"friendly_name": "Jill"})

    start = dt_util.start_of_local_day()
    end = dt_util.now() + dt.timedelta(seconds=2)
    await local_calendar.async_create_event(
        dtstart=start,
        dtend=end,
        summary="Holidays in Bahamas!!",
    )
    hass.states.async_set("alarm_panel.testing", "armed_away")
    local_config: ConfigType = CONFIG.copy()
    local_config[DOMAIN][CONF_CALENDAR_CONTROL][CONF_CALENDAR_NO_EVENT] = "disarmed"
    assert await async_setup_component(hass, "autoarm", local_config)
    await hass.async_block_till_done()
    assert panel_state(hass) == AlarmControlPanelState.ARMED_VACATION
    await asyncio.sleep(3)

    assert panel_state(hass) == AlarmControlPanelState.DISARMED


async def test_calendar_event_ending_manual_mode(local_calendar: CalendarEntity, hass: HomeAssistant) -> None:
    hass.states.async_set("person.tenant", "home", {"friendly_name": "Jill"})

    start: dt.datetime = dt_util.start_of_local_day()
    end: dt.datetime = dt_util.now() + dt.timedelta(seconds=2)
    await local_calendar.async_create_event(
        dtstart=start,
        dtend=end,
        summary="Holidays in Bahamas!!",
    )
    hass.states.async_set("alarm_panel.testing", "armed_away")
    local_config: ConfigType = CONFIG.copy()
    local_config[DOMAIN][CONF_CALENDAR_CONTROL][CONF_CALENDAR_NO_EVENT] = "manual"
    assert await async_setup_component(hass, "autoarm", local_config)
    await hass.async_block_till_done()
    assert panel_state(hass) == AlarmControlPanelState.ARMED_VACATION
    await asyncio.sleep(3)

    assert panel_state(hass) == AlarmControlPanelState.ARMED_AWAY


async def test_calendar_multiple_calendars(local_calendar: CalendarEntity, hass: HomeAssistant) -> None:
    start_of_day: dt.datetime = dt_util.start_of_local_day()
    end_of_day: dt.datetime = start_of_day + dt.timedelta(days=1) - dt.timedelta(seconds=1)
    await local_calendar.async_create_event(
        dtstart=start_of_day,
        dtend=end_of_day,
        summary="Holidays in Bahamas!!",
    )
    local_config: ConfigType = CONFIG.copy()
    local_config[DOMAIN][CONF_CALENDAR_CONTROL][CONF_CALENDARS].append({CONF_ENTITY_ID: "calendar.google"})
    local_config[DOMAIN][CONF_CALENDAR_CONTROL][CONF_CALENDARS].append({CONF_ENTITY_ID: "calendar.workday"})

    hass.states.async_set("alarm_panel.testing", "armed_away")
    assert await async_setup_component(hass, "autoarm", CONFIG)
    await hass.async_block_till_done()

    assert panel_state(hass) == AlarmControlPanelState.ARMED_VACATION
