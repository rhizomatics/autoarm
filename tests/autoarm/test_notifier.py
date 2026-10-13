from typing import TYPE_CHECKING, Any
from unittest.mock import Mock

import pytest
from homeassistant.components.alarm_control_panel.const import AlarmControlPanelState
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.autoarm.autoarming import YAML_NOTIFY_ISSUE, AlarmArmer
from custom_components.autoarm.config_flow import CONF_NOTIFY_ACTION, CONF_NOTIFY_ENABLED, CONF_USE_ALARM_SERVICE
from custom_components.autoarm.const import (
    CONF_ALARM_PANEL,
    DOMAIN,
    NOTIFY_SCHEMA,
    SUPERNOTIFY_MOBILE_ACTIONS,
    YAML_DATA_KEY,
    ChangeSource,
)
from custom_components.autoarm.helpers import AppHealthTracker
from custom_components.autoarm.notifier import Notifier

if TYPE_CHECKING:
    from homeassistant.helpers.typing import ConfigType

TEST_PANEL = "alarm_control_panel.test_panel"


def test_notify_skipped_when_no_service(hass: HomeAssistant) -> None:
    """Test that notification is skipped when no service is configured."""
    armer = AlarmArmer(hass, TEST_PANEL, notify_enabled=False)
    assert armer.notifier is None


async def test_notify_calls_service(hass: HomeAssistant) -> None:
    """Test that notify calls hass.services.async_call with correct parameters."""
    notify_config: ConfigType = {
        "backstop": {},
    }
    armer = AlarmArmer(
        hass, TEST_PANEL, notify_enabled=True, notify_action="notify.test_service", notify_profiles=notify_config
    )
    calls: list[dict[str, Any]] = []

    @callback
    def mock_handler(call: ServiceCall) -> None:
        calls.append({"service": call.service, "data": dict(call.data)})

    hass.services.async_register("notify", "test_service", mock_handler)
    assert armer.notifier is not None
    await armer.notifier.notify(ChangeSource.BUTTON, message="Test message")

    assert len(calls) == 1
    assert calls[0]["data"]["message"] == "Test message"
    assert calls[0]["data"]["title"] == "Alarm Panel Change"


async def test_notify_with_custom_title(hass: HomeAssistant) -> None:
    """Test that notify uses custom title when provided."""
    notify_config: ConfigType = {
        "backstop": {},
    }
    armer = AlarmArmer(
        hass, TEST_PANEL, notify_enabled=True, notify_action="notify.test_service", notify_profiles=notify_config
    )
    calls: list[dict[str, Any]] = []

    @callback
    def mock_handler(call: ServiceCall) -> None:
        calls.append({"service": call.service, "data": dict(call.data)})

    hass.services.async_register("notify", "test_service", mock_handler)
    assert armer.notifier is not None
    await armer.notifier.notify(ChangeSource.BUTTON, message="Test message", title="Custom Title")

    assert len(calls) == 1
    assert calls[0]["data"]["title"] == "Custom Title"


async def test_notify_profile_merging(hass: HomeAssistant) -> None:
    """Test that selected profile is merged with common profile."""
    notify_config: ConfigType = {
        "common": {"service": "notify.common_service", "data": {"priority": "low"}},
        "quiet": {"service": "notify.quiet_service", "source": [ChangeSource.BUTTON], "data": {"sound": "none"}},
    }
    armer = AlarmArmer(hass, TEST_PANEL, notify_enabled=True, notify_profiles=notify_config)
    calls: list[dict[str, Any]] = []

    @callback
    def mock_handler(call: ServiceCall) -> None:
        calls.append({"service": call.service, "data": dict(call.data)})

    hass.services.async_register("notify", "quiet_service", mock_handler)
    assert armer.notifier is not None
    await armer.notifier.notify(ChangeSource.BUTTON, message="Test message")

    assert len(calls) == 1
    # Data should have both priority from common and sound from quiet
    assert calls[0]["data"]["data"]["priority"] == "low"
    assert calls[0]["data"]["data"]["sound"] == "none"


async def test_notify_data_from_options_is_included_but_overridden_by_yaml(hass: HomeAssistant) -> None:
    """Extra data configured via the options UI's ObjectSelector is included, but a YAML profile's data wins."""
    notify_config: ConfigType = {
        "common": {"data": {"priority": "urgent"}},
        "backstop": {},
    }
    armer = AlarmArmer(
        hass,
        TEST_PANEL,
        notify_enabled=True,
        notify_action="notify.test_service",
        notify_profiles=notify_config,
        notify_data={"priority": "low", "channel": "alarm"},
    )
    calls: list[dict[str, Any]] = []

    @callback
    def mock_handler(call: ServiceCall) -> None:
        calls.append({"service": call.service, "data": dict(call.data)})

    hass.services.async_register("notify", "test_service", mock_handler)
    assert armer.notifier is not None
    await armer.notifier.notify(ChangeSource.BUTTON, message="Test message")

    assert len(calls) == 1
    assert calls[0]["data"]["data"]["channel"] == "alarm"
    # the YAML common profile's own "priority" wins over the options-configured default
    assert calls[0]["data"]["data"]["priority"] == "urgent"


async def test_notify_source_replacement(hass: HomeAssistant) -> None:
    """Test that source is set in data when data['source'] is None."""
    notify_config: ConfigType = {
        "common": {"data": {"source": None}},
        "backstop": {},
    }
    armer = AlarmArmer(
        hass, TEST_PANEL, notify_enabled=True, notify_action="notify.test_service", notify_profiles=notify_config
    )
    calls: list[dict[str, Any]] = []

    @callback
    def mock_handler(call: ServiceCall) -> None:
        calls.append({"service": call.service, "data": dict(call.data)})

    hass.services.async_register("notify", "test_service", mock_handler)
    assert armer.notifier is not None
    await armer.notifier.notify(ChangeSource.ALARM_PANEL, message="Test message")

    assert len(calls) == 1
    assert calls[0]["data"]["data"]["source"] == ChangeSource.ALARM_PANEL


async def test_notify_supernotify_scenario(hass: HomeAssistant) -> None:
    """Test that supernotify scenarios are added to data when configured."""
    notify_config: ConfigType = {
        "common": {"scenario": ["urgent"], "supernotify": True},
        "backstop": {},
    }
    armer = AlarmArmer(hass, TEST_PANEL, notify_enabled=True, notify_action="notify.supernotify", notify_profiles=notify_config)
    calls: list[dict[str, Any]] = []

    @callback
    def mock_handler(call: ServiceCall) -> None:
        calls.append({"service": call.service, "data": dict(call.data)})

    hass.services.async_register("notify", "supernotify", mock_handler)
    assert armer.notifier is not None
    await armer.notifier.notify(ChangeSource.BUTTON, message="Test message")

    assert len(calls) == 1
    assert calls[0]["data"]["data"]["apply_scenarios"] == ["urgent"]


async def test_notify_exception_records_runtime_error(hass: HomeAssistant) -> None:
    """Test that exceptions during notify call record_runtime_error."""
    # Use a non-existent service to trigger ServiceNotFound exception
    notify_config: ConfigType = {
        "backstop": {},
    }
    armer = AlarmArmer(
        hass, TEST_PANEL, notify_enabled=True, notify_action="notify.nonexistent_service", notify_profiles=notify_config
    )
    initial_failures = armer.app_health_tracker.failures

    # Don't register the service - this should cause an exception
    assert armer.notifier is not None
    await armer.notifier.notify(ChangeSource.BUTTON, message="Test message")

    assert armer.app_health_tracker.failures == initial_failures + 1


async def test_notify_strips_notify_prefix_from_service(hass: HomeAssistant) -> None:
    """Test that 'notify.' prefix is stripped from service name."""
    notify_config: ConfigType = {
        "backstop": {},
    }
    armer = AlarmArmer(hass, TEST_PANEL, notify_enabled=True, notify_action="notify.mobile_app", notify_profiles=notify_config)
    calls: list[dict[str, Any]] = []

    @callback
    def mock_handler(call: ServiceCall) -> None:
        calls.append({"service": call.service, "data": dict(call.data)})

    hass.services.async_register("notify", "mobile_app", mock_handler)
    assert armer.notifier is not None
    await armer.notifier.notify(ChangeSource.BUTTON, message="Test message")

    assert len(calls) == 1
    assert calls[0]["service"] == "mobile_app"


async def test_notify_selects_profile_by_from_state(hass: HomeAssistant) -> None:
    """Test that profile is selected when from_state matches."""
    from homeassistant.components.alarm_control_panel.const import AlarmControlPanelState

    notify_config: ConfigType = {
        "away_alert": {
            "service": "notify.away_service",
            "state": [AlarmControlPanelState.ARMED_AWAY],
            "data": {"priority": "high"},
        },
    }
    armer = AlarmArmer(
        hass, TEST_PANEL, notify_enabled=True, notify_action="notify.default_service", notify_profiles=notify_config
    )
    calls: list[dict[str, Any]] = []

    @callback
    def mock_handler(call: ServiceCall) -> None:
        calls.append({"service": call.service, "data": dict(call.data)})

    hass.services.async_register("notify", "away_service", mock_handler)
    assert armer.notifier is not None
    await armer.notifier.notify(
        ChangeSource.BUTTON,
        from_state=AlarmControlPanelState.ARMED_AWAY,
        to_state=AlarmControlPanelState.DISARMED,
    )

    assert len(calls) == 1
    assert calls[0]["data"]["data"]["priority"] == "high"


async def test_notify_selects_profile_by_to_state(hass: HomeAssistant) -> None:
    """Test that profile is selected when to_state matches."""
    from homeassistant.components.alarm_control_panel.const import AlarmControlPanelState

    notify_config: ConfigType = {
        "vacation_alert": {
            "service": "notify.vacation_service",
            "state": [AlarmControlPanelState.ARMED_VACATION],
            "data": {"channel": "vacation"},
        },
    }
    armer = AlarmArmer(
        hass, TEST_PANEL, notify_enabled=True, notify_action="notify.default_service", notify_profiles=notify_config
    )
    calls: list[dict[str, Any]] = []

    @callback
    def mock_handler(call: ServiceCall) -> None:
        calls.append({"service": call.service, "data": dict(call.data)})

    hass.services.async_register("notify", "vacation_service", mock_handler)
    assert armer.notifier is not None
    await armer.notifier.notify(
        ChangeSource.CALENDAR,
        from_state=AlarmControlPanelState.ARMED_HOME,
        to_state=AlarmControlPanelState.ARMED_VACATION,
    )

    assert len(calls) == 1
    assert calls[0]["data"]["data"]["channel"] == "vacation"


async def test_notify_skips_profile_when_state_not_matched(hass: HomeAssistant) -> None:
    """Test that no notification is sent when no profile matches the state."""
    from homeassistant.components.alarm_control_panel.const import AlarmControlPanelState

    notify_config: ConfigType = {
        "away_only": {
            "service": "notify.away_service",
            "state": [AlarmControlPanelState.ARMED_AWAY],
            "data": {"tag": "away"},
        },
    }
    armer = AlarmArmer(
        hass, TEST_PANEL, notify_enabled=True, notify_action="notify.default_service", notify_profiles=notify_config
    )
    calls: list[dict[str, Any]] = []

    @callback
    def mock_handler(call: ServiceCall) -> None:
        calls.append({"service": call.service, "data": dict(call.data)})

    hass.services.async_register("notify", "default_service", mock_handler)
    hass.services.async_register("notify", "away_service", mock_handler)
    assert armer.notifier is not None
    await armer.notifier.notify(
        ChangeSource.BUTTON,
        from_state=AlarmControlPanelState.ARMED_HOME,
        to_state=AlarmControlPanelState.DISARMED,
    )

    assert len(calls) == 0


async def test_notify_skips_profile_when_source_not_matched(hass: HomeAssistant) -> None:
    """Test that no notification is sent when no profile matches the source."""
    notify_config: ConfigType = {
        "button_only": {
            "service": "notify.button_service",
            "source": [ChangeSource.BUTTON],
            "data": {"tag": "button"},
        },
    }
    armer = AlarmArmer(
        hass, TEST_PANEL, notify_enabled=True, notify_action="notify.default_service", notify_profiles=notify_config
    )
    calls: list[dict[str, Any]] = []

    @callback
    def mock_handler(call: ServiceCall) -> None:
        calls.append({"service": call.service, "data": dict(call.data)})

    hass.services.async_register("notify", "default_service", mock_handler)
    hass.services.async_register("notify", "button_service", mock_handler)
    assert armer.notifier is not None
    await armer.notifier.notify(ChangeSource.CALENDAR, message="Test message")

    assert len(calls) == 0


async def test_notify_auto_generates_title_from_to_state(hass: HomeAssistant) -> None:
    """Test that title is auto-generated from to_state when not provided."""
    from homeassistant.components.alarm_control_panel.const import AlarmControlPanelState

    notify_config: ConfigType = {
        "backstop": {},
    }
    armer = AlarmArmer(
        hass, TEST_PANEL, notify_enabled=True, notify_action="notify.test_service", notify_profiles=notify_config
    )
    calls: list[dict[str, Any]] = []

    @callback
    def mock_handler(call: ServiceCall) -> None:
        calls.append({"service": call.service, "data": dict(call.data)})

    hass.services.async_register("notify", "test_service", mock_handler)
    assert armer.notifier is not None
    await armer.notifier.notify(
        ChangeSource.BUTTON,
        to_state=AlarmControlPanelState.ARMED_AWAY,
    )

    assert len(calls) == 1
    assert calls[0]["data"]["title"] == "Alarm now Armed Away"


async def test_notify_auto_generates_message_from_states(hass: HomeAssistant) -> None:
    """Test that message is auto-generated from from_state and to_state."""
    from homeassistant.components.alarm_control_panel.const import AlarmControlPanelState

    notify_config: ConfigType = {
        "backstop": {},
    }
    armer = AlarmArmer(
        hass, TEST_PANEL, notify_enabled=True, notify_action="notify.test_service", notify_profiles=notify_config
    )
    calls: list[dict[str, Any]] = []

    @callback
    def mock_handler(call: ServiceCall) -> None:
        calls.append({"service": call.service, "data": dict(call.data)})

    hass.services.async_register("notify", "test_service", mock_handler)
    assert armer.notifier is not None
    await armer.notifier.notify(
        ChangeSource.ALARM_PANEL,
        from_state=AlarmControlPanelState.ARMED_HOME,
        to_state=AlarmControlPanelState.ARMED_AWAY,
    )

    assert len(calls) == 1
    message = calls[0]["data"]["message"]
    assert message == "Alarm state changed from Armed Home to Armed Away by Alarm_panel"


async def test_notify_profile_name_replacement(hass: HomeAssistant) -> None:
    """Test that profile name is set in data when data['profile'] is None."""
    notify_config: ConfigType = {
        "common": {"data": {"profile": None}},
        "urgent": {"source": [ChangeSource.BUTTON]},
    }
    armer = AlarmArmer(
        hass, TEST_PANEL, notify_enabled=True, notify_action="notify.test_service", notify_profiles=notify_config
    )
    calls: list[dict[str, Any]] = []

    @callback
    def mock_handler(call: ServiceCall) -> None:
        calls.append({"service": call.service, "data": dict(call.data)})

    hass.services.async_register("notify", "test_service", mock_handler)
    assert armer.notifier is not None
    await armer.notifier.notify(ChangeSource.BUTTON, message="Test message")

    assert len(calls) == 1
    assert calls[0]["data"]["data"]["profile"] == "urgent"


async def test_notify_common_profile_not_selected_as_match(hass: HomeAssistant) -> None:
    """Test that common profile is skipped during profile selection."""
    notify_config: ConfigType = {
        "common": {"source": [ChangeSource.BUTTON]},
    }
    armer = AlarmArmer(
        hass, TEST_PANEL, notify_enabled=True, notify_action="notify.common_service", notify_profiles=notify_config
    )
    calls: list[dict[str, Any]] = []

    @callback
    def mock_handler(call: ServiceCall) -> None:
        calls.append({"service": call.service, "data": dict(call.data)})

    hass.services.async_register("notify", "common_service", mock_handler)
    # common is not selected as a matching profile, and with no other profiles
    # no notification is sent
    assert armer.notifier is not None
    await armer.notifier.notify(ChangeSource.BUTTON, message="Test message")

    assert len(calls) == 0


async def test_notify_selects_profile_with_both_source_and_state(hass: HomeAssistant) -> None:
    """Test profile selection when both source and state filters are configured."""
    from homeassistant.components.alarm_control_panel.const import AlarmControlPanelState

    notify_config: ConfigType = {
        "button_away": {
            "service": "notify.special_service",
            "source": [ChangeSource.BUTTON],
            "state": [AlarmControlPanelState.ARMED_AWAY],
            "data": {"special": True},
        },
    }
    armer = AlarmArmer(
        hass, TEST_PANEL, notify_enabled=True, notify_action="notify.default_service", notify_profiles=notify_config
    )
    calls: list[dict[str, Any]] = []

    @callback
    def mock_handler(call: ServiceCall) -> None:
        calls.append({"service": call.service, "data": dict(call.data)})

    hass.services.async_register("notify", "special_service", mock_handler)
    hass.services.async_register("notify", "default_service", mock_handler)

    # Both source and state match
    assert armer.notifier is not None
    await armer.notifier.notify(
        ChangeSource.BUTTON,
        from_state=AlarmControlPanelState.DISARMED,
        to_state=AlarmControlPanelState.ARMED_AWAY,
    )
    await armer.notifier.notify(
        ChangeSource.BUTTON,
        from_state=AlarmControlPanelState.ARMED_HOME,
        to_state=AlarmControlPanelState.DISARMED,
    )

    assert len(calls) == 1
    assert calls[0]["service"] == "special_service"
    assert calls[0]["data"]["data"]["special"] is True


async def test_notify_profile_ordering_by_state_specificity(hass: HomeAssistant) -> None:
    """Test that more specific profiles (fewer states) are checked first."""
    from homeassistant.components.alarm_control_panel.const import AlarmControlPanelState

    notify_config: ConfigType = {
        "common": {"service": "notify.default_service"},
        "backstop": {},
        # Broad profile - matches many states
        "broad": {
            "service": "notify.broad_service",
            "state": [
                AlarmControlPanelState.ARMED_AWAY,
                AlarmControlPanelState.ARMED_HOME,
                AlarmControlPanelState.ARMED_NIGHT,
            ],
            "data": {"profile": "broad"},
        },
        # Specific profile - matches only one state
        "specific": {
            "service": "notify.specific_service",
            "state": [AlarmControlPanelState.ARMED_AWAY],
            "data": {"profile": "specific"},
        },
    }
    armer = AlarmArmer(hass, TEST_PANEL, notify_enabled=True, notify_profiles=notify_config)
    calls: list[dict[str, Any]] = []

    @callback
    def mock_handler(call: ServiceCall) -> None:
        calls.append({"service": call.service, "data": dict(call.data)})

    hass.services.async_register("notify", "broad_service", mock_handler)
    hass.services.async_register("notify", "specific_service", mock_handler)

    # Both profiles match ARMED_AWAY, but specific should win due to fewer states
    assert armer.notifier is not None
    await armer.notifier.notify(
        ChangeSource.BUTTON,
        from_state=AlarmControlPanelState.DISARMED,
        to_state=AlarmControlPanelState.ARMED_AWAY,
    )

    assert len(calls) == 1
    assert calls[0]["service"] == "specific_service"
    assert calls[0]["data"]["data"]["profile"] == "specific"


async def test_notify_profile_with_state_filter_preferred_over_no_filter(hass: HomeAssistant) -> None:
    """Test that profiles with state filters are preferred over those without."""
    from homeassistant.components.alarm_control_panel.const import AlarmControlPanelState

    notify_config: ConfigType = {
        "common": {"service": "notify.default_service"},
        "backstop": {},
        # No state filter - matches all states
        "catch_all": {
            "service": "notify.catch_all_service",
            "source": [ChangeSource.BUTTON],
            "data": {"profile": "catch_all"},
        },
        # Has state filter
        "filtered": {
            "service": "notify.filtered_service",
            "source": [ChangeSource.BUTTON],
            "state": [AlarmControlPanelState.ARMED_AWAY, AlarmControlPanelState.ARMED_HOME],
            "data": {"profile": "filtered"},
        },
    }
    armer = AlarmArmer(hass, TEST_PANEL, notify_enabled=True, notify_profiles=notify_config)
    calls: list[dict[str, Any]] = []

    @callback
    def mock_handler(call: ServiceCall) -> None:
        calls.append({"service": call.service, "data": dict(call.data)})

    hass.services.async_register("notify", "catch_all_service", mock_handler)
    hass.services.async_register("notify", "filtered_service", mock_handler)

    # Both profiles match source, but filtered should win (has state filter)
    assert armer.notifier is not None
    await armer.notifier.notify(
        ChangeSource.BUTTON,
        from_state=AlarmControlPanelState.DISARMED,
        to_state=AlarmControlPanelState.ARMED_AWAY,
    )

    assert len(calls) == 1
    assert calls[0]["service"] == "filtered_service"
    assert calls[0]["data"]["data"]["profile"] == "filtered"


async def test_notify_fallback_to_broader_profile_when_specific_not_matched(hass: HomeAssistant) -> None:
    """Test that broader profile is used when specific profile doesn't match state."""
    from homeassistant.components.alarm_control_panel.const import AlarmControlPanelState

    notify_config: ConfigType = {
        "common": {"service": "notify.default_service"},
        "backstop": {},
        # Specific profile - only matches ARMED_VACATION
        "vacation_only": {
            "service": "notify.vacation_service",
            "state": [AlarmControlPanelState.ARMED_VACATION],
            "data": {"profile": "vacation_only"},
        },
        # Broader profile - matches multiple states including ARMED_AWAY
        "general": {
            "service": "notify.general_service",
            "state": [
                AlarmControlPanelState.ARMED_AWAY,
                AlarmControlPanelState.ARMED_HOME,
                AlarmControlPanelState.ARMED_NIGHT,
            ],
            "data": {"profile": "general"},
        },
    }
    armer = AlarmArmer(hass, TEST_PANEL, notify_enabled=True, notify_profiles=notify_config)
    calls: list[dict[str, Any]] = []

    @callback
    def mock_handler(call: ServiceCall) -> None:
        calls.append({"service": call.service, "data": dict(call.data)})

    hass.services.async_register("notify", "vacation_service", mock_handler)
    hass.services.async_register("notify", "general_service", mock_handler)

    # vacation_only is checked first (more specific) but doesn't match ARMED_AWAY
    # general should be used instead
    assert armer.notifier is not None
    await armer.notifier.notify(
        ChangeSource.BUTTON,
        from_state=AlarmControlPanelState.DISARMED,
        to_state=AlarmControlPanelState.ARMED_AWAY,
    )

    assert len(calls) == 1
    assert calls[0]["service"] == "general_service"
    assert calls[0]["data"]["data"]["profile"] == "general"


async def test_notify_skipped_when_no_action_resolved(hass: HomeAssistant) -> None:
    """Test that notification is skipped when notify_action resolves to None."""
    notifier = Notifier({"backstop": {}}, hass, Mock(spec=AppHealthTracker), notify_action=None)
    await notifier.notify(ChangeSource.BUTTON, message="No action")


async def test_notify_includes_targets_in_service_data(hass: HomeAssistant) -> None:
    """Test that notify_targets are passed as 'target' in service_data."""
    notifier = Notifier(
        {"backstop": {}},
        hass,
        Mock(spec=AppHealthTracker),
        notify_action="notify.test_service",
        notify_targets=["device.abc123"],
    )
    calls: list[dict[str, Any]] = []

    @callback
    def mock_handler(call: ServiceCall) -> None:
        calls.append({"service": call.service, "data": dict(call.data)})

    hass.services.async_register("notify", "test_service", mock_handler)
    await notifier.notify(ChangeSource.BUTTON, message="Target test")

    assert len(calls) == 1
    assert calls[0]["data"]["target"] == ["device.abc123"]


async def test_notify_send_message_uses_entity_id_target(hass: HomeAssistant) -> None:
    """Test that notify.send_message targets via entity_id, not a 'target' data key."""
    notifier = Notifier(
        {"backstop": {}},
        hass,
        Mock(spec=AppHealthTracker),
        notify_action="notify.send_message",
        notify_targets=["notify.mobile_app_test"],
    )
    calls: list[dict[str, Any]] = []

    @callback
    def mock_handler(call: ServiceCall) -> None:
        calls.append({"service": call.service, "data": dict(call.data)})

    hass.services.async_register("notify", "send_message", mock_handler)
    await notifier.notify(ChangeSource.BUTTON, message="Target test")

    assert len(calls) == 1
    assert calls[0]["data"]["entity_id"] == ["notify.mobile_app_test"]
    assert "target" not in calls[0]["data"]


async def test_notify_send_message_without_targets_warns_and_is_skipped(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """notify.send_message has nobody to send to without targets, so say so once and never call it"""
    notifier = Notifier({"backstop": {}}, hass, Mock(spec=AppHealthTracker), notify_action="notify.send_message")
    assert "No notifications will be sent" in caplog.text
    calls: list[ServiceCall] = []
    hass.services.async_register("notify", "send_message", callback(lambda call: calls.append(call)))

    await notifier.notify(ChangeSource.BUTTON, message="Nobody to tell")

    assert calls == []
    notifier.app_health_tracker.record_runtime_error.assert_not_called()  # type: ignore


def test_notify_with_targets_or_other_action_has_no_warning(hass: HomeAssistant, caplog: pytest.LogCaptureFixture) -> None:
    Notifier({}, hass, Mock(spec=AppHealthTracker), notify_action="notify.send_message", notify_targets=["notify.phone"])
    Notifier({}, hass, Mock(spec=AppHealthTracker), notify_action="supernotify.notify")
    Notifier({"backstop": {"target": ["notify.phone"]}}, hass, Mock(spec=AppHealthTracker), notify_action="notify.send_message")
    assert "No notifications will be sent" not in caplog.text


async def test_notify_skipped_when_action_is_empty_string(hass: HomeAssistant) -> None:
    """Test that notification hits else branch when notify_action is empty string."""
    notifier = Notifier({"backstop": {}}, hass, Mock(spec=AppHealthTracker), notify_action="")
    await notifier.notify(ChangeSource.BUTTON, message="Empty action")


async def test_notify_names_time_of_day_sensor(hass: HomeAssistant) -> None:
    """A change by a time of day sensor is described by the sensor's name, not the bare source."""
    armer = AlarmArmer(
        hass, TEST_PANEL, notify_enabled=True, notify_action="notify.test_service", notify_profiles={"backstop": {}}
    )
    messages: list[str] = []

    @callback
    def mock_handler(call: ServiceCall) -> None:
        messages.append(call.data["message"])

    hass.services.async_register("notify", "test_service", mock_handler)
    hass.states.async_set(TEST_PANEL, AlarmControlPanelState.DISARMED)

    await armer.arm(AlarmControlPanelState.ARMED_NIGHT, source=ChangeSource.TOD, change_context={"summary": "Bedtime"})
    await hass.async_block_till_done()
    assert messages == ["Alarm state changed from Disarmed to Armed Night by Bedtime Times of the Day sensor"]

    assert armer.notifier is not None
    await armer.notifier.notify(ChangeSource.TOD, AlarmControlPanelState.ARMED_NIGHT, AlarmControlPanelState.DISARMED)
    await hass.async_block_till_done()
    assert messages[1] == "Alarm state changed from Armed Night to Disarmed by Times of the Day sensor"


async def test_notify_supernotify_action_takes_data_at_top_level(hass: HomeAssistant) -> None:
    """supernotify.notify has no nested data section, and gets the mobile actions by default."""
    notify_config: ConfigType = NOTIFY_SCHEMA({
        "common": {"data": {"priority": "high"}},
        "normal": {"scenario": ["security"]},
    })
    armer = AlarmArmer(
        hass,
        TEST_PANEL,
        notify_enabled=True,
        notify_action="supernotify.notify",
        notify_targets=["person.jey"],
        notify_profiles=notify_config,
    )
    calls: list[dict[str, Any]] = []

    @callback
    def mock_handler(call: ServiceCall) -> None:
        calls.append(dict(call.data))

    hass.services.async_register("supernotify", "notify", mock_handler)
    assert armer.notifier is not None
    await armer.notifier.notify(ChangeSource.CALENDAR, AlarmControlPanelState.DISARMED, AlarmControlPanelState.ARMED_AWAY)
    await hass.async_block_till_done()

    [data] = calls
    assert "data" not in data
    assert data["message"] == "Alarm state changed from Disarmed to Armed Away by Calendar"
    assert data["priority"] == "high"
    assert data["apply_scenarios"] == ["security", "autoarm-armed_away", "autoarm-armed"]
    assert data["target"] == ["person.jey"]
    # titled from the translations, and nothing offered to arm away when that's just been done
    assert data["actions"] == [
        {"title": "Disarm Alarm Panel", "action": "ALARM_PANEL_DISARM", "icon": "sfsymbols:bell.slash"},
        {"title": "Reset Alarm Panel", "action": "ALARM_PANEL_RESET", "icon": "sfsymbols:bell"},
    ]
    assert all("title" not in action for action in SUPERNOTIFY_MOBILE_ACTIONS)


async def test_notify_uses_options_action_over_common_default(hass: HomeAssistant) -> None:
    """The action chosen in the options is used rather than the common profile's default notify.send_message."""
    armer = AlarmArmer(hass, TEST_PANEL, notify_enabled=True, notify_action="notify.chosen", notify_profiles=NOTIFY_SCHEMA({}))
    calls: list[str] = []

    @callback
    def mock_handler(call: ServiceCall) -> None:
        calls.append(call.service)

    hass.services.async_register("notify", "chosen", mock_handler)
    hass.services.async_register("notify", "send_message", mock_handler)
    assert armer.notifier is not None
    await armer.notifier.notify(ChangeSource.CALENDAR, AlarmControlPanelState.DISARMED, AlarmControlPanelState.ARMED_AWAY)
    await hass.async_block_till_done()

    assert calls == ["chosen"]


async def test_notify_profile_service_beats_options_action(hass: HomeAssistant) -> None:
    notify_config: ConfigType = NOTIFY_SCHEMA({"quiet": {"service": "notify.quiet_service", "source": ["calendar"]}})
    armer = AlarmArmer(hass, TEST_PANEL, notify_enabled=True, notify_action="notify.chosen", notify_profiles=notify_config)
    calls: list[str] = []

    @callback
    def mock_handler(call: ServiceCall) -> None:
        calls.append(call.service)

    hass.services.async_register("notify", "chosen", mock_handler)
    hass.services.async_register("notify", "quiet_service", mock_handler)
    assert armer.notifier is not None
    await armer.notifier.notify(ChangeSource.CALENDAR, AlarmControlPanelState.DISARMED, AlarmControlPanelState.ARMED_AWAY)
    await hass.async_block_till_done()

    assert calls == ["quiet_service"]


async def test_notify_from_options_without_yaml(hass: HomeAssistant, mock_notify: Any) -> None:
    """A UI only setup, with no YAML notify profiles, still notifies with the options action."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_ALARM_PANEL: TEST_PANEL},
        options={CONF_NOTIFY_ENABLED: True, CONF_NOTIFY_ACTION: "notify.supernotify", CONF_USE_ALARM_SERVICE: True},
    )
    entry.add_to_hass(hass)
    hass.data[YAML_DATA_KEY] = {}
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    mock_notify.calls.clear()

    notifier = entry.runtime_data.notifier
    assert notifier is not None
    await notifier.notify(ChangeSource.CALENDAR, AlarmControlPanelState.DISARMED, AlarmControlPanelState.ARMED_AWAY)
    await hass.async_block_till_done()

    assert len(mock_notify.calls) == 1


def _supernotify_calls(hass: HomeAssistant) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    hass.services.async_register("supernotify", "notify", callback(lambda call: calls.append(dict(call.data))))
    return calls


@pytest.mark.parametrize(
    ("to_state", "offered"),
    [
        (AlarmControlPanelState.DISARMED, ["ALARM_PANEL_RESET", "ALARM_PANEL_AWAY"]),
        (AlarmControlPanelState.ARMED_AWAY, ["ALARM_PANEL_DISARM", "ALARM_PANEL_RESET"]),
        (AlarmControlPanelState.ARMED_NIGHT, ["ALARM_PANEL_DISARM", "ALARM_PANEL_RESET", "ALARM_PANEL_AWAY"]),
        (None, ["ALARM_PANEL_DISARM", "ALARM_PANEL_RESET", "ALARM_PANEL_AWAY"]),
    ],
)
async def test_mobile_actions_for_the_state_already_set_are_left_out(
    hass: HomeAssistant, to_state: AlarmControlPanelState | None, offered: list[str]
) -> None:
    calls = _supernotify_calls(hass)
    notifier = Notifier({"backstop": {}}, hass, Mock(spec=AppHealthTracker), notify_action="supernotify.notify")

    await notifier.notify(ChangeSource.BUTTON, AlarmControlPanelState.ARMED_HOME, to_state)

    assert [action["action"] for action in calls[0]["actions"]] == offered


async def test_mobile_action_titles_translated(hass: HomeAssistant) -> None:
    hass.config.language = "de"
    calls = _supernotify_calls(hass)
    notifier = Notifier({"backstop": {}}, hass, Mock(spec=AppHealthTracker), notify_action="supernotify.notify")

    await notifier.notify(ChangeSource.BUTTON, AlarmControlPanelState.ARMED_HOME, AlarmControlPanelState.ARMED_NIGHT)

    assert [action["title"] for action in calls[0]["actions"]] == [
        "Alarmzentrale unscharf schalten",
        "Alarmzentrale zurücksetzen",
        "Alarmzentrale scharf abwesend schalten",
    ]


async def test_mobile_actions_from_extra_data_keep_own_titles_and_are_filtered(hass: HomeAssistant) -> None:
    calls = _supernotify_calls(hass)
    actions: list[dict[str, str]] = [
        {"action": "ALARM_PANEL_DISARM", "title": "Stand down"},
        {"action": "ALARM_PANEL_AWAY", "title": "Off out"},
        {"action": "OPEN_GARAGE", "title": "Open the garage"},
    ]
    notifier = Notifier(
        {"backstop": {}},
        hass,
        Mock(spec=AppHealthTracker),
        notify_action="supernotify.notify",
        notify_data={"actions": actions},
    )

    await notifier.notify(ChangeSource.BUTTON, AlarmControlPanelState.ARMED_HOME, AlarmControlPanelState.DISARMED)

    assert calls[0]["actions"] == [
        {"action": "ALARM_PANEL_AWAY", "title": "Off out"},
        {"action": "OPEN_GARAGE", "title": "Open the garage"},
    ]
    assert len(actions) == 3


@pytest.mark.parametrize(
    ("to_state", "scenarios"),
    [
        (AlarmControlPanelState.ARMED_AWAY, ["autoarm-armed_away", "autoarm-armed"]),
        (AlarmControlPanelState.ARMED_NIGHT, ["autoarm-armed_night", "autoarm-armed"]),
        (AlarmControlPanelState.DISARMED, ["autoarm-disarmed"]),
    ],
)
async def test_supernotify_given_scenarios_for_alarm_state(
    hass: HomeAssistant, to_state: AlarmControlPanelState, scenarios: list[str]
) -> None:
    calls = _supernotify_calls(hass)
    notifier = Notifier({"backstop": {}}, hass, Mock(spec=AppHealthTracker), notify_action="supernotify.notify")

    await notifier.notify(ChangeSource.BUTTON, AlarmControlPanelState.ARMED_HOME, to_state)

    assert calls[0]["apply_scenarios"] == scenarios


async def test_no_state_scenarios_without_supernotify_or_state(hass: HomeAssistant) -> None:
    calls = _supernotify_calls(hass)
    plain_calls: list[dict[str, Any]] = []
    hass.services.async_register("notify", "test_service", callback(lambda call: plain_calls.append(dict(call.data))))

    notifier = Notifier({"backstop": {}}, hass, Mock(spec=AppHealthTracker), notify_action="supernotify.notify")
    await notifier.notify(ChangeSource.BUTTON, message="Alarm will be reset")
    notifier = Notifier(
        {"backstop": {}},
        hass,
        Mock(spec=AppHealthTracker),
        notify_action="notify.test_service",
        notify_priorities={"manual": "high"},
    )
    await notifier.notify(ChangeSource.BUTTON, AlarmControlPanelState.ARMED_HOME, AlarmControlPanelState.ARMED_AWAY)

    assert "apply_scenarios" not in calls[0]
    assert plain_calls == [
        {"message": "Alarm state changed from Armed Home to Armed Away by Button", "title": "Alarm now Armed Away"}
    ]


@pytest.mark.parametrize(
    ("source", "priority"),
    [
        (ChangeSource.TOD, "low"),
        (ChangeSource.CALENDAR, "low"),
        (ChangeSource.SUNRISE, "low"),
        (ChangeSource.SUNSET, "low"),
        (ChangeSource.OCCUPANCY, "medium"),
        (ChangeSource.ALARM_PANEL, "high"),
        (ChangeSource.BUTTON, "high"),
        (ChangeSource.STARTUP, None),
    ],
)
async def test_supernotify_priority_by_kind_of_change(hass: HomeAssistant, source: ChangeSource, priority: str | None) -> None:
    calls = _supernotify_calls(hass)
    notifier = Notifier(
        {"backstop": {}},
        hass,
        Mock(spec=AppHealthTracker),
        notify_action="supernotify.notify",
        notify_priorities={"scheduled": "low", "occupancy": "medium", "manual": "high"},
    )

    await notifier.notify(source, AlarmControlPanelState.ARMED_HOME, AlarmControlPanelState.ARMED_AWAY)

    assert calls[0].get("priority") == priority


async def test_priority_in_extra_data_or_profile_is_kept(hass: HomeAssistant) -> None:
    calls = _supernotify_calls(hass)
    notifier = Notifier(
        {"backstop": {}},
        hass,
        Mock(spec=AppHealthTracker),
        notify_action="supernotify.notify",
        notify_data={"priority": "critical"},
        notify_priorities={"manual": "low"},
    )

    await notifier.notify(ChangeSource.BUTTON, AlarmControlPanelState.ARMED_HOME, AlarmControlPanelState.ARMED_AWAY)

    assert calls[0]["priority"] == "critical"


async def test_priorities_from_options(hass: HomeAssistant) -> None:
    calls = _supernotify_calls(hass)
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_ALARM_PANEL: TEST_PANEL},
        options={
            CONF_NOTIFY_ENABLED: True,
            CONF_NOTIFY_ACTION: "supernotify.notify",
            "notify_priority_occupancy": "high",
        },
    )
    entry.add_to_hass(hass)
    hass.data[YAML_DATA_KEY] = {}
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    calls.clear()

    notifier = entry.runtime_data.notifier
    assert notifier is not None
    await notifier.notify(ChangeSource.OCCUPANCY, AlarmControlPanelState.DISARMED, AlarmControlPanelState.ARMED_AWAY)
    await notifier.notify(ChangeSource.BUTTON, AlarmControlPanelState.ARMED_AWAY, AlarmControlPanelState.DISARMED)

    assert [call.get("priority") for call in calls] == ["high", None]


async def test_yaml_notify_section_raises_deprecation_repair(hass: HomeAssistant, caplog: pytest.LogCaptureFixture) -> None:
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {"notify": {"quiet": {"data": {"priority": "low"}}}}})
    await hass.async_block_till_done()

    issue = ir.async_get(hass).async_get_issue(DOMAIN, YAML_NOTIFY_ISSUE)
    assert issue is not None
    assert issue.breaks_in_ha_version == "2027.4.0"
    assert "notify section of the YAML configuration is deprecated" in caplog.text


async def test_yaml_without_notify_section_has_no_deprecation_repair(hass: HomeAssistant) -> None:
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {"transitions": {}}})
    await hass.async_block_till_done()

    assert ir.async_get(hass).async_get_issue(DOMAIN, YAML_NOTIFY_ISSUE) is None
