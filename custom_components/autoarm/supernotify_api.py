"""The parts of Supernotify used, all through its actions and entities so there's no import dependency"""

from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError

SUPERNOTIFY_DOMAIN = "supernotify"


@callback
def supernotify_available(hass: HomeAssistant) -> bool:
    return hass.services.has_service(SUPERNOTIFY_DOMAIN, "notify")


async def _enquire(hass: HomeAssistant, action: str) -> dict[str, Any]:
    try:
        response = await hass.services.async_call(SUPERNOTIFY_DOMAIN, action, blocking=True, return_response=True)
    except HomeAssistantError:
        # an older Supernotify without the action
        return {}
    return dict(response) if response else {}


async def deliveries(hass: HomeAssistant) -> list[str]:
    """Delivery names, both those configured and those Supernotify set up itself"""
    # every delivery has a switch, the only place to find one Supernotify set up itself but that
    # Delivery Control has made explicit or scenario only, so is neither implicit nor configured
    names: set[str] = {
        state.attributes["name"]
        for state in hass.states.async_all("switch")
        if state.entity_id.startswith(f"switch.{SUPERNOTIFY_DOMAIN}_delivery_") and state.attributes.get("name")
    }
    for implicit in (await _enquire(hass, "enquire_implicit_deliveries")).values():
        names.update(implicit)
    names.update((await _enquire(hass, "enquire_configuration")).get("delivery") or {})
    return sorted(names)
