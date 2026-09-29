import asyncio
import datetime as dt
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import homeassistant.util.dt as dt_util
from homeassistant.components.alarm_control_panel.const import AlarmControlPanelState
from homeassistant.components.calendar import CalendarEntity
from homeassistant.core import HomeAssistant

from conftest import TEST_PANEL
from custom_components.autoarm.autoarming import AlarmArmer, Intervention
from custom_components.autoarm.const import TRIGGER_OFF, ChangeSource
from custom_components.autoarm.notifier import Notifier

if TYPE_CHECKING:
    from custom_components.autoarm.calendar_events import TrackedCalendarEvent


async def test_direct_arm_preserves_panel_attributes(hass: HomeAssistant) -> None:
    hass.states.async_set(entity_id=TEST_PANEL, new_state="disarmed", attributes={"icon": "mdi:alarm-panel"})
    autoarmer = AlarmArmer(hass, TEST_PANEL, use_alarm_service=False)
    await autoarmer.arm(AlarmControlPanelState.ARMED_VACATION)
    panel = hass.states.get(TEST_PANEL)
    assert panel is not None
    assert panel.attributes.get("icon") == "mdi:alarm-panel"


async def test_pending_round_trip_is_never_notified(hass: HomeAssistant) -> None:
    """A pending state is internal bookkeeping - it, and any no-op round trip through it, stay silent.

    Uses sunrise rather than calendar as the source, since calendar-sourced notifications are
    coalesced over a grace period (see test_calendar_notification_coalescing) - unrelated here.
    """
    hass.states.async_set(entity_id=TEST_PANEL, new_state="armed_night")
    autoarmer = AlarmArmer(hass, TEST_PANEL, use_alarm_service=False)
    autoarmer.notifier = AsyncMock(spec=Notifier)

    await autoarmer.pending_state(source=ChangeSource.SUNRISE)
    autoarmer.notifier.notify.assert_not_called()

    # recomputes the same state - a no-op from the user's perspective
    await autoarmer.arm(AlarmControlPanelState.ARMED_NIGHT, source=ChangeSource.SUNRISE)
    autoarmer.notifier.notify.assert_not_called()

    # a genuine change after pending is reported against the state before pending, not "pending"
    await autoarmer.pending_state(source=ChangeSource.SUNRISE)
    await autoarmer.arm(AlarmControlPanelState.DISARMED, source=ChangeSource.SUNRISE)
    autoarmer.notifier.notify.assert_called_once_with(
        source=ChangeSource.SUNRISE,
        from_state=AlarmControlPanelState.ARMED_NIGHT,
        to_state=AlarmControlPanelState.DISARMED,
        context=autoarmer.notifier.notify.call_args.kwargs["context"],
    )


async def test_calendar_notification_coalescing(hass: HomeAssistant) -> None:
    """Calendar changes landing within the grace period, such as one event ending as another starts,

    are coalesced into a single net-change notification rather than two.
    """
    hass.states.async_set(entity_id=TEST_PANEL, new_state="armed_night")
    autoarmer = AlarmArmer(hass, TEST_PANEL, use_alarm_service=False)
    autoarmer.notifier = AsyncMock(spec=Notifier)
    autoarmer.calendar_notify_grace_period = dt.timedelta(milliseconds=50)

    await autoarmer.arm(AlarmControlPanelState.DISARMED, source=ChangeSource.CALENDAR)
    await autoarmer.arm(AlarmControlPanelState.ARMED_HOME, source=ChangeSource.CALENDAR)
    autoarmer.notifier.notify.assert_not_called()

    await asyncio.sleep(0.1)

    autoarmer.notifier.notify.assert_called_once_with(
        source=ChangeSource.CALENDAR,
        from_state=AlarmControlPanelState.ARMED_NIGHT,
        to_state=AlarmControlPanelState.ARMED_HOME,
        context=autoarmer.notifier.notify.call_args.kwargs["context"],
    )
    autoarmer.shutdown()


async def test_calendar_notification_coalescing_net_noop_is_silent(hass: HomeAssistant) -> None:
    """If the coalesced run ends up back where it started, no notification is sent at all."""
    hass.states.async_set(entity_id=TEST_PANEL, new_state="armed_night")
    autoarmer = AlarmArmer(hass, TEST_PANEL, use_alarm_service=False)
    autoarmer.notifier = AsyncMock(spec=Notifier)
    autoarmer.calendar_notify_grace_period = dt.timedelta(milliseconds=50)

    await autoarmer.arm(AlarmControlPanelState.DISARMED, source=ChangeSource.CALENDAR)
    await autoarmer.arm(AlarmControlPanelState.ARMED_NIGHT, source=ChangeSource.CALENDAR)

    await asyncio.sleep(0.1)

    autoarmer.notifier.notify.assert_not_called()
    autoarmer.shutdown()


async def test_vacation_day_occupied(autoarmer: AlarmArmer, day: None, occupied: None) -> None:
    await autoarmer.arm(AlarmControlPanelState.ARMED_VACATION)
    assert autoarmer.determine_state() == AlarmControlPanelState.ARMED_VACATION


async def test_vacation_day_unoccupied(autoarmer: AlarmArmer, day: None, unoccupied: None) -> None:
    await autoarmer.arm(AlarmControlPanelState.ARMED_VACATION)
    assert autoarmer.determine_state() == AlarmControlPanelState.ARMED_VACATION


def test_occupied_day_armed_default(autoarmer: AlarmArmer, day: None, occupied: None) -> None:
    autoarmer.occupied_defaults["day"] = AlarmControlPanelState.ARMED_HOME
    assert autoarmer.determine_state() == AlarmControlPanelState.ARMED_HOME


def test_occupied_day_disarmed_default(autoarmer: AlarmArmer, day: None, occupied: None) -> None:
    autoarmer.occupied_defaults["day"] = AlarmControlPanelState.DISARMED
    assert autoarmer.determine_state() == AlarmControlPanelState.DISARMED


def test_occupied_night(autoarmer: AlarmArmer, night: None, occupied: None) -> None:
    assert autoarmer.determine_state() == AlarmControlPanelState.ARMED_NIGHT


def test_unoccupied_day(autoarmer: AlarmArmer, day: None, unoccupied: None) -> None:
    assert autoarmer.determine_state() == AlarmControlPanelState.ARMED_AWAY


def test_unoccupied_night(autoarmer: AlarmArmer, night: None, unoccupied: None) -> None:
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


async def test_on_sunset_with_earliest_constraint(
    autoarmer: AlarmArmer,
    hass: HomeAssistant,
) -> None:
    """Sunset fires but earliest constraint hasn't been met — deferred arm later fires."""
    await autoarmer.arm(AlarmControlPanelState.PENDING)
    await hass.async_block_till_done()
    autoarmer.sunset_earliest = (dt_util.now() + dt.timedelta(seconds=2)).time()
    autoarmer.interventions = []
    await autoarmer.on_sunset()
    await hass.async_block_till_done()
    await asyncio.sleep(2)
    assert autoarmer.armed_state() != AlarmControlPanelState.PENDING


async def test_on_sunset_with_earliest_constraint_already_met(
    autoarmer: AlarmArmer,
    hass: HomeAssistant,
) -> None:
    """Sunset fires and earliest constraint is already past — arms immediately."""
    await autoarmer.arm(AlarmControlPanelState.PENDING)
    await hass.async_block_till_done()
    autoarmer.sunset_earliest = (dt_util.now() - dt.timedelta(seconds=1)).time()
    autoarmer.interventions = []
    await autoarmer.on_sunset()
    assert autoarmer.armed_state() != AlarmControlPanelState.PENDING


async def test_on_sunrise(autoarmer: AlarmArmer) -> None:
    await autoarmer.arm(AlarmControlPanelState.PENDING)
    assert autoarmer.armed_state() == AlarmControlPanelState.PENDING
    await autoarmer.on_sunrise()
    assert autoarmer.armed_state() != AlarmControlPanelState.PENDING


async def test_on_sunrise_ignored_when_sunrise_trigger_off(autoarmer: AlarmArmer) -> None:
    autoarmer.sunrise_trigger = TRIGGER_OFF
    await autoarmer.arm(AlarmControlPanelState.PENDING)
    await autoarmer.on_sunrise()
    assert autoarmer.armed_state() == AlarmControlPanelState.PENDING


async def test_on_sunset_ignored_when_sunset_trigger_off(autoarmer: AlarmArmer) -> None:
    autoarmer.sunset_trigger = TRIGGER_OFF
    await autoarmer.arm(AlarmControlPanelState.PENDING)
    await autoarmer.on_sunset()
    assert autoarmer.armed_state() == AlarmControlPanelState.PENDING


async def test_sun_triggers_are_independent(autoarmer: AlarmArmer) -> None:
    autoarmer.sunset_trigger = TRIGGER_OFF
    await autoarmer.arm(AlarmControlPanelState.PENDING)
    await autoarmer.on_sunrise()
    assert autoarmer.armed_state() != AlarmControlPanelState.PENDING


async def test_leaving_ignored_when_unoccupied_trigger_off(hass: HomeAssistant, autoarmer: AlarmArmer, day: None) -> None:
    hass.states.async_set("person.tester_bob", "home")
    await hass.async_block_till_done()
    settled = autoarmer.armed_state()
    autoarmer.unoccupied_trigger = False

    hass.states.async_set("person.tester_bob", "not_home")
    await hass.async_block_till_done()

    assert autoarmer.armed_state() == settled
    assert settled != AlarmControlPanelState.ARMED_AWAY


async def test_arriving_ignored_when_occupied_trigger_off(hass: HomeAssistant, autoarmer: AlarmArmer, day: None) -> None:
    hass.states.async_set("person.tester_bob", "not_home")
    await hass.async_block_till_done()
    autoarmer.interventions = []
    await autoarmer.reset_armed_state(source=ChangeSource.OCCUPANCY)
    assert autoarmer.armed_state() == AlarmControlPanelState.ARMED_AWAY
    autoarmer.occupied_trigger = False

    hass.states.async_set("person.tester_bob", "home")
    await hass.async_block_till_done()

    assert autoarmer.armed_state() == AlarmControlPanelState.ARMED_AWAY


async def test_on_sunrise_with_earliest_active_no_interventions(
    autoarmer: AlarmArmer,
    hass: HomeAssistant,
) -> None:
    """Sunrise fires but earliest constraint hasn't been met yet — deferred arm later fires."""
    await autoarmer.arm(AlarmControlPanelState.PENDING)
    await hass.async_block_till_done()
    autoarmer.sunrise_earliest = (dt_util.now() + dt.timedelta(seconds=2)).time()
    autoarmer.interventions = []
    await autoarmer.on_sunrise()
    await hass.async_block_till_done()
    # wait for delayed_reset
    await asyncio.sleep(2)
    assert autoarmer.armed_state() != AlarmControlPanelState.PENDING


async def test_on_sunrise_with_intervention_before_earliest(
    autoarmer: AlarmArmer,
    hass: HomeAssistant,
) -> None:
    """Deferred sunrise arm is cancelled by manual intervention."""
    await autoarmer.arm(AlarmControlPanelState.ARMED_AWAY)
    autoarmer.sunrise_earliest = (dt_util.now() + dt.timedelta(seconds=2)).time()
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


async def test_startup_defers_to_sunset_earliest(hass: HomeAssistant, night: None) -> None:
    """Integration startup during nighttime before sunset_earliest defers the arm."""
    hass.states.async_set(TEST_PANEL, "disarmed")
    await hass.async_block_till_done()
    future_earliest = (dt_util.now() + dt.timedelta(seconds=2)).time()
    autoarmer = AlarmArmer(
        hass,
        TEST_PANEL,
        occupancy={"entity_id": ["person.tester_bob"]},
        sunset_earliest=future_earliest,
    )
    # Override so the defer branch is taken regardless of the actual clock
    # hour (test may run in the AM, when _has_sunset_passed_today = False).
    with patch.object(autoarmer, "_has_sunset_passed_today", return_value=True):
        await autoarmer.initialize()
    # Should not have armed immediately — deferred to sunset_earliest
    assert autoarmer.armed_state() == AlarmControlPanelState.DISARMED
    await asyncio.sleep(2)
    # After the deferred time, should have armed
    assert autoarmer.armed_state() != AlarmControlPanelState.DISARMED
    autoarmer.shutdown()


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
        calendar_config={"calendars": [{"entity_id": "calendar.testing_calendar", "state_patterns": {"disarmed": ".*"}}]},
    )
    await autoarmer.initialize()
    cal_event: TrackedCalendarEvent | None = autoarmer.active_calendar_event()
    assert cal_event is not None
    assert cal_event.event.summary == "Testing Day"

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


async def test_each_person_change_reevaluates(hass: HomeAssistant, day: None) -> None:
    """Transitions can depend on who in particular is home, so every arrival or departure re-evaluates."""
    hass.states.async_set("person.alice", "home")
    hass.states.async_set("person.bob", "home")
    armer = AlarmArmer(hass, TEST_PANEL, occupancy={"entity_id": ["person.alice", "person.bob"]})
    armer.initialize_occupancy()

    with patch.object(armer, "reset_armed_state", new=AsyncMock()) as reset:
        hass.states.async_set("person.bob", "not_home")
        await hass.async_block_till_done()
        hass.states.async_set("person.alice", "not_home")
        await hass.async_block_till_done()

        assert reset.call_count == 2
    armer.shutdown()
