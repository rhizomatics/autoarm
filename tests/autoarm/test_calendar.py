
import asyncio
import datetime as dt
from unittest.mock import ANY

import homeassistant.util.dt as dt_util
from homeassistant.components.calendar import CalendarEntity
from homeassistant.const import CONF_ENTITY_ID
from homeassistant.helpers.entity_platform import EntityPlatform

from custom_components.autoarm.autoarming import AlarmArmer
from custom_components.autoarm.calendar import TrackedCalendar, TrackedCalendarEvent
from custom_components.autoarm.const import (
    CONF_CALENDAR_EVENT_STATES,
    CONF_CALENDAR_POLL_INTERVAL,
)


async def test_calendar_bare_lifecycle(local_calendar: CalendarEntity,
                              calendar_platform: EntityPlatform,
                              mock_armer_real_hass: AlarmArmer) -> None:

    uut = TrackedCalendar({CONF_ENTITY_ID: local_calendar.entity_id,
                CONF_CALENDAR_POLL_INTERVAL: 10,
                CONF_CALENDAR_EVENT_STATES: {"armed_away": [
                    "Away"], "armed_vacation": ["Holiday.*"]}
                }, mock_armer_real_hass)

    await uut.initialize(calendar_platform)
    assert uut.enabled
    await uut.match_events()
    assert not uut.has_active_event()
    await uut.prune_events()
    uut.shutdown()
    assert not uut.enabled


async def test_calendar_tracks_event(local_calendar: CalendarEntity,
                              calendar_platform: EntityPlatform,
                              mock_armer_real_hass: AlarmArmer) -> None:

    uut = TrackedCalendar({CONF_ENTITY_ID: local_calendar.entity_id,
                CONF_CALENDAR_POLL_INTERVAL: 10,
                CONF_CALENDAR_EVENT_STATES: {"armed_away": [
                    "Away"], "armed_vacation": ["Holiday.*"]}
                }, mock_armer_real_hass)
    await local_calendar.async_create_event(
        dtstart=dt_util.now() - dt.timedelta(minutes=2),
        dtend=dt_util.now() + dt.timedelta(minutes=2),
        summary="Holidays in Bahamas!!",
    )
    await uut.initialize(calendar_platform)
    assert uut.enabled
    assert uut.has_active_event()
    assert len(uut.tracked_events) == 1
    tracked_event: TrackedCalendarEvent = next(i for i in uut.tracked_events.values())
    assert tracked_event is not None
    assert tracked_event.event.summary == "Holidays in Bahamas!!"
    await uut.prune_events()
    assert uut.has_active_event()
    await uut.match_events()
    mock_armer_real_hass.on_calendar_event_start.assert_called_once_with(tracked_event, ANY)  # type: ignore
    uut.shutdown()
    assert not uut.has_active_event()


async def test_calendar_prunes_events(local_calendar: CalendarEntity,
                              calendar_platform: EntityPlatform,
                              mock_armer_real_hass: AlarmArmer) -> None:

    uut = TrackedCalendar({CONF_ENTITY_ID: local_calendar.entity_id,
                CONF_CALENDAR_POLL_INTERVAL: 10,
                CONF_CALENDAR_EVENT_STATES: {"armed_away": [
                    "Away"], "armed_vacation": ["Holiday.*"]}
                }, mock_armer_real_hass)
    await local_calendar.async_create_event(
        dtstart=dt_util.now() - dt.timedelta(minutes=20),
        dtend=dt_util.now() + dt.timedelta(seconds=2),
        summary="Holiday stopover",
    )
    await local_calendar.async_create_event(
        dtstart=dt_util.now() - dt.timedelta(minutes=2),
        dtend=dt_util.now() + dt.timedelta(days=14),
        summary="Holidays in Bahamas!!",
    )
    await uut.initialize(calendar_platform)
    assert uut.enabled
    await uut.prune_events()
    assert len(uut.tracked_events) == 2
    await asyncio.sleep(2)
    await uut.prune_events()
    assert len(uut.tracked_events) == 1
    assert next(i for i in uut.tracked_events.values()).event.summary == "Holidays in Bahamas!!"
