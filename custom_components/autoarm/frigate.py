"""Keep the active Frigate profile in step with the alarm state

See https://docs.frigate.video/configuration/profiles/
"""

import logging
from collections.abc import Callable

from homeassistant.components.select.const import ATTR_OPTIONS
from homeassistant.components.select.const import DOMAIN as SELECT_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, ATTR_OPTION, SERVICE_SELECT_OPTION, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import Context, Event, EventStateChangedData, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_state_change_event

from .const import EVENT_TRIGGERED, FRIGATE_NO_PROFILE, PUBLIC_ALARM_STATES
from .helpers import child_context

_LOGGER = logging.getLogger(__name__)

# ends the unique id of the Frigate integration's profile select, after its config entry id
FRIGATE_PROFILE_UNIQUE_ID_SUFFIX = ":select:profile"


def match_profile(state: str, available: list[str]) -> str | None:
    """The profile named for an alarm state, ignoring case, or else one named armed for any of the armed states"""
    by_name = {p.lower(): p for p in available if p != FRIGATE_NO_PROFILE}
    return by_name.get(state) or (by_name.get("armed") if state.startswith("armed_") else None)


def frigate_profile_selects(hass: HomeAssistant) -> list[str]:
    """Profile selects of the Frigate integration, one for each Frigate server with profiles"""
    return [
        entry.entity_id
        for entry in er.async_get(hass).entities.values()
        if entry.platform == "frigate" and entry.unique_id.endswith(FRIGATE_PROFILE_UNIQUE_ID_SUFFIX)
    ]


def frigate_profiles(hass: HomeAssistant, profile_select: str | None) -> list[str]:
    """Profiles of the profile select, or of any Frigate profile select before one is chosen"""
    selects = [profile_select] if profile_select else frigate_profile_selects(hass)
    return list(
        dict.fromkeys(
            p
            for entity_id in selects
            if (state := hass.states.get(entity_id))
            for p in state.attributes.get(ATTR_OPTIONS, [])
            if p != FRIGATE_NO_PROFILE
        )
    )


async def async_track_frigate_profile(
    hass: HomeAssistant, alarm_panel: str, profile_select: str, profiles: dict[str, str]
) -> Callable[[], None]:
    """Switch Frigate to the profile given for each alarm state, and to no profile for the others

    A state never given a profile is matched by name to one of the select's profiles,
    while transitional states, like arming or triggered, leave the profile as it is
    """

    async def sync(context: Context | None = None) -> None:
        panel = hass.states.get(alarm_panel)
        select = hass.states.get(profile_select)
        if (
            panel is None
            or panel.state not in PUBLIC_ALARM_STATES
            or select is None
            or select.state in (STATE_UNAVAILABLE, STATE_UNKNOWN)
        ):
            return
        available: list[str] = select.attributes.get(ATTR_OPTIONS, [])
        profile = (
            profiles[panel.state] if panel.state in profiles else match_profile(panel.state, available) or FRIGATE_NO_PROFILE
        )
        if profile not in available:
            # gone from Frigate, so back to the base config rather than staying on the profile of an earlier state
            _LOGGER.warning("AUTOARM No Frigate profile %s on %s for alarm state %s", profile, profile_select, panel.state)
            profile = FRIGATE_NO_PROFILE
        if profile == select.state:
            return
        _LOGGER.info("AUTOARM Frigate profile %s-->%s for alarm state %s", select.state, profile, panel.state)
        context = context or Context()
        if context.origin_event is None:
            # the logbook takes the first event of a context as its cause, otherwise that's the select action
            hass.bus.async_fire(EVENT_TRIGGERED, {ATTR_ENTITY_ID: profile_select, "alarm_state": panel.state}, context=context)
        try:
            await hass.services.async_call(
                SELECT_DOMAIN,
                SERVICE_SELECT_OPTION,
                {ATTR_ENTITY_ID: profile_select, ATTR_OPTION: profile},
                blocking=True,
                context=context,
            )
        except HomeAssistantError as e:
            _LOGGER.warning("AUTOARM Failed to set Frigate profile %s on %s: %s", profile, profile_select, e)

    async def on_panel_change(event: Event[EventStateChangedData]) -> None:
        await sync(child_context(event.context))

    async def on_select_change(event: Event[EventStateChangedData]) -> None:
        # only catching up as Frigate comes back, so a profile chosen by hand is left alone
        old = event.data["old_state"]
        if old is None or old.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            await sync(child_context(event.context))

    unsubscribes = [
        async_track_state_change_event(hass, [alarm_panel], on_panel_change),
        async_track_state_change_event(hass, [profile_select], on_select_change),
    ]
    await sync()

    def unsubscribe() -> None:
        for unsub in unsubscribes:
            unsub()

    return unsubscribe
