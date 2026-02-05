# Create an Alarm Panel

If you don't already have an alarm panel, set up a default manual as below, which creates the
state machine for armed/disarmed status. This is all you need in the way of alarm support for AutoArm to function.

You can also choose whether a PIN code is needed or not to arm or disarm. AutoArm has its own delay time
handling for buttons, so recommended to keep the times at zero if not needed for any other purposes.

```yaml
alarm_control_panel:
  - platform: manual
    name: Home Alarm Control
    code_arm_required: false
    arming_time: 0
    delay_time: 0
    disarm_after_trigger: false
    trigger_time: 0
```

## Selecting the Alarm Panel in AutoArm

The alarm panel entity is selected during the AutoArm UI config flow. Go to **Settings** > **Devices & Services** > **Add Integration**, search for **AutoArm**, and select your alarm panel entity in the first step.

### Legacy YAML Reference

Before the UI config flow, the alarm panel was specified in YAML. This is still supported for auto-migration, but new installations should use the UI.

```yaml
autoarm:
  alarm_panel:
    entity_id: alarm_panel.home_alarm_control
```
