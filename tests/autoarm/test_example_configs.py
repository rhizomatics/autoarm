import pathlib
from pathlib import Path
from typing import Any

import pytest
from homeassistant import config as hass_config
from homeassistant.components.calendar import CalendarEntity
from homeassistant.config import (
    load_yaml_config_file,
)
from homeassistant.const import SERVICE_RELOAD
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from custom_components.autoarm.const import DOMAIN

EXAMPLES_ROOT = Path("examples")

examples: list[Path] = [p for p in EXAMPLES_ROOT.iterdir() if p.is_file() and p.name.endswith(".yaml")]


@pytest.mark.parametrize("config_name", examples, ids=lambda v: v.stem)
@pytest.mark.parametrize(argnames="reload", argvalues=[True, False], ids=["reload", "no-reload"])
async def test_examples(
    hass: HomeAssistant,
    config_name: str,
    reload: bool,
    local_calendar: CalendarEntity,  # noqa: ARG001
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config: dict[Any, Any] = await hass.async_add_executor_job(load_yaml_config_file, str(config_name))

    for domain in config:
        assert await async_setup_component(hass, domain, config)

    await hass.async_block_till_done()

    autoarm_init = hass.states.get("binary_sensor.autoarm_initialized")
    assert autoarm_init is not None
    assert autoarm_init.state == "valid"
    hass.bus.async_fire("mobile_app_notification_action", {"action": "ALARM_PANEL_DISARM"})
    await hass.async_block_till_done()
    assert hass.states.get("alarm_control_panel.testing").state == "disarmed"  # type: ignore
    assert hass.states.get("sensor.autoarm_failures").state == "0"  # type: ignore

    config = await hass.services.async_call("autoarm", "enquire_configuration", None, blocking=True, return_response=True)
    assert config["notify"]["common"]["service"] == "notify.send_message"
    assert config["notify"]["quiet"]["source"] == ["alarm_panel", "button", "calendar", "sunrise", "sunset"]

    if reload:
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
