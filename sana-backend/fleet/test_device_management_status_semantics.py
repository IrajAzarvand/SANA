from django.test import SimpleTestCase

from fleet.models import Device, DeviceOperation, DeviceLifecycleEvent


class DeviceManagementStatusSemanticsTests(SimpleTestCase):
    def test_management_status_choices_exclude_sale_and_retirement(self):
        choices = dict(Device.MANAGEMENT_STATUS_CHOICES)

        self.assertNotIn('sold', choices)
        self.assertNotIn('retired', choices)
        self.assertIn('in_repair', choices)
        self.assertIn('unusable', choices)

    def test_sale_remains_operation_metadata_not_management_status(self):
        replacement_methods = dict(DeviceOperation._meta.get_field('replacement_method').choices)
        lifecycle_events = dict(DeviceLifecycleEvent.EVENT_TYPE_CHOICES)

        self.assertIn('sold', replacement_methods)
        self.assertIn('sold', lifecycle_events)
        self.assertNotIn('sold', dict(Device.MANAGEMENT_STATUS_CHOICES))


    def test_admin_operation_choices_exclude_removed_actions(self):
        choices = dict(DeviceOperation.OPERATION_TYPE_CHOICES)

        for removed in (
            'repaired',
            'retire',
            'transfer_vehicle',
            'transfer_branch',
            'stolen',
            'found',
            'disposition',
        ):
            self.assertNotIn(removed, choices)

        for retained in (
            'return_for_repair',
            'temporary_replacement',
            'permanent_replacement',
            'lost',
            'transfer_customer',
            'dispose',
        ):
            self.assertIn(retained, choices)
