from django.test import TestCase
from unittest.mock import patch

from accounts.models import User
from fleet.models import Device
from organizations.models import (
    Organization, Subscription, SubscriptionDevice, SubscriptionPayment,
    SubscriptionInstallmentPlan, SubscriptionInstallment, SubscriptionPaymentAllocation,
)
from organizations.financial import create_installment_plan, allocate_payment
from rest_framework.exceptions import ValidationError
from django.db.models import Sum
from .serializers import SubscriptionWizardSerializer


class SubscriptionWizardExistingUserTests(TestCase):
    def setUp(self):
        self.lifecycle_patcher = patch('organizations.serializers.record_device_lifecycle_event')
        self.lifecycle_patcher.start()
        self.addCleanup(self.lifecycle_patcher.stop)
        self.device = Device.objects.create(imei='111111111111111')
        self.user = User.objects.create_user(
            username='existing-person',
            password='Original-Password-123',
            first_name='نام قبلی',
            last_name='نام خانوادگی قبلی',
            mobile='09120000000',
            account_type='personal',
            role='personal_user',
        )

    def _payload(self, **overrides):
        payload = {
            'customer_type': 'personal',
            'existing_user_id': self.user.id,
            'username': self.user.username,
            'first_name': 'نام جدید',
            'last_name': 'نام خانوادگی جدید',
            'mobile': '09121111111',
            'national_id': '0012345678',
            'address': 'نشانی جدید',
            'contract_number': 'PRS-TEST-0001',
            'start_date': '2026-11-07',
            'end_date': '2027-11-07',
            'price': '100000000',
            'devices': [{
                'device_id': self.device.id,
                'start_date': '2026-11-07',
                'end_date': '2027-11-07',
            }],
            'payments': [],
        }
        payload.update(overrides)
        return payload

    @patch('organizations.serializers.record_device_lifecycle_event')
    def test_existing_user_is_updated_without_changing_password(self, _record_event):
        serializer = SubscriptionWizardSerializer(data=self._payload())
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()

        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'نام جدید')
        self.assertEqual(self.user.last_name, 'نام خانوادگی جدید')
        self.assertEqual(self.user.mobile, '09121111111')
        self.assertEqual(self.user.national_id, '0012345678')
        self.assertEqual(self.user.address, 'نشانی جدید')
        self.assertTrue(self.user.check_password('Original-Password-123'))

    def test_existing_user_username_must_match_selected_account(self):
        serializer = SubscriptionWizardSerializer(
            data=self._payload(username='another-username')
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn('username', serializer.errors)

    def test_new_user_requires_password(self):
        payload = self._payload()
        payload.pop('existing_user_id')
        payload['username'] = 'new-person'
        payload['contract_number'] = 'PRS-TEST-0002'
        serializer = SubscriptionWizardSerializer(data=payload)
        self.assertFalse(serializer.is_valid())
        self.assertIn('password', serializer.errors)


    @patch('organizations.serializers.record_device_lifecycle_event')
    def test_wizard_records_upfront_receipt_and_creates_schedule_for_remaining_amount(self, _record_event):
        payload = self._payload(
            payments=[{
                'amount': '20000000',
                'payment_date': '2026-11-07',
                'description': 'پیش‌پرداخت',
            }],
            installment_plan={
                'installment_count': 4,
                'interval_months': 3,
                'calculation_mode': 'equal',
                'surplus_policy': 'credit',
            },
        )
        serializer = SubscriptionWizardSerializer(data=payload)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        subscription = serializer.save()

        plan = subscription.installment_plans.get(status='active')
        self.assertEqual(subscription.price, 100000000)
        self.assertEqual(plan.scheduled_amount, 80000000)
        self.assertEqual(
            list(plan.installments.order_by('number').values_list('amount', flat=True)),
            [20000000, 20000000, 20000000, 20000000],
        )
        receipt = subscription.payments.get()
        allocation = receipt.allocations.get()
        self.assertEqual(allocation.allocation_type, 'contract_advance')
        self.assertEqual(allocation.amount, 20000000)
        self.assertIsNone(allocation.installment_id)


class SubscriptionWizardOrganizationSelectionTests(TestCase):
    def setUp(self):
        self.lifecycle_patcher = patch('organizations.serializers.record_device_lifecycle_event')
        self.lifecycle_patcher.start()
        self.addCleanup(self.lifecycle_patcher.stop)
        self.device = Device.objects.create(imei='222222222222222')

        self.organization = Organization.objects.create(
            name='سازمان اولیه',
            code='ORG-EXISTING-01',
            phone='02111111111',
        )
        self.manager = User.objects.create_user(
            username='existing-manager',
            password='Original-Password-123',
            first_name='مدیر',
            last_name='شرکت',
            mobile='09120000001',
            account_type='organization',
            role='main_user',
            organization=self.organization,
        )

    def _payload(self, **overrides):
        payload = {
            'customer_type': 'organization',
            'organization_id': self.organization.id,
            'organization_name': 'نام ویرایش‌شده سازمان',
            'organization_code': self.organization.code,
            'registration_number': '12345',
            'economy_code': '98765',
            'organization_phone': '02122222222',
            'organization_email': 'office@example.com',
            'organization_address': 'نشانی جدید سازمان',
            'existing_user_id': self.manager.id,
            'username': self.manager.username,
            'first_name': 'مدیر',
            'last_name': 'جدید',
            'mobile': '09121111111',
            'national_id': '',
            'address': '',
            'contract_number': 'ORG-TEST-0001',
            'start_date': '2026-11-07',
            'end_date': '2027-11-07',
            'price': '100000000',
            'devices': [{
                'device_id': self.device.id,
                'start_date': '2026-11-07',
                'end_date': '2027-11-07',
            }],
            'payments': [],
        }
        payload.update(overrides)
        return payload

    def test_existing_organization_is_reused_and_updated(self):
        serializer = SubscriptionWizardSerializer(data=self._payload())
        self.assertTrue(serializer.is_valid(), serializer.errors)
        subscription = serializer.save()

        self.organization.refresh_from_db()
        self.manager.refresh_from_db()
        self.assertEqual(subscription.organization_id, self.organization.id)
        self.assertEqual(self.organization.name, 'نام ویرایش‌شده سازمان')
        self.assertEqual(self.organization.registration_number, '12345')
        self.assertEqual(self.organization.phone, '02122222222')
        self.assertEqual(self.manager.organization_id, self.organization.id)
        self.assertTrue(self.manager.check_password('Original-Password-123'))

    def test_existing_organization_requires_a_non_empty_name(self):
        serializer = SubscriptionWizardSerializer(
            data=self._payload(organization_name='   ')
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn('organization_name', serializer.errors)

    def test_new_manager_is_attached_to_selected_existing_organization(self):
        payload = self._payload(
            existing_user_id=None,
            username='new-manager',
            password='New-Password-123',
            contract_number='ORG-TEST-0002',
        )
        serializer = SubscriptionWizardSerializer(data=payload)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        subscription = serializer.save()

        self.assertEqual(subscription.organization_id, self.organization.id)
        manager = User.objects.get(username='new-manager')
        self.assertEqual(manager.organization_id, self.organization.id)
        self.assertEqual(manager.role, 'main_user')

    def test_manager_from_another_organization_is_rejected(self):
        from organizations.models import Organization

        other_organization = Organization.objects.create(
            name='سازمان دوم',
            code='ORG-EXISTING-02',
        )
        self.manager.organization = other_organization
        self.manager.save(update_fields=['organization'])

        serializer = SubscriptionWizardSerializer(data=self._payload())
        self.assertFalse(serializer.is_valid())
        self.assertIn('existing_user_id', serializer.errors)

    def test_existing_manager_cannot_be_silently_moved_to_new_organization(self):
        payload = self._payload(
            organization_id=None,
            organization_name='سازمان تازه',
            contract_number='ORG-TEST-0003',
        )
        serializer = SubscriptionWizardSerializer(data=payload)
        self.assertFalse(serializer.is_valid())
        self.assertIn('organization_id', serializer.errors)


class SubscriptionWizardDeviceValidationTests(TestCase):
    def setUp(self):
        self.lifecycle_patcher = patch('organizations.serializers.record_device_lifecycle_event')
        self.lifecycle_patcher.start()
        self.addCleanup(self.lifecycle_patcher.stop)
        self.user = User.objects.create_user(
            username='device-test-user',
            password='Password-123456',
            account_type='personal',
            role='personal_user',
        )
        self.device = Device.objects.create(imei='333333333333333')

    def _payload(self, **overrides):
        payload = {
            'customer_type': 'personal',
            'username': self.user.username,
            'existing_user_id': self.user.id,
            'first_name': 'Test',
            'last_name': 'User',
            'mobile': '09120000000',
            'contract_number': 'DEVICE-TEST-0001',
            'start_date': '2026-11-07',
            'end_date': '2027-11-07',
            'price': '100000000',
            'devices': [{
                'device_id': self.device.id,
                'start_date': '2026-11-07',
                'end_date': '2027-11-07',
            }],
            'payments': [],
        }
        payload.update(overrides)
        return payload

    def test_empty_device_list_is_rejected(self):
        serializer = SubscriptionWizardSerializer(data=self._payload(devices=[]))
        self.assertFalse(serializer.is_valid())
        self.assertIn('devices', serializer.errors)

    def test_device_not_in_warehouse_is_rejected(self):
        self.device.management_status = 'sold'
        self.device.save(update_fields=['management_status'])
        serializer = SubscriptionWizardSerializer(data=self._payload())
        self.assertFalse(serializer.is_valid())
        self.assertIn('devices', serializer.errors)

    def test_device_with_active_subscription_is_rejected(self):
        existing_subscription = Subscription.objects.create(
            contract_number='DEVICE-TEST-EXISTING',
            customer_type='personal',
            user=self.user,
            start_date='2026-11-07',
            end_date='2027-11-07',
        )
        SubscriptionDevice.objects.create(
            subscription=existing_subscription,
            device=self.device,
            start_date='2026-11-07',
            end_date='2027-11-07',
        )
        serializer = SubscriptionWizardSerializer(data=self._payload())
        self.assertFalse(serializer.is_valid())
        self.assertIn('devices', serializer.errors)

    def test_device_date_range_must_be_inside_contract(self):
        serializer = SubscriptionWizardSerializer(data=self._payload(devices=[{
            'device_id': self.device.id,
            'start_date': '2026-11-06',
            'end_date': '2027-11-07',
        }]))
        self.assertFalse(serializer.is_valid())
        self.assertIn('devices', serializer.errors)

    def test_valid_warehouse_device_is_assigned_to_new_contract(self):
        serializer = SubscriptionWizardSerializer(data=self._payload())
        self.assertTrue(serializer.is_valid(), serializer.errors)
        subscription = serializer.save()
        link = SubscriptionDevice.objects.get(subscription=subscription, device=self.device)
        self.assertIsNone(link.unassigned_at)
        self.device.refresh_from_db()
        self.assertEqual(self.device.management_status, 'sold')

class SubscriptionContractNumberUniquenessTests(TestCase):
    def test_contract_number_cannot_duplicate_any_existing_contract(self):
        existing_number = 'PRS-TEST-DUPLICATE'
        Subscription.objects.create(
            contract_number=existing_number,
            customer_type='organization',
            start_date='2026-11-07',
            end_date='2027-11-07',
        )
        device = Device.objects.create(imei='444444444444444')

        payload = {
            'customer_type': 'personal',
            'username': 'unique-number-test-user',
            'password': 'Password-123456',
            'first_name': 'Test',
            'last_name': 'User',
            'mobile': '09120000000',
            'contract_number': existing_number,
            'start_date': '2026-11-07',
            'end_date': '2027-11-07',
            'price': '100000000',
            'devices': [{
                'device_id': device.id,
                'start_date': '2026-11-07',
                'end_date': '2027-11-07',
            }],
            'payments': [],
        }

        serializer = SubscriptionWizardSerializer(data=payload)

        self.assertFalse(serializer.is_valid())
        self.assertIn('contract_number', serializer.errors)
        self.assertIn('قبلاً استفاده شده', str(serializer.errors['contract_number']))




class SubscriptionContractPriceTests(TestCase):
    def test_receipt_does_not_change_contract_total(self):
        subscription = Subscription.objects.create(
            contract_number='FIN-TEST-0001',
            customer_type='personal',
            start_date='2026-11-07',
            end_date='2027-11-07',
            price=100000000,
        )

        SubscriptionPayment.objects.create(
            subscription=subscription,
            amount=20000000,
            received_at='2026-11-07',
        )
        SubscriptionPayment.objects.create(
            subscription=subscription,
            amount=30000000,
            payment_date='2026-12-07',
        )

        subscription.refresh_from_db()
        self.assertEqual(subscription.price, 100000000)
        self.assertEqual(
            sum(payment.amount for payment in subscription.payments.all()),
            50000000,
        )



class SubscriptionInstallmentLedgerTests(TestCase):
    def setUp(self):
        self.subscription = Subscription.objects.create(
            contract_number='INST-TEST-0001',
            customer_type='personal',
            start_date='2026-01-31',
            end_date='2027-01-31',
            price=100,
        )

    def _plan(self, **overrides):
        data = {
            'scheduled_amount': 100,
            'installment_count': 3,
            'interval_months': 1,
            'calculation_mode': 'equal',
            'surplus_policy': 'credit',
        }
        data.update(overrides)
        return create_installment_plan(self.subscription, data)

    def test_equal_installments_put_rounding_remainder_on_last(self):
        plan = self._plan()
        installments = list(plan.installments.order_by('number'))
        self.assertEqual([item.amount for item in installments], [33, 33, 34])
        self.assertEqual(sum(item.amount for item in installments), 100)

    def test_due_dates_are_based_on_this_contract_start_date_and_clamp_month_end(self):
        plan = self._plan()
        dates = list(plan.installments.order_by('number').values_list('due_date', flat=True))
        self.assertEqual(
            [item.isoformat() for item in dates],
            ['2026-02-28', '2026-03-31', '2026-04-30'],
        )

    def test_custom_installments_must_sum_to_scheduled_amount(self):
        plan = self._plan(
            calculation_mode='custom',
            custom_amounts=[20, 30, 50],
        )
        self.assertEqual(
            list(plan.installments.order_by('number').values_list('amount', flat=True)),
            [20, 30, 50],
        )
        with self.assertRaises(ValidationError):
            self._plan(
                calculation_mode='custom',
                custom_amounts=[20, 30, 49],
            )

    def test_automatic_allocation_pays_oldest_due_installments_first(self):
        plan = self._plan(installment_count=2)
        payment = SubscriptionPayment.objects.create(
            subscription=self.subscription,
            amount=60,
            payment_date='2026-04-01',
        )
        allocate_payment(payment)
        allocations = list(
            payment.allocations.order_by('installment__number').values_list(
                'installment__number', 'amount'
            )
        )
        self.assertEqual(allocations, [(1, 50), (2, 10)])

    def test_future_installments_remain_credit_by_default(self):
        self.subscription.start_date = '2026-01-01'
        self.subscription.save(update_fields=['start_date'])
        plan = self._plan(installment_count=2)
        payment = SubscriptionPayment.objects.create(
            subscription=self.subscription,
            amount=70,
            payment_date='2026-01-15',
        )
        allocate_payment(payment)
        self.assertEqual(
            payment.allocations.aggregate(total=Sum('amount'))['total'],
            None,
        )

    def test_future_installments_can_be_allocated_when_plan_allows_it(self):
        self.subscription.start_date = '2026-01-01'
        self.subscription.save(update_fields=['start_date'])
        plan = self._plan(installment_count=2, surplus_policy='future')
        payment = SubscriptionPayment.objects.create(
            subscription=self.subscription,
            amount=70,
            payment_date='2026-01-15',
        )
        allocate_payment(payment)
        self.assertEqual(
            list(payment.allocations.order_by('installment__number').values_list('amount', flat=True)),
            [50, 20],
        )

    def test_manual_allocation_can_target_a_selected_installment(self):
        plan = self._plan(installment_count=2)
        second = plan.installments.get(number=2)
        payment = SubscriptionPayment.objects.create(
            subscription=self.subscription,
            amount=25,
            payment_date='2026-01-10',
        )
        allocate_payment(
            payment,
            mode='manual',
            allocations=[{'installment_id': second.id, 'amount': 25}],
        )
        allocation = payment.allocations.get()
        self.assertEqual(allocation.installment_id, second.id)
        self.assertEqual(allocation.amount, 25)

    def test_manual_allocation_cannot_exceed_receipt_or_installment_balance(self):
        plan = self._plan(installment_count=2)
        first = plan.installments.get(number=1)
        payment = SubscriptionPayment.objects.create(
            subscription=self.subscription,
            amount=20,
            payment_date='2026-01-10',
        )
        with self.assertRaises(ValidationError):
            allocate_payment(
                payment,
                mode='manual',
                allocations=[{'installment_id': first.id, 'amount': 21}],
            )

    def test_unallocated_overpayment_remains_customer_credit(self):
        plan = self._plan(installment_count=2)
        payment = SubscriptionPayment.objects.create(
            subscription=self.subscription,
            amount=130,
            payment_date='2026-04-01',
        )
        allocate_payment(payment)
        allocated = payment.allocations.aggregate(
            total=Sum('amount')
        )['total']
        self.assertEqual(allocated, 100)
        self.assertEqual(payment.amount - allocated, 30)

    def test_contract_advance_is_not_mistaken_for_installment_or_credit(self):
        payment = SubscriptionPayment.objects.create(
            subscription=self.subscription,
            amount=20,
            payment_date='2026-01-31',
        )
        allocate_payment(payment, allocation_type='contract_advance')
        allocation = payment.allocations.get()
        self.assertEqual(allocation.allocation_type, 'contract_advance')
        self.assertIsNone(allocation.installment_id)
        self.assertEqual(allocation.amount, 20)

    def test_new_schedule_keeps_previous_plan_as_history(self):
        old_plan = self._plan(installment_count=2)
        new_plan = self._plan(installment_count=4, scheduled_amount=80)
        old_plan.refresh_from_db()
        self.assertEqual(old_plan.status, 'superseded')
        self.assertEqual(new_plan.version, 2)
        self.assertEqual(old_plan.installments.count(), 2)
        self.assertEqual(new_plan.installments.count(), 4)
