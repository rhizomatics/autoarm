import pathlib
from typing import Any

import pytest
from homeassistant import config as hass_config
from homeassistant.config import (
    load_yaml_config_file,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import SERVICE_RELOAD
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from conftest import MockAction
from custom_components.autoarm.config_flow import CONF_PERSON_ENTITIES
from custom_components.autoarm.const import CONF_ALARM_PANEL, DOMAIN

EXAMPLES_ROOT = pathlib.Path("examples")
RELOAD_FIXTURE = pathlib.Path(__file__).parent.joinpath("fixtures", "empty_config.yaml").absolute()


@pytest.fixture
def preconfigured_autoarm(hass: HomeAssistant) -> ConfigEntry:
    existing = MockConfigEntry(
        domain=DOMAIN,
        title="Auto Arm",
        data={CONF_ALARM_PANEL: "alarm_control_panel.testing"},
        unique_id=DOMAIN,
    )
    existing.add_to_hass(hass)
    return existing


async def _reload_and_verify(hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch) -> None:
    """Reload autoarm with the empty_config fixture and verify it stays valid."""
    with monkeypatch.context() as m:
        m.setattr(hass_config, "YAML_CONFIG_FILE", str(RELOAD_FIXTURE))
        await hass.services.async_call(DOMAIN, SERVICE_RELOAD, {}, blocking=True)
        await hass.async_block_till_done()

    autoarm_init = hass.states.get("binary_sensor.autoarm_initialized")
    assert autoarm_init is not None
    assert autoarm_init.state == "valid"
    assert hass.states.get("sensor.autoarm_failures").state == "0"  # type: ignore


async def test_empty_config_installed(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
    test_config_calendars: None,  # noqa: ARG001
    mock_notify: MockAction,  # noqa: ARG001
    alarm_panel: str,  # noqa: ARG001
    preconfigured_autoarm: ConfigEntry,  # noqa: ARG001
) -> None:
    """Test empty YAML config with pre-existing ConfigEntry initializes correctly."""
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].data[CONF_ALARM_PANEL] == "alarm_control_panel.testing"

    autoarm_init = hass.states.get("binary_sensor.autoarm_initialized")
    assert autoarm_init is not None
    assert autoarm_init.state == "valid"
    assert hass.states.get("sensor.autoarm_failures").state == "0"  # type: ignore

    await _reload_and_verify(hass, monkeypatch)


async def test_supplemental_config_installed(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
    test_config_calendars: None,  # noqa: ARG001
    mock_notify: MockAction,  # noqa: ARG001
    alarm_panel: str,  # noqa: ARG001
    preconfigured_autoarm: ConfigEntry,  # noqa: ARG001
) -> None:
    """Test supplemental YAML config with pre-existing ConfigEntry picks up YAML-only settings."""
    config: dict[Any, Any] = await hass.async_add_executor_job(load_yaml_config_file, str(EXAMPLES_ROOT / "typical.yaml"))
    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].data[CONF_ALARM_PANEL] == "alarm_control_panel.testing"

    autoarm_init = hass.states.get("binary_sensor.autoarm_initialized")
    assert autoarm_init is not None
    assert autoarm_init.state == "valid"

    hass.bus.async_fire("mobile_app_notification_action", {"action": "ALARM_PANEL_DISARM"})
    await hass.async_block_till_done()

    assert hass.states.get("alarm_control_panel.testing").state == "disarmed"  # type: ignore
    assert hass.states.get("sensor.autoarm_failures").state == "0"  # type: ignore

    enquire_config = await hass.services.async_call(
        "autoarm", "enquire_configuration", None, blocking=True, return_response=True
    )
    assert enquire_config["notify"]["quiet"]["source"] == ["alarm_panel", "button", "calendar", "sunrise", "sunset"]
    assert enquire_config["notify"]["normal"]["source"] == ["calendar"]
    assert enquire_config["notify"]["common"]["service"] == "notify.supernotify"
    assert enquire_config["notify"]["common"]["supernotify"]
    assert enquire_config["rate_limit"]["period"] == "60 seconds"

    await _reload_and_verify(hass, monkeypatch)


async def test_legacy_config_installed(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
    test_config_calendars: None,  # noqa: ARG001
    mock_notify: MockAction,  # noqa: ARG001
    alarm_panel: str,  # noqa: ARG001
    preconfigured_autoarm: ConfigEntry,  # noqa: ARG001
) -> None:
    """Test legacy full YAML config with pre-existing ConfigEntry ignores YAML core settings."""
    config: dict[Any, Any] = await hass.async_add_executor_job(load_yaml_config_file, str(EXAMPLES_ROOT / "legacy.yaml"))
    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    # Pre-existing entry kept; import skipped since ConfigEntry already exists
    assert entries[0].data[CONF_ALARM_PANEL] == "alarm_control_panel.testing"

    autoarm_init = hass.states.get("binary_sensor.autoarm_initialized")
    assert autoarm_init is not None
    assert autoarm_init.state == "valid"

    hass.bus.async_fire("mobile_app_notification_action", {"action": "ALARM_PANEL_DISARM"})
    await hass.async_block_till_done()

    assert hass.states.get("alarm_control_panel.testing").state == "disarmed"  # type: ignore
    assert hass.states.get("sensor.autoarm_failures").state == "0"  # type: ignore

    enquire_config = await hass.services.async_call(
        "autoarm", "enquire_configuration", None, blocking=True, return_response=True
    )
    assert enquire_config["notify"]["quiet"]["source"] == ["alarm_panel", "button", "calendar", "sunrise", "sunset"]
    assert enquire_config["notify"]["normal"]["source"] == ["calendar"]
    assert enquire_config["notify"]["common"]["service"] == "notify.supernotify"
    assert enquire_config["notify"]["common"]["supernotify"]
    assert enquire_config["rate_limit"]["period"] == "60 seconds"

    await _reload_and_verify(hass, monkeypatch)


async def test_legacy_config_fresh_install(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
    test_config_calendars: None,  # noqa: ARG001
    mock_notify: MockAction,  # noqa: ARG001
    alarm_panel: str,  # noqa: ARG001
) -> None:
    """Test legacy full YAML config without ConfigEntry triggers import flow."""
    config: dict[Any, Any] = await hass.async_add_executor_job(load_yaml_config_file, str(EXAMPLES_ROOT / "legacy.yaml"))
    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    # Import flow should have created entry from YAML
    assert entries[0].data[CONF_ALARM_PANEL] == "alarm_control_panel.testing"
    assert entries[0].options[CONF_PERSON_ENTITIES] == ["person.house_owner", "person.tenant"]

    autoarm_init = hass.states.get("binary_sensor.autoarm_initialized")
    assert autoarm_init is not None
    assert autoarm_init.state == "valid"

    hass.bus.async_fire("mobile_app_notification_action", {"action": "ALARM_PANEL_DISARM"})
    await hass.async_block_till_done()

    assert hass.states.get("alarm_control_panel.testing").state == "disarmed"  # type: ignore
    assert hass.states.get("sensor.autoarm_failures").state == "0"  # type: ignore

    enquire_config = await hass.services.async_call(
        "autoarm", "enquire_configuration", None, blocking=True, return_response=True
    )
    assert enquire_config["notify"]["quiet"]["source"] == ["alarm_panel", "button", "calendar", "sunrise", "sunset"]
    assert enquire_config["notify"]["normal"]["source"] == ["calendar"]
    assert enquire_config["notify"]["common"]["service"] == "notify.supernotify"
    assert enquire_config["notify"]["common"]["supernotify"]
    assert enquire_config["rate_limit"]["period"] == "60 seconds"

    await _reload_and_verify(hass, monkeypatch)
