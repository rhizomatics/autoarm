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

## Panels That Must Be Changed Through Their Actions

By default AutoArm sets the alarm panel's state directly, which is all a *manual* panel needs. Some alarm
integrations do more than hold a state when armed or disarmed. For example, [Alarmo](https://github.com/nielsfaber/alarmo)
arms its child areas when its master panel is armed. For these, switch on **Change state using the alarm panel's actions**
in the AutoArm options, so AutoArm calls `alarm_control_panel.alarm_arm_away`, `alarm_control_panel.alarm_disarm` and so on instead.

- The panel mustn't need a code to arm or disarm, as AutoArm doesn't have one to give it.
- If the action fails, or doesn't change the state, AutoArm leaves the panel alone rather than set the state behind the integration's back. A warning is logged.
- An exit delay is fine: when the panel goes to `arming`, and then to the armed state, AutoArm doesn't mistake that for someone changing it by hand.
- `pending` has no action, so it's still set directly, for example between calendar events.

### Legacy YAML Reference

Before the UI config flow, the alarm panel was specified in YAML. This is still supported for auto-migration, but new installations should use the UI.

```yaml
autoarm:
  alarm_panel:
    entity_id: alarm_panel.home_alarm_control
```
