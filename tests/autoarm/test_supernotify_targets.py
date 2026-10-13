"""The target and delivery fields for notifications, as in supernotify.notify itself"""

from typing import Any
from unittest.mock import Mock

from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse, callback
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.autoarm.config_flow import (
    CONF_NOTIFY_CUSTOM_TARGET,
    CONF_NOTIFY_DELIVERIES,
    CONF_NOTIFY_TARGET,
    CONF_NOTIFY_TARGETS,
)
from custom_components.autoarm.const import ChangeSource
from custom_components.autoarm.helpers import AppHealthTracker
from custom_components.autoarm.notifier import Notifier
from custom_components.autoarm.supernotify_api import deliveries


def _capture(hass: HomeAssistant, domain: str, action: str) -> list[ServiceCall]:
    calls: list[ServiceCall] = []
    hass.services.async_register(domain, action, callback(lambda call: calls.append(call)))
    return calls


def _respond(hass: HomeAssistant, action: str, response: dict[str, Any]) -> None:
    async def handler(_call: ServiceCall) -> ServiceResponse:
        return response

    hass.services.async_register("supernotify", action, handler, supports_response=SupportsResponse.ONLY)


def _notifier(hass: HomeAssistant, action: str = "supernotify.notify", **kwargs: Any) -> Notifier:
    return Notifier({"backstop": {}}, hass, Mock(spec=AppHealthTracker), notify_action=action, **kwargs)


def _notify_fields(result: Any) -> dict[Any, Any]:
    data_schema = result["data_schema"]
    assert data_schema is not None
    return data_schema.schema["notify_options"].schema.schema  # type: ignore[no-any-return]


async def test_deliveries_found_from_switches_and_enquiries(hass: HomeAssistant) -> None:
    hass.states.async_set("switch.supernotify_delivery_chime", "on", {"name": "chime_alert", "transport": "chime"})
    hass.states.async_set("switch.unrelated", "on", {"name": "not_a_delivery"})
    _respond(hass, "enquire_implicit_deliveries", {"mobile_push": ["DEFAULT_mobile_push"]})
    _respond(hass, "enquire_configuration", {"delivery": {"plain_email": {"transport": "email"}}})

    assert await deliveries(hass) == ["DEFAULT_mobile_push", "chime_alert", "plain_email"]


async def test_deliveries_with_older_supernotify(hass: HomeAssistant) -> None:
    hass.states.async_set("switch.supernotify_delivery_chime", "on", {"name": "chime_alert", "transport": "chime"})

    assert await deliveries(hass) == ["chime_alert"]


async def test_options_offer_supernotify_fields(hass: HomeAssistant, setup_autoarm: MockConfigEntry) -> None:
    hass.services.async_register("supernotify", "notify", lambda _call: None)
    hass.states.async_set("switch.supernotify_delivery_chime", "on", {"name": "chime_alert", "transport": "chime"})
    hass.config_entries.async_update_entry(
        setup_autoarm,
        options={**setup_autoarm.options, CONF_NOTIFY_TARGETS: ["joe@example.com"], CONF_NOTIFY_DELIVERIES: ["gone"]},
    )
    await hass.async_block_till_done()

    fields = _notify_fields(await hass.config_entries.options.async_init(setup_autoarm.entry_id))

    assert CONF_NOTIFY_TARGET in fields
    assert CONF_NOTIFY_TARGETS not in fields
    # targets from before the fields were split are carried over as custom ones
    custom_target = next(key for key in fields if key == CONF_NOTIFY_CUSTOM_TARGET)
    assert custom_target.default() == ["joe@example.com"]
    delivery_selector = fields[CONF_NOTIFY_DELIVERIES]
    assert delivery_selector.config["options"] == ["chime_alert"]
    # one no longer in Supernotify doesn't stop the options being saved
    assert delivery_selector(["gone", "chime_alert"]) == ["gone", "chime_alert"]
    for kind, default in (("scheduled", "low"), ("occupancy", "medium"), ("manual", "medium")):
        priority = next(key for key in fields if key == f"notify_priority_{kind}")
        assert priority.default() == default
        assert fields[priority].config["options"] == ["critical", "high", "medium", "low", "minimum"]


async def test_options_without_supernotify_keep_plain_targets(hass: HomeAssistant, setup_autoarm: MockConfigEntry) -> None:
    fields = _notify_fields(await hass.config_entries.options.async_init(setup_autoarm.entry_id))

    assert CONF_NOTIFY_TARGETS in fields
    assert not {CONF_NOTIFY_TARGET, CONF_NOTIFY_CUSTOM_TARGET, CONF_NOTIFY_DELIVERIES} & set(fields)
    assert not any(str(field).startswith("notify_priority_") for field in fields)


async def test_supernotify_given_targets_and_deliveries(hass: HomeAssistant) -> None:
    calls = _capture(hass, "supernotify", "notify")
    notifier = _notifier(
        hass,
        notify_targets=["joe@example.com"],
        notify_target={"entity_id": ["person.joe"], "area_id": ["hall"]},
        notify_custom_target=["joe@example.com", "+441234567890"],
        notify_deliveries=["chime_alert"],
    )

    await notifier.notify(ChangeSource.BUTTON, message="Testing")

    data = calls[0].data
    assert data["target"] == {"entity_id": ["person.joe"], "area_id": ["hall"]}
    assert data["custom_target"] == ["joe@example.com", "+441234567890"]
    assert data["delivery"] == ["chime_alert"]
    assert data["delivery_selection"] == "explicit"


async def test_supernotify_typed_targets_alone_sent_as_before(hass: HomeAssistant) -> None:
    calls = _capture(hass, "supernotify", "notify")
    notifier = _notifier(hass, notify_targets=["joe@example.com"])

    await notifier.notify(ChangeSource.BUTTON, message="Testing")

    assert calls[0].data["target"] == ["joe@example.com"]
    assert not {"custom_target", "delivery", "delivery_selection"} & set(calls[0].data)


async def test_deliveries_in_extra_data_or_profile_are_kept(hass: HomeAssistant) -> None:
    calls = _capture(hass, "supernotify", "notify")
    notifier = _notifier(hass, notify_deliveries=["chime_alert"], notify_data={"delivery": ["plain_email"]})

    await notifier.notify(ChangeSource.BUTTON, message="Testing")

    assert calls[0].data["delivery"] == ["plain_email"]
    assert "delivery_selection" not in calls[0].data


async def test_profile_targets_replace_those_in_options(hass: HomeAssistant) -> None:
    calls = _capture(hass, "supernotify", "notify")
    notifier = Notifier(
        {"backstop": {"target": ["person.jane"]}},
        hass,
        Mock(spec=AppHealthTracker),
        notify_action="supernotify.notify",
        notify_target={"entity_id": ["person.joe"]},
        notify_custom_target=["joe@example.com"],
    )

    await notifier.notify(ChangeSource.BUTTON, message="Testing")

    assert calls[0].data["target"] == ["person.jane"]
    assert "custom_target" not in calls[0].data


async def test_send_message_uses_picked_and_typed_entities(hass: HomeAssistant) -> None:
    calls = _capture(hass, "notify", "send_message")
    notifier = _notifier(
        hass,
        "notify.send_message",
        notify_target={"entity_id": "notify.joe_phone"},
        notify_custom_target=["notify.jane_phone"],
        notify_deliveries=["chime_alert"],
    )

    await notifier.notify(ChangeSource.BUTTON, message="Testing")

    assert calls[0].data["entity_id"] == ["notify.joe_phone", "notify.jane_phone"]
    assert "delivery" not in calls[0].data


async def test_other_notify_action_given_typed_targets(hass: HomeAssistant) -> None:
    calls = _capture(hass, "notify", "smtp")
    notifier = _notifier(
        hass, "notify.smtp", notify_target={"entity_id": ["person.joe"]}, notify_custom_target=["joe@example.com"]
    )

    await notifier.notify(ChangeSource.BUTTON, message="Testing")

    assert calls[0].data["target"] == ["joe@example.com"]
