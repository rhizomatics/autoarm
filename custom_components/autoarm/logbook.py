"""Describe AutoArm's logbook events, so the changes it makes on its own show what caused them"""

from collections.abc import Callable
from typing import Any

from homeassistant.components.logbook import LazyEventPartialState  # type: ignore[attr-defined]
from homeassistant.components.logbook.const import (
    LOGBOOK_ENTRY_ENTITY_ID,
    LOGBOOK_ENTRY_MESSAGE,
    LOGBOOK_ENTRY_NAME,
    LOGBOOK_ENTRY_SOURCE,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN, EVENT_TRIGGERED, ChangeSource


@callback
def async_describe_events(
    hass: HomeAssistant,
    async_describe_event: Callable[[str, str, Callable[[LazyEventPartialState], dict[str, Any]]], None],
) -> None:
    """Describe logbook events."""

    @callback
    def async_describe_triggered(event: LazyEventPartialState) -> dict[str, Any]:
        data = event.data
        cause: str = data.get("source", "unknown")
        if data.get("summary"):
            kind = "time of day sensor" if cause == ChangeSource.TOD else "calendar event"
            cause = f"{kind} {data['summary']}"
        return {
            LOGBOOK_ENTRY_NAME: "AutoArm",
            LOGBOOK_ENTRY_MESSAGE: f"triggered by {cause}",
            LOGBOOK_ENTRY_SOURCE: cause,
            LOGBOOK_ENTRY_ENTITY_ID: data.get(ATTR_ENTITY_ID),
        }

    async_describe_event(DOMAIN, EVENT_TRIGGERED, async_describe_triggered)
