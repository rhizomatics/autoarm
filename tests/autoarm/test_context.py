"""Home Assistant context is carried from whatever caused a change through to the panel, notification and event"""

import datetime as dt
from typing import Any
from unittest.mock import AsyncMock, Mock

import homeassistant.util.dt as dt_util
from homeassistant.components.alarm_control_panel.const import AlarmControlPanelState
from homeassistant.const import CONF_ENTITY_ID
from homeassistant.core import Context, Event, HomeAssistant, ServiceCall, callback
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from conftest import TEST_PANEL
from custom_components.autoarm.autoarming import AlarmArmer
from custom_components.autoarm.calendar_events import TrackedCalendarEvent
from custom_components.autoarm.const import DOMAIN, NO_CAL_EVENT_MODE_AUTO, ChangeSource

USER_ID = "user-1234"


def _capture_changes(hass: HomeAssistant) -> list[Event]:
    events: list[Event] = []
    hass.bus.async_listen(f"{DOMAIN}_change", callback(lambda event: events.append(event)))
    return events


def _capture_notifications(hass: HomeAssistant) -> list[ServiceCall]:
    calls: list[ServiceCall] = []
    hass.services.async_register("notify", "test_service", callback(lambda call: calls.append(call)))
    return calls


def _armer(hass: HomeAssistant, **kwargs: Any) -> AlarmArmer:
    hass.states.async_set(TEST_PANEL, "disarmed")
    return AlarmArmer(
        hass,
        TEST_PANEL,
        notify_enabled=True,
        notify_action="notify.test_service",
        notify_profiles={"backstop": {}},
        **kwargs,
    )


async def test_arm_propagates_given_context(hass: HomeAssistant) -> None:
    changes = _capture_changes(hass)
    notifications = _capture_notifications(hass)
    armer = _armer(hass, use_alarm_service=False)
    context = Context(user_id=USER_ID)

    await armer.arm(AlarmControlPanelState.ARMED_AWAY, source=ChangeSource.BUTTON, context=context)
    await hass.async_block_till_done()

    panel = hass.states.get(TEST_PANEL)
    assert panel is not None
    assert panel.context is context
    assert notifications[0].context is context
    assert changes[0].context is context


async def test_arm_without_context_shares_a_new_one(hass: HomeAssistant) -> None:
    changes = _capture_changes(hass)
    notifications = _capture_notifications(hass)
    armer = _armer(hass, use_alarm_service=False)

    await armer.arm(AlarmControlPanelState.ARMED_AWAY, source=ChangeSource.SUNSET)
    await hass.async_block_till_done()

    panel = hass.states.get(TEST_PANEL)
    assert panel is not None
    assert notifications[0].context is panel.context
    assert changes[0].context is panel.context


async def test_arm_via_alarm_service_propagates_context(hass: HomeAssistant, panel_actions: list[ServiceCall]) -> None:
    changes = _capture_changes(hass)
    armer = _armer(hass, use_alarm_service=True)
    context = Context(user_id=USER_ID)

    await armer.arm(AlarmControlPanelState.ARMED_AWAY, source=ChangeSource.BUTTON, context=context)
    await hass.async_block_till_done()

    assert panel_actions[0].context is context
    assert changes[0].context is context


async def test_button_press_links_back_to_event(hass: HomeAssistant) -> None:
    changes = _capture_changes(hass)
    armer = _armer(hass, buttons={AlarmControlPanelState.ARMED_AWAY: {CONF_ENTITY_ID: ["binary_sensor.button"]}})
    armer.initialize_buttons()
    pressed = Context(user_id=USER_ID)

    hass.states.async_set("binary_sensor.button", "on", context=pressed)
    await hass.async_block_till_done()

    assert changes[0].context.parent_id == pressed.id
    assert changes[0].context.user_id == USER_ID
    armer.shutdown()


async def test_mobile_action_links_back_to_event(hass: HomeAssistant) -> None:
    changes = _capture_changes(hass)
    armer = _armer(hass)
    armer.initialize_integration()
    tapped = Context(user_id=USER_ID)

    hass.bus.async_fire("mobile_app_notification_action", {"action": "ALARM_PANEL_AWAY"}, context=tapped)
    await hass.async_block_till_done()

    assert changes[0].context.parent_id == tapped.id
    assert changes[0].context.user_id == USER_ID
    armer.shutdown()


async def test_delayed_arm_keeps_context(hass: HomeAssistant) -> None:
    changes = _capture_changes(hass)
    armer = _armer(hass)
    context = Context(user_id=USER_ID)

    armer.schedule_state(
        dt_util.now() + dt.timedelta(seconds=1),
        AlarmControlPanelState.ARMED_AWAY,
        intervention=None,
        source=ChangeSource.BUTTON,
        context=context,
    )
    async_fire_time_changed(hass, dt_util.utcnow() + dt.timedelta(seconds=2))
    await hass.async_block_till_done()

    assert changes[0].context is context
    armer.shutdown()


async def test_reset_propagates_context(hass: HomeAssistant) -> None:
    changes = _capture_changes(hass)
    armer = _armer(hass)
    hass.states.async_set("sun.sun", "above_horizon")
    await armer.initialize_logic()
    hass.states.async_set(TEST_PANEL, "pending")
    context = Context(user_id=USER_ID)

    await armer.reset_armed_state(source=ChangeSource.ACTION, context=context)
    await hass.async_block_till_done()

    assert changes[0].context is context


async def test_calendar_event_end_shares_context_for_pending_and_reset(hass: HomeAssistant) -> None:
    armer = AsyncMock(spec=AlarmArmer)
    armer.has_active_calendar_event = Mock(return_value=False)
    tracked = Mock(spec=TrackedCalendarEvent, armer=armer, no_event_mode=NO_CAL_EVENT_MODE_AUTO)
    tracked.id = tracked.calendar_id = "calendar.test"

    await TrackedCalendarEvent.on_calendar_event_end(tracked, dt_util.now())

    context = armer.pending_state.call_args.kwargs["context"]
    assert isinstance(context, Context)
    assert armer.reset_armed_state.call_args.kwargs["context"] is context
