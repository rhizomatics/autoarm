import pathlib
from pathlib import Path
from typing import Any

import pytest
from homeassistant import config as hass_config
from homeassistant.config import (
    load_yaml_config_file,
)
from homeassistant.const import SERVICE_RELOAD
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from conftest import MockAction
from custom_components.autoarm.config_flow import CONF_PERSON_ENTITIES
from custom_components.autoarm.const import CONF_ALARM_PANEL, DOMAIN

EXAMPLES_ROOT = Path("examples")

examples: list[Path] = [p for p in EXAMPLES_ROOT.iterdir() if p.is_file() and p.name.endswith(".yaml")]


@pytest.mark.parametrize("config_name", examples, ids=lambda v: v.stem)
async def test_examples_import(
    hass: HomeAssistant,
    config_name: Path,
    test_config_calendars: None,  # noqa: ARG001
    mock_notify: MockAction,  # noqa: ARG001
) -> None:
    """Test that example YAML configs trigger import flow and initialize correctly."""
    config: dict[Any, Any] = await hass.async_add_executor_job(load_yaml_config_file, str(config_name))

    for domain_name in config:
        assert await async_setup_component(hass, domain_name, config)

    await hass.async_block_till_done()

    # Import flow should have created a config entry
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].data[CONF_ALARM_PANEL] is not None

    autoarm_init = hass.states.get("binary_sensor.autoarm_initialized")
    assert autoarm_init is not None
    assert autoarm_init.state == "valid"

    hass.bus.async_fire("mobile_app_notification_action", {"action": "ALARM_PANEL_DISARM"})
    await hass.async_block_till_done()

    alarm_panel_entity_id = entries[0].data[CONF_ALARM_PANEL]
    assert hass.states.get(alarm_panel_entity_id).state == "disarmed"  # type: ignore
    assert hass.states.get("sensor.autoarm_failures").state == "0"  # type: ignore

    enquire_config = await hass.services.async_call(
        "autoarm", "enquire_configuration", None, blocking=True, return_response=True
    )
    if config_name.name == "typical.yaml":
        assert enquire_config["notify"]["quiet"]["source"] == ["alarm_panel", "button", "calendar", "sunrise", "sunset"]
        assert enquire_config["notify"]["normal"]["source"] == ["calendar"]
        assert enquire_config["notify"]["common"]["service"] == "notify.supernotify"
        assert enquire_config["notify"]["common"]["supernotify"]
        assert entries[0].options[CONF_PERSON_ENTITIES] == ["person.house_owner", "person.tenant"]
        assert enquire_config["rate_limit"]["period"] == "60 seconds"
    elif config_name.name == "minimal.yaml":
        assert enquire_config["notify"]["quiet"]["source"] == ["alarm_panel", "button", "calendar", "sunrise", "sunset"]
        assert enquire_config["notify"]["common"]["service"] == "notify.send_message"
        assert not enquire_config["notify"]["common"]["supernotify"]


@pytest.mark.parametrize("config_name", examples, ids=lambda v: v.stem)
async def test_examples_reload(
    hass: HomeAssistant,
    config_name: Path,
    test_config_calendars: None,  # noqa: ARG001
    monkeypatch: pytest.MonkeyPatch,
    mock_notify: MockAction,  # noqa: ARG001
) -> None:
    """Test that reload service works after import."""
    config: dict[Any, Any] = await hass.async_add_executor_job(load_yaml_config_file, str(config_name))

    for domain_name in config:
        assert await async_setup_component(hass, domain_name, config)

    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1

    config_path = pathlib.Path(__file__).parent.joinpath("fixtures", "empty_config.yaml").absolute()

    with monkeypatch.context() as m:
        m.setattr(hass_config, "YAML_CONFIG_FILE", str(config_path))
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RELOAD,
            {},
            blocking=True,
        )
        await hass.async_block_till_done()

    autoarm_init = hass.states.get("binary_sensor.autoarm_initialized")
    assert autoarm_init is not None
    assert autoarm_init.state == "valid"
    assert hass.states.get("sensor.autoarm_failures").state == "0"  # type: ignore
