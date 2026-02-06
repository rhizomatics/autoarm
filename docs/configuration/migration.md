# Migration Guide

## What Changed

AutoArm now uses a hybrid configuration model. Core settings are managed through the Home Assistant UI via a config flow, while advanced features remain in YAML.

Existing YAML-only installations are **automatically migrated** to a config entry on restart. No manual action is required.

## What Moves Where

| Setting | Before | After |
|---------|--------|-------|
| `alarm_panel.entity_id` | YAML | UI (set during config flow setup) |
| `calendar_control.calendars[].entity_id` | YAML | UI (Options) |
| `calendar_control.no_event_mode` | YAML | UI (Options) |
| `occupancy.entity_id` | YAML | UI (Options) |
| `occupancy.default_state.day` | YAML | UI (Options) |
| `occupancy.default_state.night` | YAML | UI (Options) |
| `diurnal` | YAML | UI (Options) |
| `calendar_control.calendars[].state_patterns` | YAML | YAML (unchanged) |
| `calendar_control.calendars[].poll_interval` | YAML | YAML (unchanged) |
| `transitions` | YAML | YAML (unchanged) |
| `buttons` | YAML | YAML (unchanged) |
| `notify` | YAML | YAML (unchanged) |
| `rate_limit` | YAML | YAML (unchanged) |
| `occupancy.delay_time` | YAML | YAML (unchanged) |

## Auto-Migration

On restart, if AutoArm finds a YAML configuration without a matching config entry, it automatically:

1. Creates a config entry with the alarm panel entity from YAML
2. Populates options with calendar entities, person entities, occupancy defaults, and no-event mode from YAML
3. Continues to read advanced settings (transitions, buttons, notifications, etc.) from YAML

## Cleaning Up YAML After Migration

After migration, the following YAML keys are read from the config entry and can be removed from your YAML configuration:

- `alarm_panel.entity_id`
- `occupancy.entity_id`
- `occupancy.default_state`
- `calendar_control.no_event_mode`
- Calendar `entity_id` values (the entity list is managed in Options)

The remaining YAML sections (`transitions`, `buttons`, `notify`, `rate_limit`, per-calendar `state_patterns` and `poll_interval`) should be kept.

## Coexisting Configurations

If both a YAML configuration and a config entry exist, AutoArm raises a **repair issue** to alert you. The config entry takes precedence for the migrated settings, while YAML continues to provide advanced configuration.
