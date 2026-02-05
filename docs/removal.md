# Removing AutoArm

## Via HACS

1. Open **HACS** in your Home Assistant instance
2. Navigate to **Integrations**
3. Find **AutoArm** and click on it
4. Click the three-dot menu and select **Remove**
5. Restart Home Assistant

## Manual Removal

1. Delete the `custom_components/autoarm` directory
2. Remove the `autoarm:` section from your `configuration.yaml` if present
3. Restart Home Assistant

## Cleaning Up

After removal, you may also want to:

- Delete any AutoArm-related automations or scripts you created
- Remove mobile notification actions configured for AutoArm
- Remove any calendar entities that were created solely for AutoArm scheduling
