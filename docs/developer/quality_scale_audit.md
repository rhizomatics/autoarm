# Home Assistant Quality Scale Audit

This document provides a comprehensive audit of the AutoArm integration against the [Home Assistant Integration Quality Scale](https://developers.home-assistant.io/docs/core/integration-quality-scale/). The rule by rule status is kept in `custom_components/autoarm/quality_scale.yaml`.

**Audit Date:** September 2026
**Integration Version:** 1.3.0
**Auditor:** Automated analysis

## Summary

| Tier | Done | Exempt | Todo | Total |
|------|------|--------|------|-------|
| Bronze | 16 | 2 | 0 | 18 |
| Silver | 7 | 3 | 0 | 10 |
| Gold | 12 | 6 | 3 | 21 |
| Platinum | 0 | 2 | 1 | 3 |
| **Total** | **35** | **13** | **4** | **52** |

**Current Tier Achievement:** Silver (with most Gold requirements met)

**Path to Gold:** Complete `exception-translations`, `icon-translations` and `reconfiguration-flow`.

---

## Bronze Tier

The Bronze tier represents the baseline standard for all integrations.

### Completed Rules

| Rule | Status | Notes |
|------|--------|-------|
| `action-setup` | Done | All actions registered in `async_setup` |
| `brands` | Done | Brand assets submitted and approved in the HA brands repository |
| `common-modules` | Done | Logic separated into `const.py`, `helpers.py`, `hass_api.py`, `calendar_events.py`, with the base entity in `entity.py` |
| `config-flow` | Done | UI config flow for alarm panel, calendars, persons, and occupancy defaults |
| `config-flow-test-coverage` | Done | Config flow and options flow covered by tests |
| `dependency-transparency` | Done | No external packages; only standard HA components, declared in `manifest.json` |
| `docs-actions` | Done | Actions documented in `services.yaml` and the docs |
| `docs-high-level-description` | Done | Clear overview in README.md |
| `docs-installation-instructions` | Done | HACS installation documented |
| `docs-removal-instructions` | Done | Removal instructions in `docs/configuration/removal.md` |
| `entity-event-setup` | Done | Entities subscribe to status updates in `async_added_to_hass`, and unsubscribe with `async_on_remove` |
| `entity-unique-id` | Done | Unique ID from the config entry id and the entity key |
| `has-entity-name` | Done | Entities use `has_entity_name` with translated names |
| `runtime-data` | Done | Armer kept in `ConfigEntry.runtime_data` |
| `test-before-setup` | Done | Validates config via voluptuous schemas; `ConfigEntryNotReady` on init failure; raises repair issues for invalid transitions |
| `unique-config-entry` | Done | Unique ID set to domain; `_abort_if_unique_id_configured()` prevents duplicates |

### Exempt Rules

| Rule | Status | Reason |
|------|--------|--------|
| `appropriate-polling` | Exempt | Event-driven integration with pushed entities; calendar polling is configurable |
| `test-before-configure` | Exempt | No device or service connection to test |

---

## Silver Tier

The Silver tier focuses on reliability and robustness.

### Completed Rules

| Rule | Status | Notes |
|------|--------|-------|
| `action-exceptions` | Done | Service handlers raise `HomeAssistantError` on failure |
| `config-entry-unloading` | Done | Unloads the entity platforms, and `shutdown()` cleans up all listeners |
| `docs-configuration-parameters` | Done | Parameters documented in `automated_arming.md` and examples |
| `docs-installation-parameters` | Done | Config flow settings listed in the typical configuration example |
| `integration-owner` | Done | @jeyrb declared as code owner |
| `parallel-updates` | Done | `PARALLEL_UPDATES = 0` on both entity platforms |
| `test-coverage` | Done | Test coverage >90% with `--cov-fail-under=90` enforced |

### Exempt Rules

| Rule | Status | Reason |
|------|--------|--------|
| `entity-unavailable` | Exempt | Entities report AutoArm's own state, always available while loaded |
| `log-when-unavailable` | Exempt | No device or service connection of its own |
| `reauthentication-flow` | Exempt | No authentication required |

---

## Gold Tier

The Gold tier represents best-in-class user experience.

### Completed Rules

| Rule | Status | Notes |
|------|--------|-------|
| `devices` | Done | Entities belong to a single AutoArm service device |
| `diagnostics` | Done | `diagnostics.py` exposes entry data, options, YAML keys, and armer state |
| `docs-data-update` | Done | Update mechanisms documented (events, polling, manual triggers) |
| `docs-examples` | Done | Example configs in `docs/configuration/examples/` |
| `docs-known-limitations` | Done | Limitations documented in `docs/known_limitations.md` |
| `docs-supported-functions` | Done | All features documented in README and automated_arming.md |
| `docs-troubleshooting` | Done | Troubleshooting guide in `docs/troubleshooting.md` |
| `docs-use-cases` | Done | Use cases illustrated in "Why use alarm control panels?" section |
| `entity-category` | Done | Initialized and failures entities are diagnostic |
| `entity-device-class` | Done | Timestamp for last calculation, enum for last intervention |
| `entity-translations` | Done | Entity names translated for every supported language |
| `repair-issues` | Done | Raises repair issues for invalid transition conditions |

### Exempt Rules

| Rule | Status | Reason |
|------|--------|--------|
| `discovery` | Exempt | User-configured entities; nothing to discover |
| `discovery-update-info` | Exempt | No discovery |
| `docs-supported-devices` | Exempt | Works with any compatible HA entities |
| `dynamic-devices` | Exempt | Only one service device, created with the config entry |
| `entity-disabled-by-default` | Exempt | All entities are essential |
| `stale-devices` | Exempt | Only one service device, removed with the config entry |

### Todo Rules

| Rule | Status | Action Required |
|------|--------|-----------------|
| `exception-translations` | Todo | Use translation keys for the `HomeAssistantError` messages raised by `reload` and `enquire_configuration` |
| `icon-translations` | Todo | Add `icons.json` |
| `reconfiguration-flow` | Todo | Add a reconfigure step; the options flow does already allow the alarm panel to be changed |

---

## Platinum Tier

The Platinum tier represents technical excellence.

### Exempt Rules

| Rule | Status | Reason |
|------|--------|--------|
| `async-dependency` | Exempt | No external library dependency |
| `inject-websession` | Exempt | No external HTTP calls |

### In Progress

| Rule | Status | Notes |
|------|--------|-------|
| `strict-typing` | In Progress | `py.typed` marker present; some `Any` types remain due to HA ConfigType patterns |

---

## Code Quality Notes

### Strengths

- Clean separation of concerns across modules
- Comprehensive error tracking via `failures` counter and repair issues
- Rate limiting prevents arming loops
- Proper async/await throughout
- Good test coverage (>90%) for core functionality
- Consistent logging with "AUTOARM" prefix
- Support for graceful shutdown and reload
- Diagnostics support for debugging

### Areas for Improvement

- Some methods in `autoarming.py` are lengthy and could be refactored
- A few `Any` type hints remain that could be more specific

---

## References

- [Home Assistant Integration Quality Scale](https://developers.home-assistant.io/docs/core/integration-quality-scale/)
- [Quality Scale Rules](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/)
- [Home Assistant Brands Repository](https://github.com/home-assistant/brands)
