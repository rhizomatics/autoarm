import datetime as dt
import logging
from typing import Any

import homeassistant.util.dt as dt_util
from homeassistant.auth import HomeAssistant
from homeassistant.components.alarm_control_panel.const import AlarmControlPanelState
from homeassistant.core import State

from .const import DOMAIN

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


class Limiter:
    """Rate limiting tracker"""

    def __init__(self, window: dt.timedelta, max_calls: int = 4) -> None:
        self.calls: list[dt.datetime] = []
        self.window: dt.timedelta = window
        self.max_calls: int = max_calls
        _LOGGER.debug(
            "AUTOARM Rate limiter initialized with window %s and max_calls %s",
            window,
            max_calls,
        )

    def triggered(self) -> bool:
        """Register a call and check if window based rate limit triggered"""
        cut_off: dt.datetime = dt_util.now() - self.window
        self.calls.append(dt_util.now())
        in_scope = 0

        for call in self.calls[:]:
            if call >= cut_off:
                in_scope += 1
            else:
                self.calls.remove(call)

        return in_scope > self.max_calls


def deobjectify(obj: object) -> dict[Any, Any] | str | int | float | bool | None:
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, (dt.datetime, dt.time, dt.date)):
        return obj.isoformat()
    as_dict = getattr(obj, "as_dict", None)
    if as_dict is None:
        return str(obj)
    return as_dict()


class AppHealthTracker:
    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self.initialization_errors: dict[str, int] = {}
        self.failures = 0

    def app_initialized(self) -> None:
        self.hass.states.async_set(
            f"binary_sensor.{DOMAIN}_initialized",
            "valid" if not self.initialization_errors else "invalid",
            attributes=self.initialization_errors,
        )
        self.hass.states.async_set(f"sensor.{DOMAIN}_failures", str(self.failures))

    def record_initialization_error(self, stage: str) -> None:
        self.initialization_errors.setdefault(stage, 0)
        self.initialization_errors[stage] += 1
        self.failures += 1
        self.hass.states.async_set(
            f"sensor.{DOMAIN}_failures", str(self.failures), attributes={"initialization_errors": self.initialization_errors}
        )

    def record_runtime_error(self) -> None:
        self.failures += 1
        self.hass.states.async_set(f"sensor.{DOMAIN}_failures", str(self.failures))
