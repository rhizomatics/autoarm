# Migration Guide

## What Changed

Auto Arm now uses a hybrid configuration model. Core settings are managed through the Home Assistant UI via a config flow, while advanced features remain in YAML.

Existing YAML-only installations are **automatically migrated** to a config entry on restart. No manual action is required.

## What Moves Where

| Setting | Before | After |
|---------|--------|-------|
| `alarm_panel.entity_id` | YAML | UI (set during config flow setup) |
| `calendar_control.calendars[].entity_id` | YAML | UI (Options) |
| `calendar_control.no_event_mode` | YAML | UI (Options, as both the armed and disarmed calendar end modes) |
| `occupancy.entity_id` | YAML | UI (Options) |
| `occupancy.default_state.day` | YAML | UI (Options) |
| `occupancy.default_state.night` | YAML | UI (Options) |
| `diurnal` | YAML | UI (Options) |
| `calendar_control.calendars[].state_patterns` | YAML | UI Options, as match rules, copied from YAML on first start |
| `calendar_control.calendars[].poll_interval` | YAML | UI Options, one for all calendars, the shortest in YAML copied on first start |
| `calendar_control.notify_grace_period` | YAML | UI Options, copied from YAML on first start |
| `transitions` | YAML | YAML (unchanged) |
| `buttons` | YAML | UI Options, copied from YAML on first start |
| `notify` | YAML | UI (Options). Profiles in YAML still work, but are **deprecated** and will be removed when Home Assistant 2027.4 is released |
| `rate_limit` | YAML | UI Options, copied from YAML on first start |
| `occupancy.delay_time` | YAML | UI Options, copied from YAML on first start |

## Auto-Migration

On restart, if Auto Arm finds a YAML configuration without a matching config entry, it automatically:

1. Creates a config entry with the alarm panel entity from YAML
2. Populates options with calendar entities, person entities, occupancy defaults, and calendar end modes from `no_event_mode` in YAML
3. Continues to read advanced settings (transitions, notification profiles, etc.) from YAML

## Cleaning Up YAML After Migration

After migration, the following YAML keys are read from the config entry and can be removed from your YAML configuration:

- `alarm_panel.entity_id`
- `occupancy.entity_id`
- `occupancy.default_state`
- `calendar_control.no_event_mode`
- Calendar `entity_id` values (the entity list is managed in Options)

The `buttons`, `rate_limit` and `calendar_control` sections, and `occupancy.delay_time`, are copied into the options the first time, and can then be removed. Only `transitions` needs to be kept in YAML.

The `notify` section is deprecated, replaced by deeper Supernotify integration in the options, and will be removed when Home Assistant 2027.4 is released. A repair is raised while it is still there. See [Notifications](./notifications.md) for the priorities and scenarios that take its place.

## Coexisting Configurations

If both a YAML configuration and a config entry exist, Auto Arm raises a **repair issue** to alert you. The config entry takes precedence for the migrated settings, while YAML continues to provide advanced configuration.
