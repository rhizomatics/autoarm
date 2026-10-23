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
    return describer  # type: ignore[no-any-return]


async def test_describes_source(hass: HomeAssistant) -> None:
    described = _describer(hass)(Mock(data={"entity_id": "alarm_control_panel.home", "source": "sunset", "summary": None}))

    assert described == {
        "name": "Auto Arm (sunset)",
        "message": "triggered by sunset",
        "source": "sunset",
        "entity_id": "alarm_control_panel.home",
    }


async def test_describes_calendar_event(hass: HomeAssistant) -> None:
    described = _describer(hass)(
        Mock(data={"entity_id": "alarm_control_panel.home", "source": "calendar", "summary": "Skiing"})
    )

    assert described["name"] == "Auto Arm (calendar event Skiing)"
    assert described["message"] == "triggered by calendar event Skiing"
    assert described["source"] == "calendar event Skiing"


async def test_describes_time_of_day_sensor(hass: HomeAssistant) -> None:
    described = _describer(hass)(Mock(data={"entity_id": "alarm_control_panel.home", "source": "tod", "summary": "Bedtime"}))

    assert described["name"] == "Auto Arm (times of the day sensor Bedtime)"
    assert described["message"] == "triggered by times of the day sensor Bedtime"
    assert described["source"] == "times of the day sensor Bedtime"


async def test_describes_alarm_state(hass: HomeAssistant) -> None:
    described = _describer(hass)(Mock(data={"entity_id": "select.frigate_profile", "alarm_state": "armed_away"}))

    assert described == {
        "name": "Auto Arm (alarm armed_away)",
        "message": "triggered by alarm armed_away",
        "source": "alarm armed_away",
        "entity_id": "select.frigate_profile",
    }


async def test_describes_deferred_source(hass: HomeAssistant) -> None:
    described = _describer(hass)(
        Mock(data={"entity_id": "alarm_control_panel.home", "source": "sunrise", "summary": None, "deferred": True})
    )

    assert described["name"] == "Auto Arm (deferred from sunrise)"
    assert described["message"] == "triggered by deferred from sunrise"
