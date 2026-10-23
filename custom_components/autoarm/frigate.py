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
from homeassistant.helpers.event import async_track_state_change_event

from .const import FRIGATE_NO_PROFILE, PUBLIC_ALARM_STATES
from .helpers import child_context

_LOGGER = logging.getLogger(__name__)


async def async_track_frigate_profile(
    hass: HomeAssistant, alarm_panel: str, profile_select: str, profiles: dict[str, str]
) -> Callable[[], None]:
    """Switch Frigate to the profile given for each alarm state, and to no profile for the others

    Transitional states, like arming or triggered, leave the profile as it is
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
        profile = profiles.get(panel.state, FRIGATE_NO_PROFILE)
        if profile == select.state:
            return
        if profile not in select.attributes.get(ATTR_OPTIONS, []):
            _LOGGER.warning("AUTOARM No Frigate profile %s on %s for alarm state %s", profile, profile_select, panel.state)
            return
        _LOGGER.info("AUTOARM Frigate profile %s-->%s for alarm state %s", select.state, profile, panel.state)
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
