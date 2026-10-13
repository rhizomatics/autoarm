"""Diagnostics support for AutoArm."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .autoarming import AutoArmConfigEntry
from .config_flow import CONF_PANEL_CODE
from .const import YAML_DATA_KEY


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: AutoArmConfigEntry) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    yaml_config = hass.data.get(YAML_DATA_KEY, {})
    data: dict[str, Any] = {
        "entry_data": dict(entry.data),
        "entry_options": async_redact_data(dict(entry.options), {CONF_PANEL_CODE}),
        "yaml_keys": list(yaml_config.keys()),
    }

    if armer := getattr(entry, "runtime_data", None):
        data["armer"] = {
            "alarm_panel": armer.alarm_panel,
            "calendar_count": len(armer.calendars),
            "occupants": armer.occupants,
            "failures": armer.app_health_tracker.failures,
            "initialization_errors": armer.app_health_tracker.initialization_errors,
        }

    return data
