# Removing Auto Arm

Source: https://autoarm.rhizomatics.org.uk/configuration/removal/

## Remove the Integration Entry

1. Go to **Settings** > **Devices & Services** and select **Auto Arm**
1. Click the three-dot menu and select **Delete**

This also removes the Auto Arm device and its entities.

## Via HACS

1. Open **HACS** in your Home Assistant instance
1. Navigate to **Integrations**
1. Find **Auto Arm** and click on it
1. Click the three-dot menu and select **Remove**
1. Restart Home Assistant

## Manual Removal

1. Delete the `custom_components/autoarm` directory
1. Remove the `autoarm:` section from your `configuration.yaml` if present
1. Restart Home Assistant

## Cleaning Up

After removal, you may also want to:

- Delete any Auto Arm-related automations or scripts you created
- Remove mobile notification actions configured for Auto Arm
- Remove any calendar entities that were created solely for Auto Arm scheduling
