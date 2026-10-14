# Typical Configuration

More extensive example configuration, using most of the features.

## UI vs YAML Settings

With the config flow, most settings are now managed in the UI:

| Setting | Where | Notes |
|---------|-------|-------|
| Alarm panel entity | UI (setup) | Selected when adding the integration |
| Change state using panel actions | UI (options, Advanced) | On for new installs, see [Create Panel](../create_panel.md) |
| Arm and explain by voice, Disarm by voice | UI (options) | Voice and chat commands, see [Automated Arming](../../automated_arming.md#built-in-agent-sentences) |
| Bedtime sensor | UI (setup, options) | Times of the Day sensor for `armed_night`, see [Recommended Recipe](recommended_recipe.md) |
| Calendar entities | UI (setup, options) | Which calendars to use |
| Person entities | UI (setup, options) | Which persons to track for occupancy |
| Occupied states | UI (options, Advanced - Diurnal) | Alarm state when occupied by day, after bedtime and before bedtime |
| Times of the Day sensors | UI (options) | Sensors that set any other alarm state while on |
| Calendar end modes | UI (options, Advanced - Calendar) | What happens when an armed or disarmed calendar event ends |
| Triggers | UI (options, Advanced - Diurnal and Advanced - Occupancy) | Whether sunrise, sunset and people arriving or leaving re-evaluate the state |
| Sunrise and sunset | UI (options) | Earliest and latest times |
| Calendar match rules | UI (options, Advanced - Calendar) | Regex patterns matching calendar events to alarm states, copied from YAML if already there |
| Calendar poll interval | UI (options, Advanced - Calendar) | How often to check the calendars |
| Transitions | YAML | Condition templates for state transitions |
| Buttons | UI (options, Buttons) | Physical button entities and delays, copied from YAML if already there |
| Notifications | UI (options) | Notification service and targets, and priorities for Supernotify |
| Notification Profiles | YAML | **Deprecated**, replaced by deeper Supernotify integration in the options, and will be removed when Home Assistant 2027.4 is released |
| Rate limit | YAML | Throttling for arm calls |

## Full YAML Example

``` yaml
--8<-- "examples/typical.yaml"
```
