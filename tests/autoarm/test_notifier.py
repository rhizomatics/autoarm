from homeassistant.core import HomeAssistant

from custom_components.autoarm.autoarming import AlarmArmer
from custom_components.autoarm.const import ChangeSource

TEST_PANEL = "alarm_control_panel.test_panel"


async def test_notify_skipped_when_no_service(hass: HomeAssistant) -> None:
    """Test that notification is skipped when no service is configured."""
    armer = AlarmArmer(hass, TEST_PANEL, notify={})
    calls: list[dict] = []

    def mock_handler(call) -> None:  # noqa: ANN001, RUF029, RUF100
        calls.append({"service": call.service, "data": dict(call.data)})

    hass.services.async_register("notify", "test_service", mock_handler)
    await armer.notifier.notify(ChangeSource.BUTTON, message="Test message")
    # No service configured, so handler should not be called
    assert len(calls) == 0


async def test_notify_calls_service(hass: HomeAssistant) -> None:
    """Test that notify calls hass.services.async_call with correct parameters."""
    notify_config = {
        "common": {"service": "notify.test_service"},
        "backstop": {},
    }
    armer = AlarmArmer(hass, TEST_PANEL, notify=notify_config)
    calls: list[dict] = []

    async def mock_handler(call) -> None:  # noqa: ANN001, RUF029, RUF100
        calls.append({"service": call.service, "data": dict(call.data)})

    hass.services.async_register("notify", "test_service", mock_handler)
    await armer.notifier.notify(ChangeSource.BUTTON, message="Test message")

    assert len(calls) == 1
    assert calls[0]["data"]["message"] == "Test message"
    assert calls[0]["data"]["title"] == "Alarm Panel Change"


async def test_notify_with_custom_title(hass: HomeAssistant) -> None:
    """Test that notify uses custom title when provided."""
    notify_config = {
        "common": {"service": "notify.test_service"},
        "backstop": {},
    }
    armer = AlarmArmer(hass, TEST_PANEL, notify=notify_config)
    calls: list[dict] = []

    async def mock_handler(call) -> None:  # noqa: ANN001, RUF029, RUF100
        calls.append({"service": call.service, "data": dict(call.data)})

    hass.services.async_register("notify", "test_service", mock_handler)
    await armer.notifier.notify(ChangeSource.BUTTON, message="Test message", title="Custom Title")

    assert len(calls) == 1
    assert calls[0]["data"]["title"] == "Custom Title"


async def test_notify_profile_merging(hass: HomeAssistant) -> None:
    """Test that selected profile is merged with common profile."""
    notify_config = {
        "common": {"service": "notify.common_service", "data": {"priority": "low"}},
        "quiet": {"service": "notify.quiet_service", "source": [ChangeSource.BUTTON], "data": {"sound": "none"}},
    }
    armer = AlarmArmer(hass, TEST_PANEL, notify=notify_config)
    calls: list[dict] = []

    async def mock_handler(call) -> None:  # noqa: ANN001, RUF029, RUF100
        calls.append({"service": call.service, "data": dict(call.data)})

    hass.services.async_register("notify", "quiet_service", mock_handler)
    await armer.notifier.notify(ChangeSource.BUTTON, message="Test message")

    assert len(calls) == 1
    # Data should have both priority from common and sound from quiet
    assert calls[0]["data"]["data"]["priority"] == "low"
    assert calls[0]["data"]["data"]["sound"] == "none"


async def test_notify_source_replacement(hass: HomeAssistant) -> None:
    """Test that source is set in data when data['source'] is None."""
    notify_config = {
        "common": {"service": "notify.test_service", "data": {"source": None}},
        "backstop": {},
    }
    armer = AlarmArmer(hass, TEST_PANEL, notify=notify_config)
    calls: list[dict] = []

    async def mock_handler(call) -> None:  # noqa: ANN001, RUF029, RUF100
        calls.append({"service": call.service, "data": dict(call.data)})

    hass.services.async_register("notify", "test_service", mock_handler)
    await armer.notifier.notify(ChangeSource.ALARM_PANEL, message="Test message")

    assert len(calls) == 1
    assert calls[0]["data"]["data"]["source"] == ChangeSource.ALARM_PANEL


async def test_notify_supernotify_scenario(hass: HomeAssistant) -> None:
    """Test that supernotify scenarios are added to data when configured."""
    notify_config = {
        "common": {"service": "notify.test_service", "supernotify": True, "scenario": ["urgent"]},
        "backstop": {},
    }
    armer = AlarmArmer(hass, TEST_PANEL, notify=notify_config)
    calls: list[dict] = []

    async def mock_handler(call) -> None:  # noqa: ANN001, RUF029, RUF100
        calls.append({"service": call.service, "data": dict(call.data)})

    hass.services.async_register("notify", "test_service", mock_handler)
    await armer.notifier.notify(ChangeSource.BUTTON, message="Test message")

    assert len(calls) == 1
    assert calls[0]["data"]["data"]["apply_scenarios"] == ["urgent"]


async def test_notify_exception_records_runtime_error(hass: HomeAssistant) -> None:
    """Test that exceptions during notify call record_runtime_error."""
    # Use a non-existent service to trigger ServiceNotFound exception
    notify_config = {
        "common": {"service": "notify.nonexistent_service"},
        "backstop": {},
    }
    armer = AlarmArmer(hass, TEST_PANEL, notify=notify_config)
    initial_failures = armer.app_health_tracker.failures

    # Don't register the service - this should cause an exception
    await armer.notifier.notify(ChangeSource.BUTTON, message="Test message")

    assert armer.app_health_tracker.failures == initial_failures + 1


async def test_notify_strips_notify_prefix_from_service(hass: HomeAssistant) -> None:
    """Test that 'notify.' prefix is stripped from service name."""
    notify_config = {
        "common": {"service": "notify.mobile_app"},
        "backstop": {},
    }
    armer = AlarmArmer(hass, TEST_PANEL, notify=notify_config)
    calls: list[dict] = []

    async def mock_handler(call) -> None:  # noqa: ANN001, RUF029, RUF100
        calls.append({"service": call.service, "data": dict(call.data)})

    hass.services.async_register("notify", "mobile_app", mock_handler)
    await armer.notifier.notify(ChangeSource.BUTTON, message="Test message")

    assert len(calls) == 1
    assert calls[0]["service"] == "mobile_app"


async def test_notify_selects_profile_by_from_state(hass: HomeAssistant) -> None:
    """Test that profile is selected when from_state matches."""
    from homeassistant.components.alarm_control_panel.const import AlarmControlPanelState

    notify_config = {
        "common": {"service": "notify.default_service"},
        "away_alert": {
            "service": "notify.away_service",
            "state": [AlarmControlPanelState.ARMED_AWAY],
            "data": {"priority": "high"},
        },
    }
    armer = AlarmArmer(hass, TEST_PANEL, notify=notify_config)
    calls: list[dict] = []

    async def mock_handler(call) -> None:  # noqa: ANN001, RUF029, RUF100
        calls.append({"service": call.service, "data": dict(call.data)})

    hass.services.async_register("notify", "away_service", mock_handler)
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

    notify_config = {
        "common": {"service": "notify.default_service"},
        "vacation_alert": {
            "service": "notify.vacation_service",
            "state": [AlarmControlPanelState.ARMED_VACATION],
            "data": {"channel": "vacation"},
        },
    }
    armer = AlarmArmer(hass, TEST_PANEL, notify=notify_config)
    calls: list[dict] = []

    async def mock_handler(call) -> None:  # noqa: ANN001, RUF029, RUF100
        calls.append({"service": call.service, "data": dict(call.data)})

    hass.services.async_register("notify", "vacation_service", mock_handler)
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

    notify_config = {
        "common": {"service": "notify.default_service"},
        "away_only": {
            "service": "notify.away_service",
            "state": [AlarmControlPanelState.ARMED_AWAY],
            "data": {"tag": "away"},
        },
    }
    armer = AlarmArmer(hass, TEST_PANEL, notify=notify_config)
    calls: list[dict] = []

    async def mock_handler(call) -> None:  # noqa: ANN001, RUF029, RUF100
        calls.append({"service": call.service, "data": dict(call.data)})

    hass.services.async_register("notify", "default_service", mock_handler)
    hass.services.async_register("notify", "away_service", mock_handler)
    await armer.notifier.notify(
        ChangeSource.BUTTON,
        from_state=AlarmControlPanelState.ARMED_HOME,
        to_state=AlarmControlPanelState.DISARMED,
    )

    assert len(calls) == 0


async def test_notify_skips_profile_when_source_not_matched(hass: HomeAssistant) -> None:
    """Test that no notification is sent when no profile matches the source."""
    notify_config = {
        "common": {"service": "notify.default_service"},
        "button_only": {
            "service": "notify.button_service",
            "source": [ChangeSource.BUTTON],
            "data": {"tag": "button"},
        },
    }
    armer = AlarmArmer(hass, TEST_PANEL, notify=notify_config)
    calls: list[dict] = []

    async def mock_handler(call) -> None:  # noqa: ANN001, RUF029, RUF100
        calls.append({"service": call.service, "data": dict(call.data)})

    hass.services.async_register("notify", "default_service", mock_handler)
    hass.services.async_register("notify", "button_service", mock_handler)
    await armer.notifier.notify(ChangeSource.CALENDAR, message="Test message")

    assert len(calls) == 0


async def test_notify_auto_generates_title_from_to_state(hass: HomeAssistant) -> None:
    """Test that title is auto-generated from to_state when not provided."""
    from homeassistant.components.alarm_control_panel.const import AlarmControlPanelState

    notify_config = {
        "common": {"service": "notify.test_service"},
        "backstop": {},
    }
    armer = AlarmArmer(hass, TEST_PANEL, notify=notify_config)
    calls: list[dict] = []

    async def mock_handler(call) -> None:  # noqa: ANN001, RUF029, RUF100
        calls.append({"service": call.service, "data": dict(call.data)})

    hass.services.async_register("notify", "test_service", mock_handler)
    await armer.notifier.notify(
        ChangeSource.BUTTON,
        to_state=AlarmControlPanelState.ARMED_AWAY,
    )

    assert len(calls) == 1
    assert "armed_away" in calls[0]["data"]["title"].lower()


async def test_notify_auto_generates_message_from_states(hass: HomeAssistant) -> None:
    """Test that message is auto-generated from from_state and to_state."""
    from homeassistant.components.alarm_control_panel.const import AlarmControlPanelState

    notify_config = {
        "common": {"service": "notify.test_service"},
        "backstop": {},
    }
    armer = AlarmArmer(hass, TEST_PANEL, notify=notify_config)
    calls: list[dict] = []

    async def mock_handler(call) -> None:  # noqa: ANN001, RUF029, RUF100
        calls.append({"service": call.service, "data": dict(call.data)})

    hass.services.async_register("notify", "test_service", mock_handler)
    await armer.notifier.notify(
        ChangeSource.ALARM_PANEL,
        from_state=AlarmControlPanelState.ARMED_HOME,
        to_state=AlarmControlPanelState.ARMED_AWAY,
    )

    assert len(calls) == 1
    message = calls[0]["data"]["message"]
    assert message == "Alarm state changed from armed_home to armed_away by Alarm_panel"


async def test_notify_profile_name_replacement(hass: HomeAssistant) -> None:
    """Test that profile name is set in data when data['profile'] is None."""
    notify_config = {
        "common": {"service": "notify.test_service", "data": {"profile": None}},
        "urgent": {"service": "notify.test_service", "source": [ChangeSource.BUTTON]},
    }
    armer = AlarmArmer(hass, TEST_PANEL, notify=notify_config)
    calls: list[dict] = []

    async def mock_handler(call) -> None:  # noqa: ANN001, RUF029, RUF100
        calls.append({"service": call.service, "data": dict(call.data)})

    hass.services.async_register("notify", "test_service", mock_handler)
    await armer.notifier.notify(ChangeSource.BUTTON, message="Test message")

    assert len(calls) == 1
    assert calls[0]["data"]["data"]["profile"] == "urgent"


async def test_notify_common_profile_not_selected_as_match(hass: HomeAssistant) -> None:
    """Test that common profile is skipped during profile selection."""
    notify_config = {
        "common": {"service": "notify.common_service", "source": [ChangeSource.BUTTON]},
    }
    armer = AlarmArmer(hass, TEST_PANEL, notify=notify_config)
    calls: list[dict] = []

    async def mock_handler(call) -> None:  # noqa: ANN001, RUF029, RUF100
        calls.append({"service": call.service, "data": dict(call.data)})

    hass.services.async_register("notify", "common_service", mock_handler)
    # common is not selected as a matching profile, and with no other profiles
    # no notification is sent
    await armer.notifier.notify(ChangeSource.BUTTON, message="Test message")

    assert len(calls) == 0


async def test_notify_selects_profile_with_both_source_and_state(hass: HomeAssistant) -> None:
    """Test profile selection when both source and state filters are configured."""
    from homeassistant.components.alarm_control_panel.const import AlarmControlPanelState

    notify_config = {
        "common": {"service": "notify.default_service"},
        "button_away": {
            "service": "notify.special_service",
            "source": [ChangeSource.BUTTON],
            "state": [AlarmControlPanelState.ARMED_AWAY],
            "data": {"special": True},
        },
    }
    armer = AlarmArmer(hass, TEST_PANEL, notify=notify_config)
    calls: list[dict] = []

    async def mock_handler(call) -> None:  # noqa: ANN001, RUF029, RUF100
        calls.append({"service": call.service, "data": dict(call.data)})

    hass.services.async_register("notify", "special_service", mock_handler)
    hass.services.async_register("notify", "default_service", mock_handler)

    # Both source and state match
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

    notify_config = {
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
    armer = AlarmArmer(hass, TEST_PANEL, notify=notify_config)
    calls: list[dict] = []

    async def mock_handler(call) -> None:  # noqa: ANN001, RUF029, RUF100
        calls.append({"service": call.service, "data": dict(call.data)})

    hass.services.async_register("notify", "broad_service", mock_handler)
    hass.services.async_register("notify", "specific_service", mock_handler)

    # Both profiles match ARMED_AWAY, but specific should win due to fewer states
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

    notify_config = {
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
    armer = AlarmArmer(hass, TEST_PANEL, notify=notify_config)
    calls: list[dict] = []

    async def mock_handler(call) -> None:  # noqa: ANN001, RUF029, RUF100
        calls.append({"service": call.service, "data": dict(call.data)})

    hass.services.async_register("notify", "catch_all_service", mock_handler)
    hass.services.async_register("notify", "filtered_service", mock_handler)

    # Both profiles match source, but filtered should win (has state filter)
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

    notify_config = {
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
    armer = AlarmArmer(hass, TEST_PANEL, notify=notify_config)
    calls: list[dict] = []

    async def mock_handler(call) -> None:  # noqa: ANN001, RUF029, RUF100
        calls.append({"service": call.service, "data": dict(call.data)})

    hass.services.async_register("notify", "vacation_service", mock_handler)
    hass.services.async_register("notify", "general_service", mock_handler)

    # vacation_only is checked first (more specific) but doesn't match ARMED_AWAY
    # general should be used instead
    await armer.notifier.notify(
        ChangeSource.BUTTON,
        from_state=AlarmControlPanelState.DISARMED,
        to_state=AlarmControlPanelState.ARMED_AWAY,
    )

    assert len(calls) == 1
    assert calls[0]["service"] == "general_service"
    assert calls[0]["data"]["data"]["profile"] == "general"
