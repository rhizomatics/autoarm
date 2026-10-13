import logging
from typing import Any

from homeassistant.components.alarm_control_panel.const import AlarmControlPanelState
from homeassistant.const import CONF_ACTION, CONF_ACTIONS, CONF_SERVICE, CONF_SOURCE, CONF_STATE, CONF_TARGET
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import translation

from custom_components.autoarm.const import (
    ALARM_STATES,
    CONF_SCENARIO,
    CONF_SUPERNOTIFY,
    DOMAIN,
    MOBILE_ACTION_STATES,
    NOTIFY_COMMON,
    NOTIFY_PRIORITY_SOURCES,
    SUPERNOTIFY_ACTION,
    SUPERNOTIFY_MOBILE_ACTIONS,
    ChangeSource,
)
from custom_components.autoarm.helpers import AppHealthTracker, friendly_state

_LOGGER = logging.getLogger(__name__)


class Notifier:
    def __init__(
        self,
        notify_profiles: dict[str, dict[str, Any]] | None,
        hass: HomeAssistant,
        app_health_tracker: AppHealthTracker,
        notify_action: str | None,
        notify_targets: list[str] | None = None,
        notify_data: dict[str, Any] | None = None,
        notify_target: dict[str, Any] | None = None,
        notify_custom_target: list[str] | None = None,
        notify_deliveries: list[str] | None = None,
        notify_priorities: dict[str, str] | None = None,
    ) -> None:
        self.notify_profiles: dict[str, dict[str, Any]] = notify_profiles or {}
        self.hass: HomeAssistant = hass
        self.app_health_tracker: AppHealthTracker = app_health_tracker
        self.notify_action: str | None = notify_action
        # targets typed in, as addresses or entity ids, wherever in the options they were put
        self.notify_targets: list[str] = list(dict.fromkeys([*(notify_targets or []), *(notify_custom_target or [])]))
        # targets picked from Home Assistant's own entities, devices, areas and labels
        self.notify_target: dict[str, Any] = notify_target or {}
        self.notify_deliveries: list[str] = notify_deliveries or []
        # Supernotify priority for each kind of change, keyed as NOTIFY_PRIORITY_SOURCES
        self.notify_priorities: dict[str, str] = notify_priorities or {}
        # extra service data configured via the options UI's ObjectSelector, lowest priority so
        # YAML profile data (common or per-profile) can still override individual keys
        self.notify_data: dict[str, Any] = notify_data or {}
        if (
            (self.notify_action or self.notify_profiles.get(NOTIFY_COMMON, {}).get(CONF_SERVICE)) == "notify.send_message"
            and not self.notify_targets
            and not self.notify_target
            and not any(profile.get(CONF_TARGET) for profile in self.notify_profiles.values())
        ):
            _LOGGER.warning(
                "AUTOARM No notifications will be sent, as notify.send_message needs Notification Targets, set in the options"
            )

    async def _mobile_actions(
        self, actions: list[dict[str, Any]], state: AlarmControlPanelState | None
    ) -> list[dict[str, Any]]:
        """Leave out actions for the state the alarm is already in, and give Auto Arm's own a translated title"""
        titles: dict[str, str] = await translation.async_get_translations(
            self.hass, self.hass.config.language, "selector", [DOMAIN]
        )
        selected: list[dict[str, Any]] = []
        for action in actions:
            action_key: str = str(action.get(CONF_ACTION))
            if state is not None and MOBILE_ACTION_STATES.get(action_key) == state:
                continue
            title: str | None = titles.get(f"component.{DOMAIN}.selector.mobile_action.options.{action_key.lower()}")
            selected.append({"title": title, **action} if title else action)
        return selected

    async def notify(
        self,
        source: ChangeSource,
        from_state: AlarmControlPanelState | None = None,
        to_state: AlarmControlPanelState | None = None,
        message: str | None = None,
        title: str | None = None,
        context: Context | None = None,
        source_name: str | None = None,
    ) -> None:

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
                    _LOGGER.debug(
                        "AUTOARM Notification not selected for %s profile for source match on %s", profile_name, source
                    )
                    continue
                only_for_states: list[AlarmControlPanelState] | None = profile.get(CONF_STATE)
                if only_for_states and from_state not in only_for_states and to_state not in only_for_states:
                    _LOGGER.debug(
                        "AUTOARM Notification not selected for %s profile for state match on %s->%s",
                        profile_name,
                        from_state,
                        to_state,
                    )
                    continue
                selected_profile = profile
                selected_profile_name = profile_name
                break
            if selected_profile is None:
                _LOGGER.debug("AUTOARM No profile selected for %s notification: %s", source, message)
                return

            # separately merge base dict and data sub-dict as cheap and nasty semi-deep-merge
            base_profile = self.notify_profiles.get(NOTIFY_COMMON, {})
            base_profile_data = base_profile.get("data", {})
            merged_profile = dict(base_profile)
            # options-configured data is the lowest priority layer, YAML profiles can override any key
            merged_profile_data = dict(self.notify_data)
            merged_profile_data.update(base_profile_data)
            if selected_profile is not None:
                selected_profile_data: dict[str, Any] = selected_profile.get("data", {})
                merged_profile.update(selected_profile)
                merged_profile_data.update(selected_profile_data)
            merged_profile["data"] = merged_profile_data

            data = merged_profile.get("data", {})
            if "source" in data and data["source"] is None:
                data["source"] = str(source)
            if "profile" in data and data["profile"] is None:
                data["profile"] = selected_profile_name
            # a profile's own service wins, then the action chosen in the options, then the common profile's
            notify_action: str | None = (
                selected_profile.get(CONF_SERVICE) or self.notify_action or merged_profile.get(CONF_SERVICE)
            )
            supernotify_action: bool = notify_action == SUPERNOTIFY_ACTION
            if supernotify_action:
                data.setdefault(CONF_ACTIONS, SUPERNOTIFY_MOBILE_ACTIONS)
                # a priority in a profile or the extra data is kept
                for kind, priority in self.notify_priorities.items():
                    if source in NOTIFY_PRIORITY_SOURCES.get(kind, []):
                        data.setdefault("priority", priority)
            if isinstance(data.get(CONF_ACTIONS), list):
                data[CONF_ACTIONS] = await self._mobile_actions(data[CONF_ACTIONS], to_state)
            if (merged_profile.get(CONF_SUPERNOTIFY) or supernotify_action) and merged_profile.get(CONF_SCENARIO):
                data["apply_scenarios"] = merged_profile.get(CONF_SCENARIO)
            if supernotify_action and to_state:
                # for Supernotify scenarios to pick up, it ignores any that aren't configured there
                state_scenarios: list[str] = [f"{DOMAIN}-{to_state}"]
                if to_state.startswith("armed_"):
                    state_scenarios.append(f"{DOMAIN}-armed")
                data["apply_scenarios"] = [*cv.ensure_list(data.get("apply_scenarios")), *state_scenarios]

            # a profile's own targets take over from all of those chosen in the options
            notify_targets: list[str] | None = merged_profile.get(CONF_TARGET, self.notify_targets)
            picked_target: dict[str, Any] = {} if CONF_TARGET in merged_profile else self.notify_target
            if notify_action is None:
                _LOGGER.debug("AUTOARM Notifications disabled, no notification action")
                return
            if notify_action == "notify.send_message" and not notify_targets and not picked_target:
                _LOGGER.debug("AUTOARM Notifications disabled, no targets for notify.send_message")
                return

            if title is None:
                title = f"Alarm now {friendly_state(to_state)}" if to_state else "Alarm Panel Change"
            if message is None:
                if from_state and to_state:
                    if source == ChangeSource.TOD:
                        changed_by = f"{source_name} Times of the Day sensor" if source_name else "Times of the Day sensor"
                    else:
                        changed_by = source.capitalize()
                    message = (
                        f"Alarm state changed from {friendly_state(from_state)} to {friendly_state(to_state)} by {changed_by}"
                    )
                else:
                    message = "Alarm control panel operation complete"

            if notify_action and merged_profile:
                service_data: dict[str, Any] = {"message": message, "title": title}
                if supernotify_action:
                    # supernotify.notify takes the data fields at the top level
                    service_data.update(data)
                    if self.notify_deliveries and "delivery" not in service_data:
                        service_data["delivery"] = self.notify_deliveries
                        service_data.setdefault("delivery_selection", "explicit")
                elif data and notify_action != "notify.send_message":
                    # new notify entities can't handle nested data section
                    service_data["data"] = data
                domain, action = notify_action.split(".", 1)
                target: dict[str, Any] | None = None
                if domain == "notify" and action == "send_message":
                    # notify.send_message is entity-based and targets via entity_id,
                    # not a "target" key in service_data like legacy notify services
                    target = dict(picked_target)
                    if entity_ids := [*cv.ensure_list(picked_target.get("entity_id")), *(notify_targets or [])]:
                        target["entity_id"] = entity_ids
                elif supernotify_action and picked_target:
                    # the same pair of target fields as supernotify.notify itself
                    service_data["target"] = picked_target
                    if notify_targets:
                        service_data["custom_target"] = notify_targets
                elif notify_targets:
                    service_data["target"] = notify_targets

                _LOGGER.debug("AUTOARM Notifying %s.%s with %s target=%s", domain, action, service_data, target)
                try:
                    await self.hass.services.async_call(
                        domain,
                        action,
                        service_data=service_data,
                        target=target,
                        context=context,
                    )
                except Exception as e:
                    _LOGGER.error("AUTOARM notify failure, %s.%s: %s [%s]", domain, action, service_data, e)
                    raise
            else:
                _LOGGER.debug("AUTOARM Skipped notification, service: %s, data: %s", self.notify_action, merged_profile)

        except Exception:
            self.app_health_tracker.record_runtime_error()
            _LOGGER.exception("AUTOARM %s failed", self.notify_action)
