# Typical Configuration

More extensive example configuration, using most of the features.

## UI vs YAML Settings

With the config flow, some settings are now managed in the UI:

| Setting | Where | Notes |
|---------|-------|-------|
| Alarm panel entity | UI (setup) | Selected when adding the integration |
| Change state using panel actions | UI (options, Advanced) | On for new installs, see [Create Panel](../create_panel.md) |
| Arm and explain by voice, Disarm by voice | UI (options) | Voice and chat commands, see [Automated Arming](../../automated_arming.md#built-in-agent-sentences) |
| Calendar entities | UI (options) | Which calendars to use |
| Person entities | UI (options) | Which persons to track for occupancy |
| Occupancy day/night defaults | UI (options, Advanced) | Default alarm state when occupied |
| Time of Day sensors | UI (options) | Sensors that set an alarm state while on, see [Bedtime Recipe](bedtime.md) |
| Calendar end modes | UI (options, Advanced) | What happens when an armed or disarmed calendar event ends |
| Triggers | UI (options) | Whether sunrise, sunset and people arriving or leaving re-evaluate the state |
| Sunrise and sunset | UI (options) | Earliest and latest times |
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
