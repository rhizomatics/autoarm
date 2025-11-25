import logging

from homeassistant.components.alarm_control_panel.const import AlarmControlPanelState
from homeassistant.core import State

_LOGGER = logging.getLogger(__name__)


def alarm_state_as_enum(state_str: str | None) -> AlarmControlPanelState | None:
    if state_str is None:
        return None
    try:
        return AlarmControlPanelState(state_str)
    except ValueError as e:
        _LOGGER.warning("AUTOARM Invalid alarm state: %s", e)
        return None


def safe_state(state: State | None) -> str | None:
    try:
        return state.state if state is not None else None
    except Exception as e:
        _LOGGER.debug("AUTOARM Failed to load state %s: %s", state, e)
        return None
