# Typical Configuration

More extensive example configuration, using most of the features.

## UI vs YAML Settings

With the config flow, some settings are now managed in the UI:

| Setting | Where | Notes |
|---------|-------|-------|
| Alarm panel entity | UI (setup) | Selected when adding the integration |
| Calendar entities | UI (options) | Which calendars to use |
| Person entities | UI (options) | Which persons to track for occupancy |
| Occupancy day/night defaults | UI (options) | Default alarm state when occupied |
| No-event mode | UI (options) | Behaviour when no calendar event is active |
| Diurnal | UI (options) | Sunrise/sunset configuration |
| Per-calendar state patterns | YAML | Regex patterns matching calendar events to alarm states |
| Per-calendar poll interval | YAML | How often to check each calendar |
| Transitions | YAML | Condition templates for state transitions |
| Buttons | YAML | Physical button entity mappings |
| Notifications | UI (options) | Notification service and targets |
| Notification Profiles | YAML | Notification profile configuration |
| Rate limit | YAML | Throttling for arm calls |

## Full YAML Example

``` yaml
--8<-- "examples/typical.yaml"
```
