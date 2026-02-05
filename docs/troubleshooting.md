# Troubleshooting

## Alarm State Not Changing

**Check the initialized sensor**: Look at `binary_sensor.autoarm_initialized` in Developer Tools > States. If it shows anything other than `valid`, there is a configuration issue.

**Check for manual intervention lock**: After a manual change (button press, mobile action, panel change), AutoArm will not override the state until the next occupancy change. Use the `autoarm.reset_state` service to clear the lock.

**Check transition conditions**: Open Settings > System > Repairs to see if any transition conditions have validation errors. Fix the conditions in your YAML configuration and reload.

## Calendar Events Not Detected

**Check poll interval**: Calendar events are detected by polling. If events are very short, increase the poll interval or ensure events span at least 30 seconds.

**Check state patterns**: Verify that your calendar event summaries match the configured state patterns. The default patterns are `Away`, `Home`, `Night`, `Disarmed`, and `Vacation`/`Holiday`. Custom patterns use regex matching.

**Check the last calendar event sensor**: Look at `sensor.autoarm_last_calendar_event` in Developer Tools > States for the most recently detected event.

## Notifications Not Sending

**Check notify profile configuration**: Notifications require at least one non-common profile to match. The `common` profile only provides base configuration (service, data) that is merged into matched profiles, with default `silent` and `normal` profiles
created if no explicit ones given.

**Check the service name**: Ensure the notify service exists. The `notify.` prefix is stripped automatically, so `notify.mobile_app` becomes a call to the `mobile_app` service in the `notify` domain.

## Repair Issues

AutoArm uses the Home Assistant repair system to report configuration problems:

- **Invalid Transition Condition**: A transition condition template failed validation. Check the condition syntax in your YAML.
- **YAML core configuration is deprecated**: Core settings have been migrated to the UI config entry. Remove the migrated keys from YAML (see the [Migration Guide](configuration/migration.md)).

## Reload After YAML Changes

After modifying YAML configuration (transitions, buttons, notify, etc.), call the `autoarm.reload` service or restart Home Assistant for changes to take effect.

## Debug Logging

Enable debug logging for AutoArm to see detailed operation logs:

```yaml
logger:
  logs:
    custom_components.autoarm: debug
```

All AutoArm log messages use the `AUTOARM` prefix for easy filtering.
