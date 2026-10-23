# Frigate Profiles

Auto Arm can switch the active [Frigate Profile](https://docs.frigate.video/configuration/profiles/) as the
alarm state changes. For example, your cameras could record and send notifications only while the alarm is
`armed_away`, or skip detection on indoor cameras while `disarmed`.

This needs Frigate 0.18 or later, and the [Frigate integration](https://docs.frigate.video/integrations/home-assistant/),
which provides a **Profile** select entity once at least one profile is defined in Frigate.

## Set up the Profiles in Frigate

!!! tip
    Profiles can be configured in Frigate's web based [Settings UI](https://docs.frigate.video/configuration/config/#using-the-settings-ui) as well as directly in YAML.

Name each profile after the alarm state it's for, using the state's own name:

```yaml
profiles:
  disarmed:
    friendly_name: Disarmed
  armed_away:
    friendly_name: Away

cameras:
  living_room:
    profiles:
      disarmed:
        detect:
          enabled: false
```

Profiles can only override what's already in the base config. See the Frigate docs for the constraints,
such as recording having to be enabled in the base config.

## Configure Auto Arm

In the **Advanced - Frigate** section of the Options:

- **Frigate profile select**: the Profile select entity from the Frigate integration
- a profile for each alarm state that should have one, chosen from the profiles of the select entity, or typed in.
  Profiles are offered once the select entity has been saved, and the Options reopened.

Whenever the alarm panel moves to a state with a profile, whatever changed it, Frigate is switched to that
profile. Any other alarm state switches Frigate back to no profile, so the cameras use their base config.

Some states leave the profile as it is:

- transitional states, like `arming`, `pending` and `triggered`
- an alarm panel that is unavailable

Auto Arm also brings Frigate up to date when Home Assistant starts, and when the Profile select becomes
available again after Frigate has been offline. It doesn't switch back a profile you choose by hand in Frigate.
It only changes the profile again when the alarm state next changes.

If the profile given for an alarm state isn't in Frigate, Auto Arm logs a warning and leaves the
profile as it is.
