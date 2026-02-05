"""Diagnostics support for AutoArm."""

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .autoarming import HASS_DATA_KEY
from .const import YAML_DATA_KEY


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    yaml_config = hass.data.get(YAML_DATA_KEY, {})
    data: dict[str, Any] = {
        "entry_data": dict(entry.data),
        "entry_options": dict(entry.options),
        "yaml_keys": list(yaml_config.keys()),
    }

    if HASS_DATA_KEY in hass.data:
        armer = hass.data[HASS_DATA_KEY].armer
        data["armer"] = {
            "alarm_panel": armer.alarm_panel,
            "calendar_count": len(armer.calendars),
            "person_entities": armer.person_entities,
            "failures": armer.app_health_tracker.failures,
            "initialized": armer.app_health_tracker.initialized,
        }

    return data
