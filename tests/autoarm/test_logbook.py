"""Logbook descriptions, so changes AutoArm makes on its own show what caused them"""

from collections.abc import Callable
from typing import Any
from unittest.mock import Mock

from homeassistant.core import HomeAssistant

from custom_components.autoarm.const import DOMAIN, EVENT_TRIGGERED
from custom_components.autoarm.logbook import async_describe_events


def _describer(hass: HomeAssistant) -> Callable[[Any], dict[str, Any]]:
    registered: dict[str, Any] = {}

    def describe_event(domain: str, event_type: str, describer: Callable[[Any], dict[str, Any]]) -> None:
        registered[event_type] = (domain, describer)

    async_describe_events(hass, describe_event)
    domain, describer = registered[EVENT_TRIGGERED]
    assert domain == DOMAIN
    return describer


async def test_describes_source(hass: HomeAssistant) -> None:
    described = _describer(hass)(Mock(data={"entity_id": "alarm_control_panel.home", "source": "sunset", "summary": None}))

    assert described == {
        "name": "AutoArm",
        "message": "triggered by sunset",
        "source": "sunset",
        "entity_id": "alarm_control_panel.home",
    }


async def test_describes_calendar_event(hass: HomeAssistant) -> None:
    described = _describer(hass)(
        Mock(data={"entity_id": "alarm_control_panel.home", "source": "calendar", "summary": "Skiing"})
    )

    assert described["message"] == "triggered by calendar event Skiing"
    assert described["source"] == "calendar event Skiing"
