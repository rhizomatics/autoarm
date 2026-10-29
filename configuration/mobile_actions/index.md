# Mobile Actions

Source: https://autoarm.rhizomatics.org.uk/configuration/mobile_actions/

Auto Arm listens out for the result of [Actionable Notifications](https://companion.home-assistant.io/docs/notifications/actionable-notifications/) with the following `action` values:

## Supported Actions

| Action Key         |
| ------------------ |
| ALARM_PANEL_DISARM |
| ALARM_PANEL_RESET  |
| ALARM_PANEL_AWAY   |

## Add Action to a Mobile Push Notification

Here's how to send a notification to a mobile app, with a Disarm action:

```yaml
action: notify.mobile_app_<your_device_id_here>
data:
  message: "The noisy PIR has detected the kids again"
  data:
    actions:
      - action: "ALARM_PANEL_DISARM" # The key you are sending for the event
        title: "Disarm Alarm" # The button title
        icon: sfsymbols:bell.slash
```

## Adding Actions to Auto Arm's Own Notifications

Auto Arm's own state-change notifications, sent from the **Notifications** section of the Options UI, can carry the same kind of actions. Set **Extra Notification Data** to include an `actions` list, and every notification Auto Arm sends gets those buttons:

```yaml
actions:
  - action: "ALARM_PANEL_DISARM"
    title: "Disarm Alarm"
    icon: sfsymbols:bell.slash
```

This is a plain data block, not a template or script - it's merged into every notification's `data` as-is.

With Supernotify as the notification action, all three actions are added without any of this, with titles in the Home Assistant language.

Whichever way they are added, an action that would do nothing is left out of the notification, so `ALARM_PANEL_DISARM` isn't offered when the alarm has just been disarmed, nor `ALARM_PANEL_AWAY` when it has just been armed away.
