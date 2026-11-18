"""Run the actions chosen in the options whenever the alarm state changes, for example to update a display"""

import logging
from collections.abc import Callable
from typing import Any

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import Context, Event, EventStateChangedData, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.script import SCRIPT_MODE_QUEUED, Script, async_validate_actions_config

from .compat import vol
from .const import DOMAIN
from .helpers import AppHealthTracker, friendly_state

_LOGGER = logging.getLogger(__name__)


async def async_validate_state_actions(hass: HomeAssistant, actions: Any) -> list[dict[str, Any]]:
    """Actions as the action selector gives them, checked and ready to run, raising vol.Invalid or HomeAssistantError"""
    return await async_validate_actions_config(hass, cv.SCRIPT_SCHEMA(actions))


async def async_track_state_action(
    hass: HomeAssistant, alarm_panel: str, actions: list[dict[str, Any]], app_health_tracker: AppHealthTracker
) -> Callable[[], None] | None:
    """Run the actions on each change of alarm state, with from_state, to_state, friendly_state and alarm_panel to use"""
    try:
        sequence = await async_validate_state_actions(hass, actions)
    except (vol.Invalid, HomeAssistantError) as e:
        app_health_tracker.record_initialization_error("state_action")
        _LOGGER.error("AUTOARM State change action is invalid, and won't be run: %s", e)
        return None
    # queued so that a display shows the changes in the order they happened
    script = Script(hass, sequence, "Auto Arm state change action", DOMAIN, script_mode=SCRIPT_MODE_QUEUED, logger=_LOGGER)

    async def on_panel_change(event: Event[EventStateChangedData]) -> None:
        old = event.data["old_state"]
        new = event.data["new_state"]
        if new is None or new.state in (STATE_UNAVAILABLE, STATE_UNKNOWN) or (old is not None and old.state == new.state):
            return
        _LOGGER.debug("AUTOARM Running state change action for %s-->%s", old.state if old else None, new.state)
        try:
            await script.async_run(
                {
                    "alarm_panel": alarm_panel,
                    "from_state": old.state if old else None,
                    "to_state": new.state,
                    "friendly_state": friendly_state(new.state),
                },
                # linked to the change, but not run as whoever made it, the same as an automation
                context=Context(parent_id=event.context.id),
            )
        except Exception as e:
            app_health_tracker.record_runtime_error()
            _LOGGER.warning("AUTOARM State change action failed: %s", e)

    return async_track_state_change_event(hass, [alarm_panel], on_panel_change)
