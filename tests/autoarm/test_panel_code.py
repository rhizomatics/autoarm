import logging
from typing import Any

import pytest
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import MockConfigEntry

from conftest import TEST_PANEL
from custom_components.autoarm.autoarming import PANEL_CODE_ISSUE, AlarmArmer
from custom_components.autoarm.config_flow import CONF_PANEL_CODE, CONF_PANEL_CODE_CLEAR, CONF_USE_ALARM_SERVICE
from custom_components.autoarm.const import CONF_ALARM_PANEL, DOMAIN, ChangeSource
from custom_components.autoarm.crypto import async_decrypt, async_encrypt
from custom_components.autoarm.diagnostics import async_get_config_entry_diagnostics

CODE_WANTED: dict[str, Any] = {"code_arm_required": True, "code_format": "number"}


def _panel_actions(hass: HomeAssistant) -> list[ServiceCall]:
    calls: list[ServiceCall] = []

    @callback
    def handler(call: ServiceCall) -> None:
        calls.append(call)
        hass.states.async_set(TEST_PANEL, "armed_away")

    hass.services.async_register("alarm_control_panel", "alarm_arm_away", handler)
    return calls


async def _save_options(hass: HomeAssistant, entry: MockConfigEntry, advanced: dict[str, Any]) -> Any:
    """Go through the options flow, leaving everything but the advanced section as it is"""
    result = await hass.config_entries.options.async_init(entry.entry_id)
    schema = result["data_schema"]
    assert schema is not None
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_ALARM_PANEL: TEST_PANEL,
            **{str(key): {} for key in schema.schema if str(key).endswith("_options")},
            "advanced_options": advanced,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    return schema.schema["advanced_options"].schema


async def test_code_round_trip(hass: HomeAssistant) -> None:
    token = await async_encrypt(hass, "1234")
    assert "1234" not in token
    assert await async_decrypt(hass, token) == "1234"


async def test_unreadable_code_is_no_code(hass: HomeAssistant, caplog: pytest.LogCaptureFixture) -> None:
    assert await async_decrypt(hass, "not-a-token") is None
    assert "Unable to read the stored alarm panel code" in caplog.text


async def test_options_flow_stores_code_encrypted_and_never_offers_it_back(
    hass: HomeAssistant, setup_autoarm: MockConfigEntry
) -> None:
    entry = setup_autoarm

    fields = await _save_options(hass, entry, {CONF_PANEL_CODE: "1234"})
    # nothing to remove until there's a code
    assert CONF_PANEL_CODE_CLEAR not in fields.schema
    token = entry.options[CONF_PANEL_CODE]
    assert "1234" not in token
    assert await async_decrypt(hass, token) == "1234"
    assert CONF_PANEL_CODE_CLEAR not in entry.options
    # and the reloaded entry has it to use
    assert entry.runtime_data._panel_code == "1234"

    # left blank, the stored code stays, and isn't put in the form
    fields = await _save_options(hass, entry, {})
    assert entry.options[CONF_PANEL_CODE] == token
    code_field = next(key for key in fields.schema if key == CONF_PANEL_CODE)
    assert not code_field.description
    assert CONF_PANEL_CODE not in fields({})
    assert fields({})[CONF_PANEL_CODE_CLEAR] is False

    await _save_options(hass, entry, {CONF_PANEL_CODE_CLEAR: True})
    assert CONF_PANEL_CODE not in entry.options
    assert entry.runtime_data._panel_code is None


async def test_code_given_to_panel_actions_and_kept_out_of_logs(hass: HomeAssistant, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    calls = _panel_actions(hass)
    hass.states.async_set(TEST_PANEL, "disarmed")
    armer = AlarmArmer(hass, TEST_PANEL, use_alarm_service=True, panel_code="1234")

    await armer.arm("armed_away", source=ChangeSource.BUTTON)  # type: ignore
    await hass.async_block_till_done()

    assert calls[0].data["code"] == "1234"
    assert "1234" not in "".join(r.getMessage() for r in caplog.records if r.name.startswith("custom_components.autoarm"))


async def test_no_code_given_when_none_set(hass: HomeAssistant) -> None:
    calls = _panel_actions(hass)
    hass.states.async_set(TEST_PANEL, "disarmed")
    armer = AlarmArmer(hass, TEST_PANEL, use_alarm_service=True)

    await armer.arm("armed_away", source=ChangeSource.BUTTON)  # type: ignore

    assert "code" not in calls[0].data


async def test_repair_raised_when_panel_wants_a_code(hass: HomeAssistant, issue_registry: ir.IssueRegistry) -> None:
    hass.states.async_set(TEST_PANEL, "disarmed", CODE_WANTED)
    armer = AlarmArmer(hass, TEST_PANEL, use_alarm_service=True)
    armer.initialize_alarm_panel()

    issue = issue_registry.async_get_issue(DOMAIN, PANEL_CODE_ISSUE)
    assert issue is not None
    assert issue.translation_placeholders == {"panel": TEST_PANEL}

    # and withdrawn when the panel stops wanting one
    hass.states.async_set(TEST_PANEL, "disarmed", {})
    await hass.async_block_till_done()
    assert issue_registry.async_get_issue(DOMAIN, PANEL_CODE_ISSUE) is None
    armer.shutdown()


async def test_repair_raised_once_panel_turns_up(hass: HomeAssistant, issue_registry: ir.IssueRegistry) -> None:
    armer = AlarmArmer(hass, TEST_PANEL, use_alarm_service=True)
    armer.initialize_alarm_panel()
    assert issue_registry.async_get_issue(DOMAIN, PANEL_CODE_ISSUE) is None

    hass.states.async_set(TEST_PANEL, "disarmed", CODE_WANTED)
    await hass.async_block_till_done()

    assert issue_registry.async_get_issue(DOMAIN, PANEL_CODE_ISSUE) is not None
    armer.shutdown()


@pytest.mark.parametrize(("use_alarm_service", "panel_code"), [(True, "1234"), (False, None)])
async def test_no_repair_with_a_code_or_setting_state_directly(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry, use_alarm_service: bool, panel_code: str | None
) -> None:
    hass.states.async_set(TEST_PANEL, "disarmed", CODE_WANTED)
    armer = AlarmArmer(hass, TEST_PANEL, use_alarm_service=use_alarm_service, panel_code=panel_code)
    armer.initialize_alarm_panel()

    assert issue_registry.async_get_issue(DOMAIN, PANEL_CODE_ISSUE) is None
    armer.shutdown()


async def test_no_repair_with_home_assistant_default_code(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry, entity_registry: er.EntityRegistry
) -> None:
    domain, object_id = TEST_PANEL.split(".")
    entity_registry.async_get_or_create(domain, "test", "panel", suggested_object_id=object_id)
    entity_registry.async_update_entity_options(TEST_PANEL, domain, {"default_code": "4321"})
    hass.states.async_set(TEST_PANEL, "disarmed", CODE_WANTED)
    armer = AlarmArmer(hass, TEST_PANEL, use_alarm_service=True)
    armer.initialize_alarm_panel()

    assert issue_registry.async_get_issue(DOMAIN, PANEL_CODE_ISSUE) is None
    armer.shutdown()


async def test_diagnostics_redact_code(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_ALARM_PANEL: TEST_PANEL},
        options={CONF_USE_ALARM_SERVICE: True, CONF_PANEL_CODE: await async_encrypt(hass, "1234")},
    )

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert result["entry_options"] == {CONF_USE_ALARM_SERVICE: True, CONF_PANEL_CODE: "**REDACTED**"}
