import logging
from typing import Any

from homeassistant.auth import HomeAssistant
from homeassistant.components.alarm_control_panel.const import AlarmControlPanelState
from homeassistant.const import CONF_SERVICE, CONF_SOURCE, CONF_STATE

from custom_components.autoarm.const import ALARM_STATES, CONF_SCENARIO, CONF_SUPERNOTIFY, NOTIFY_COMMON, ChangeSource
from custom_components.autoarm.helpers import AppHealthTracker

_LOGGER = logging.getLogger(__name__)


class Notifier:
    def __init__(
        self, notify_profiles: dict[str, dict[str, Any]] | None, hass: HomeAssistant, app_health_tracker: AppHealthTracker
    ) -> None:
        self.notify_profiles: dict[str, dict[str, Any]] = notify_profiles or {}
        self.hass = hass
        self.app_health_tracker = app_health_tracker

    async def notify(
        self,
        source: ChangeSource,
        from_state: AlarmControlPanelState | None = None,
        to_state: AlarmControlPanelState | None = None,
        message: str | None = None,
        title: str | None = None,
    ) -> None:
        notify_service: str | None = None
        try:
            selected_profile: dict[str, Any] | None = None
            selected_profile_name: str | None = None
            config_by_state_pickiness = sorted(
                self.notify_profiles, key=lambda v: len(self.notify_profiles[v].get(CONF_STATE, ALARM_STATES))
            )
            for profile_name in config_by_state_pickiness:
                if profile_name == NOTIFY_COMMON:
                    continue
                profile: dict[str, Any] = self.notify_profiles[profile_name]
                if profile.get(CONF_SOURCE) and source not in profile.get(CONF_SOURCE, []):
                    _LOGGER.debug("Notification not selected for %s profile for source match on %s", profile_name, source)
                    continue
                only_for_states: list[AlarmControlPanelState] | None = profile.get(CONF_STATE)
                if only_for_states and from_state not in only_for_states and to_state not in only_for_states:
                    _LOGGER.debug(
                        "Notification not selected for %s profile for state match on %s->%s", profile_name, from_state, to_state
                    )
                    continue
                selected_profile = profile
                selected_profile_name = profile_name
                break
            if not selected_profile:
                _LOGGER.debug("No profile selected for %s notification: %s", source, message)

            # separately merge base dict and data sub-dict as cheap and nasty semi-deep-merge
            base_profile = self.notify_profiles.get(NOTIFY_COMMON, {})
            base_profile_data = base_profile.get("data", {})
            merged_profile = dict(base_profile)
            merged_profile_data = dict(base_profile_data)
            if selected_profile:
                selected_profile_data: dict = selected_profile.get("data", {})
                merged_profile.update(selected_profile)
                merged_profile_data.update(selected_profile_data)
            merged_profile["data"] = merged_profile_data

            data = merged_profile.get("data", {})
            if "source" in data and data["source"] is None:
                data["source"] = source
            if "profile" in data and data["profile"] is None:
                data["profile"] = selected_profile_name
            if merged_profile.get(CONF_SUPERNOTIFY) and merged_profile.get(CONF_SCENARIO):
                data["apply_scenarios"] = merged_profile.get(CONF_SCENARIO)
            notify_service = merged_profile.get(CONF_SERVICE, "").replace("notify.", "")

            if title is None:
                title = f"Alarm now {to_state}" if to_state else "Alarm Panel Change"
            if message is None:
                if from_state and to_state:
                    message = f"Alarm state changed from {from_state} to {to_state} by {source.capitalize()}"
                else:
                    message = "Alarm control panel operation complete"

            if notify_service and merged_profile:
                await self.hass.services.async_call(
                    "notify",
                    notify_service,
                    service_data={"message": message, "title": title, "data": data},
                )
            else:
                _LOGGER.debug("AUTOARM Skipped notification, service: %s, data: %s", notify_service, merged_profile)

        except Exception as e:
            self.app_health_tracker.record_runtime_error()
            _LOGGER.error("AUTOARM notify.%s failed: %s", notify_service, e)
