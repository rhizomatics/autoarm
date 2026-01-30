import asyncio
import datetime as dt

import homeassistant.util.dt as dt_util
import pytest
from homeassistant.components.calendar import EVENT_END, EVENT_START, CalendarEntity, CalendarEvent
from homeassistant.const import CONF_ENTITY_ID
from homeassistant.helpers.entity_platform import EntityPlatform

from custom_components.autoarm.autoarming import AlarmArmer
from custom_components.autoarm.calendar import TrackedCalendar, TrackedCalendarEvent
from custom_components.autoarm.const import (
    CONF_CALENDAR_EVENT_STATES,
    CONF_CALENDAR_POLL_INTERVAL,
    NO_CAL_EVENT_MODE_AUTO,
    AlarmControlPanelState,
    ChangeSource,
)


@pytest.fixture
async def simple_tracked_calendar(
    local_calendar: CalendarEntity, calendar_platform: EntityPlatform, mock_armer_real_hass: AlarmArmer
) -> TrackedCalendar:
    uut = TrackedCalendar(
        mock_armer_real_hass.hass,
        {
            CONF_ENTITY_ID: local_calendar.entity_id,
            CONF_CALENDAR_POLL_INTERVAL: 10,
            CONF_CALENDAR_EVENT_STATES: {"armed_away": ["Away"], "armed_vacation": ["Holiday.*"]},
        },
        no_event_mode=NO_CAL_EVENT_MODE_AUTO,
        armer=mock_armer_real_hass,
        app_health_tracker=mock_armer_real_hass.app_health_tracker,
    )
    await uut.initialize(calendar_platform)
    return uut


@pytest.fixture
async def calendar_with_holiday_event(
    simple_tracked_calendar: TrackedCalendar, local_calendar: CalendarEntity
) -> TrackedCalendar:
    await local_calendar.async_create_event(
        dtstart=dt_util.now() - dt.timedelta(minutes=2),
        dtend=dt_util.now() + dt.timedelta(minutes=2),
        summary="Holidays in Bahamas!!",
    )
    await simple_tracked_calendar.on_timed_poll(dt_util.now())
    return simple_tracked_calendar


async def test_calendar_finds_alarm_states(simple_tracked_calendar: TrackedCalendar, local_calendar: CalendarEntity) -> None:
    await local_calendar.async_create_event(
        dtstart=dt_util.now() - dt.timedelta(minutes=2),
        dtend=dt_util.now() + dt.timedelta(minutes=2),
        description="Something is happening and ARMED_AWAY should be set",
    )
    await simple_tracked_calendar.on_timed_poll(dt_util.now())
    assert simple_tracked_calendar.has_active_event()
    simple_tracked_calendar.armer.arm.assert_called_once_with(
        arming_state=AlarmControlPanelState.ARMED_AWAY,  # type: ignore
        source=ChangeSource.CALENDAR,
    )  # type: ignore


async def test_calendar_bare_lifecycle(simple_tracked_calendar: TrackedCalendar) -> None:
    assert simple_tracked_calendar.enabled
    await simple_tracked_calendar.match_events()
    assert not simple_tracked_calendar.has_active_event()
    await simple_tracked_calendar.prune_events()
    simple_tracked_calendar.shutdown()
    assert not simple_tracked_calendar.enabled


async def test_calendar_tracks_event(
    calendar_with_holiday_event: TrackedCalendar,
    mock_armer_real_hass: AlarmArmer,
) -> None:

    assert calendar_with_holiday_event.has_active_event()
    assert len(calendar_with_holiday_event.tracked_events) == 1
    tracked_event: TrackedCalendarEvent = next(i for i in calendar_with_holiday_event.tracked_events.values())
    assert tracked_event is not None
    assert tracked_event.event.summary == "Holidays in Bahamas!!"
    await calendar_with_holiday_event.prune_events()
    assert calendar_with_holiday_event.has_active_event()
    await calendar_with_holiday_event.match_events()
    mock_armer_real_hass.arm.assert_called_once_with(  # type: ignore
        arming_state=AlarmControlPanelState.ARMED_VACATION,
        source=ChangeSource.CALENDAR,
    )  # type: ignore
    calendar_with_holiday_event.shutdown()
    assert not calendar_with_holiday_event.has_active_event()


async def test_calendar_prunes_events(
    simple_tracked_calendar: TrackedCalendar,
    local_calendar: CalendarEntity,
) -> None:

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
    await simple_tracked_calendar.on_timed_poll(dt_util.now())
    assert simple_tracked_calendar.enabled
    await simple_tracked_calendar.prune_events()
    assert len(simple_tracked_calendar.tracked_events) == 2
    await asyncio.sleep(2)
    await simple_tracked_calendar.prune_events()
    assert len(simple_tracked_calendar.tracked_events) == 1
    assert next(i for i in simple_tracked_calendar.tracked_events.values()).event.summary == "Holidays in Bahamas!!"


async def test_calendar_follows_event_name_change_no_longer_in_scope(
    calendar_with_holiday_event: TrackedCalendar,
    local_calendar: CalendarEntity,
) -> None:

    existing_event: CalendarEvent = calendar_with_holiday_event.active_events()[0]  # type: ignore
    await local_calendar.async_update_event(
        existing_event.uid,  # type: ignore
        {
            EVENT_START: existing_event.start_datetime_local,
            EVENT_END: existing_event.end_datetime_local,
            "summary": "Cancelled holidays in Bahamas!!",
        },
    )
    await calendar_with_holiday_event.on_timed_poll(dt_util.now())
    assert not calendar_with_holiday_event.has_active_event()


async def test_calendar_follows_event_date_change_out_of_window(
    calendar_with_holiday_event: TrackedCalendar,
    local_calendar: CalendarEntity,
) -> None:

    existing_event: CalendarEvent = calendar_with_holiday_event.active_events()[0]  # type: ignore
    await local_calendar.async_update_event(
        existing_event.uid,  # type: ignore
        {
            EVENT_START: dt_util.now() + dt.timedelta(minutes=20),
            EVENT_END: dt_util.now() + dt.timedelta(minutes=25),
            "summary": "Holiday somewhere else",
        },
    )
    await calendar_with_holiday_event.on_timed_poll(dt_util.now())
    assert not calendar_with_holiday_event.has_active_event()
    assert not calendar_with_holiday_event.tracked_events


async def test_calendar_follows_event_date_change_within_window(
    calendar_with_holiday_event: TrackedCalendar,
    local_calendar: CalendarEntity,
) -> None:

    existing_event: CalendarEvent = calendar_with_holiday_event.active_events()[0]  # type: ignore
    await local_calendar.async_update_event(
        existing_event.uid,  # type: ignore
        {
            EVENT_START: dt_util.now() - dt.timedelta(minutes=1),
            EVENT_END: dt_util.now() + dt.timedelta(minutes=3),
            "summary": "Holiday somewhere else",
        },
    )
    await calendar_with_holiday_event.on_timed_poll(dt_util.now())
    tracker = next(iter(calendar_with_holiday_event.tracked_events.values()))
    assert tracker.event.summary == "Holiday somewhere else"
    assert calendar_with_holiday_event.has_active_event()


async def test_calendar_terminates_early(
    calendar_with_holiday_event: TrackedCalendar,
    local_calendar: CalendarEntity,
) -> None:

    existing_event: CalendarEvent = calendar_with_holiday_event.active_events()[0]  # type: ignore
    await local_calendar.async_update_event(
        existing_event.uid,  # type: ignore
        {
            EVENT_START: dt_util.now() - dt.timedelta(minutes=2),
            EVENT_END: dt_util.now() - dt.timedelta(seconds=5),
            "summary": existing_event.summary,
        },
    )
    await calendar_with_holiday_event.on_timed_poll(dt_util.now())
    assert not calendar_with_holiday_event.has_active_event()


async def test_calendar_follows_event_deleted(
    calendar_with_holiday_event: TrackedCalendar,
    local_calendar: CalendarEntity,
) -> None:
    uid: str = calendar_with_holiday_event.active_events()[0].uid  # type: ignore
    await local_calendar.async_delete_event(uid)
    await calendar_with_holiday_event.on_timed_poll(dt_util.now())
    assert not calendar_with_holiday_event.has_active_event()
