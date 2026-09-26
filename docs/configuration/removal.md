# Removing Auto Arm

## Remove the Integration Entry

1. Go to **Settings** > **Devices & Services** and select **Auto Arm**
2. Click the three-dot menu and select **Delete**

This also removes the Auto Arm device and its entities.

## Via HACS

1. Open **HACS** in your Home Assistant instance
2. Navigate to **Integrations**
3. Find **Auto Arm** and click on it
4. Click the three-dot menu and select **Remove**
5. Restart Home Assistant

## Manual Removal

1. Delete the `custom_components/autoarm` directory
2. Remove the `autoarm:` section from your `configuration.yaml` if present
3. Restart Home Assistant

## Cleaning Up

After removal, you may also want to:

- Delete any Auto Arm-related automations or scripts you created
- Remove mobile notification actions configured for Auto Arm
- Remove any calendar entities that were created solely for Auto Arm scheduling
