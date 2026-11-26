from django.test import TestCase
from rest_framework.test import APIClient
from unittest.mock import patch

from accounts.models import User
from fleet.models import Device, Vehicle, Driver, VehicleType, DeviceCustomerAccessPeriod, DeviceOperation, DeviceLifecycleEvent
from organizations.models import (
    Branch, Organization, Subscription, SubscriptionDevice, SubscriptionPayment, SubscriptionOperation,
    SubscriptionInstallmentPlan, SubscriptionInstallment, SubscriptionPaymentAllocation,
)
from organizations.financial import create_installment_plan, allocate_payment, revise_installment_plan
from rest_framework.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta
from django.db import transaction
from django.db.models import Sum
from .serializers import SubscriptionWizardSerializer, SubscriptionPaymentSerializer


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

    def test_new_user_rejects_weak_passwords(self):
        for username, password in [
            ('wizard-numeric-password', '12345678'),
            ('wizard-common-password', 'password'),
            ('wizard-similar-password', 'wizard-similar-password'),
        ]:
            with self.subTest(username=username):
                payload = self._payload(
                    existing_user_id=None,
                    username=username,
                    password=password,
                    contract_number=f'PRS-{username.upper()}',
                )
                serializer = SubscriptionWizardSerializer(data=payload)
                self.assertFalse(serializer.is_valid())
                self.assertIn('password', serializer.errors)
                self.assertFalse(User.objects.filter(username=username).exists())

    def test_new_user_accepts_a_strong_password(self):
        payload = self._payload(
            existing_user_id=None,
            username='wizard-strong-password-user',
            password='N0t-Common-Password!739',
            contract_number='PRS-WIZARD-STRONG-PASSWORD',
        )
        serializer = SubscriptionWizardSerializer(data=payload)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        subscription = serializer.save()
        user = User.objects.get(username='wizard-strong-password-user')
        self.assertEqual(subscription.user_id, user.pk)
        self.assertTrue(user.check_password('N0t-Common-Password!739'))


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
        self.device.management_status = 'installed'
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
        self.assertEqual(self.device.management_status, 'installed')
        access = DeviceCustomerAccessPeriod.objects.get(device=self.device, ended_at__isnull=True)
        self.assertEqual(access.user_id, self.user.id)
        self.assertEqual(access.organization_id, None)
        self.assertEqual(access.subscription_id, subscription.id)

class SubscriptionContractNumberUniquenessTests(TestCase):
    def test_contract_number_cannot_duplicate_any_existing_contract(self):
        existing_number = 'PRS-TEST-DUPLICATE'
        organization = Organization.objects.create(
            name='Contract Number Test Org',
            code='CONTRACT-NUMBER-TEST-ORG',
        )
        Subscription.objects.create(
            contract_number=existing_number,
            customer_type='organization',
            organization=organization,
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
        user = User.objects.create_user(
            username='fin-test-personal',
            password='test-password',
            account_type='personal',
            role='personal_user',
        )
        subscription = Subscription.objects.create(
            contract_number='FIN-TEST-0001',
            customer_type='personal',
            user=user,
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
            received_at='2026-12-07',
        )

        subscription.refresh_from_db()
        self.assertEqual(subscription.price, 100000000)
        self.assertEqual(
            sum(payment.amount for payment in subscription.payments.all()),
            50000000,
        )



class SubscriptionInstallmentLedgerTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(
            username='inst-test-personal',
            password='test-password',
            account_type='personal',
            role='personal_user',
        )
        self.subscription = Subscription.objects.create(
            contract_number='INST-TEST-0001',
            customer_type='personal',
            user=user,
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
            received_at='2026-04-01',
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
            received_at='2026-01-15',
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
            received_at='2026-01-15',
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
            received_at='2026-01-10',
        )
        allocate_payment(
            payment,
            mode='manual',
            allocations=[{'installment_id': second.id, 'amount': 25}],
        )
        allocation = payment.allocations.get()
        self.assertEqual(allocation.installment_id, second.id)
        self.assertEqual(allocation.amount, 25)

    def test_same_receipt_can_be_allocated_in_multiple_events_to_same_installment(self):
        plan = self._plan(installment_count=2)
        first = plan.installments.get(number=1)
        payment = SubscriptionPayment.objects.create(
            subscription=self.subscription,
            amount=30,
            received_at='2026-01-10',
        )
        allocate_payment(
            payment,
            mode='manual',
            allocations=[{'installment_id': first.id, 'amount': 10}],
        )
        allocate_payment(
            payment,
            mode='manual',
            allocations=[{'installment_id': first.id, 'amount': 10}],
        )
        self.assertEqual(payment.allocations.count(), 2)
        self.assertEqual(first.allocations.aggregate(total=Sum('amount'))['total'], 20)
        self.assertEqual(payment.amount - payment.allocations.aggregate(total=Sum('amount'))['total'], 10)

    def test_manual_allocation_cannot_exceed_receipt_or_installment_balance(self):
        plan = self._plan(installment_count=2)
        first = plan.installments.get(number=1)
        payment = SubscriptionPayment.objects.create(
            subscription=self.subscription,
            amount=20,
            received_at='2026-01-10',
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
            received_at='2026-04-01',
        )
        allocate_payment(payment)
        allocated = payment.allocations.aggregate(
            total=Sum('amount')
        )['total']
        self.assertEqual(allocated, 100)
        self.assertEqual(payment.amount - allocated, 30)

    def test_payment_api_payment_date_alias_maps_to_received_at(self):
        today = timezone.localdate()
        serializer = SubscriptionPaymentSerializer(data={
            'subscription': self.subscription.id,
            'amount': 10,
            'payment_date': today.isoformat(),
            'description': 'تست تاریخ دریافت',
        })
        self.assertTrue(serializer.is_valid(), serializer.errors)
        payment = serializer.save()
        self.assertEqual(payment.received_at, today)

    def test_payment_api_rejects_future_receipt_date(self):
        future_date = timezone.localdate() + timedelta(days=1)
        serializer = SubscriptionPaymentSerializer(data={
            'subscription': self.subscription.id,
            'amount': 10,
            'payment_date': future_date.isoformat(),
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn('payment_date', serializer.errors)

    def test_contract_advance_is_not_mistaken_for_installment_or_credit(self):
        payment = SubscriptionPayment.objects.create(
            subscription=self.subscription,
            amount=20,
            received_at='2026-01-31',
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
        self.assertEqual(old_plan.installments.filter(status='superseded').count(), 2)
        self.assertEqual(new_plan.version, 2)
        self.assertEqual(old_plan.installments.count(), 2)
        self.assertEqual(new_plan.installments.count(), 4)


    def test_contract_price_change_rebalances_only_the_unpaid_schedule(self):
        old_plan = self._plan(installment_count=2)
        first, _ = list(old_plan.installments.order_by('number'))
        receipt = SubscriptionPayment.objects.create(
            subscription=self.subscription,
            amount=50,
            received_at=first.due_date,
        )
        allocate_payment(
            receipt,
            mode='manual',
            allocations=[{'installment_id': first.id, 'amount': 50}],
        )

        new_plan = revise_installment_plan(
            self.subscription,
            {
                'contract_price': 120,
                'installment_count': 2,
                'interval_months': 2,
                'calculation_mode': 'equal',
                'surplus_policy': 'credit',
            },
        )
        self.subscription.refresh_from_db()
        old_plan.refresh_from_db()
        first.refresh_from_db()
        self.assertEqual(self.subscription.price, 120)
        self.assertEqual(old_plan.status, 'superseded')
        self.assertEqual(first.amount, 50)
        self.assertEqual(first.allocations.get().amount, 50)
        self.assertEqual(new_plan.scheduled_amount, 70)
        self.assertEqual(
            list(new_plan.installments.order_by('number').values_list('amount', flat=True)),
            [35, 35],
        )

    def test_contract_price_cannot_be_reduced_below_already_allocated_amount(self):
        plan = self._plan(installment_count=2)
        first = plan.installments.get(number=1)
        receipt = SubscriptionPayment.objects.create(
            subscription=self.subscription,
            amount=50,
            received_at=first.due_date,
        )
        allocate_payment(
            receipt,
            mode='manual',
            allocations=[{'installment_id': first.id, 'amount': 50}],
        )
        with self.assertRaises(ValidationError):
            revise_installment_plan(
                self.subscription,
                {
                    'contract_price': 40,
                    'installment_count': 2,
                    'interval_months': 2,
                    'calculation_mode': 'equal',
                    'surplus_policy': 'credit',
                },
            )
        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.price, 100)

    def test_schedule_revision_preserves_paid_and_partially_paid_installments(self):
        old_plan = self._plan(installment_count=2)
        first, second = list(old_plan.installments.order_by('number'))

        full_receipt = SubscriptionPayment.objects.create(
            subscription=self.subscription,
            amount=50,
            received_at=first.due_date,
        )
        allocate_payment(
            full_receipt,
            mode='manual',
            allocations=[{'installment_id': first.id, 'amount': 50}],
        )
        partial_receipt = SubscriptionPayment.objects.create(
            subscription=self.subscription,
            amount=20,
            received_at=second.due_date,
        )
        allocate_payment(
            partial_receipt,
            mode='manual',
            allocations=[{'installment_id': second.id, 'amount': 20}],
        )

        revised = revise_installment_plan(
            self.subscription,
            {
                'installment_count': 1,
                'interval_months': 2,
                'calculation_mode': 'equal',
                'surplus_policy': 'credit',
            },
        )

        old_plan.refresh_from_db()
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(old_plan.status, 'superseded')
        self.assertEqual(first.amount, 50)
        self.assertEqual(first.allocations.get().amount, 50)
        self.assertEqual(second.amount, 50)
        self.assertEqual(second.allocations.get().amount, 20)
        self.assertEqual(revised.scheduled_amount, 30)
        revised_installment = revised.installments.get()
        self.assertEqual(revised_installment.amount, 30)
        self.assertEqual(revised_installment.due_date, second.due_date)


class PersonalSubscriptionReadOnlyAccessTests(TestCase):
    def setUp(self):
        from datetime import timedelta

        self.client = APIClient()
        self.personal_user = User.objects.create_user(
            username='contract-view-owner',
            password='test-password',
            role='personal_user',
            account_type='personal',
        )
        self.other_user = User.objects.create_user(
            username='contract-view-other',
            password='test-password',
            role='personal_user',
            account_type='personal',
        )
        today = timezone.localdate()
        self.own_subscription = Subscription.objects.create(
            contract_number='PERSONAL-VIEW-001',
            customer_type='personal',
            user=self.personal_user,
            start_date=today - timedelta(days=10),
            end_date=today + timedelta(days=100),
            price=1000000,
        )
        self.other_subscription = Subscription.objects.create(
            contract_number='PERSONAL-VIEW-002',
            customer_type='personal',
            user=self.other_user,
            start_date=today - timedelta(days=10),
            end_date=today + timedelta(days=100),
            price=1000000,
        )

    def test_site_admin_cannot_bypass_contract_operation_log_with_direct_patch(self):
        admin = User.objects.create_user(
            username='contract-update-admin',
            password='test-password',
            role='site_admin',
            account_type='admin',
            is_staff=True,
            is_superuser=True,
        )
        self.client.force_authenticate(user=admin)

        response = self.client.patch(
            f'/api/subscriptions/{self.own_subscription.id}/',
            {'notes': 'ویرایش بدون سابقه'},
            format='json',
        )

        self.assertEqual(response.status_code, 405)
        self.own_subscription.refresh_from_db()
        self.assertEqual(self.own_subscription.notes, '')
        self.assertFalse(self.own_subscription.operations.exists())

    def test_site_admin_cannot_delete_contract_and_must_use_cancel_operation(self):
        admin = User.objects.create_user(
            username='contract-delete-admin',
            password='test-password',
            role='site_admin',
            account_type='admin',
            is_staff=True,
            is_superuser=True,
        )
        self.client.force_authenticate(user=admin)

        response = self.client.delete(f'/api/subscriptions/{self.own_subscription.id}/')

        self.assertEqual(response.status_code, 405)
        self.assertTrue(Subscription.objects.filter(pk=self.own_subscription.pk).exists())
        self.assertFalse(self.own_subscription.operations.exists())

    def test_site_admin_cannot_update_device_directly_and_delete_is_audited(self):
        admin = User.objects.create_user(
            username='subscription-device-admin',
            password='test-password',
            role='site_admin',
            account_type='admin',
            is_staff=True,
            is_superuser=True,
        )
        device = Device.objects.create(imei='555555555555555')
        link = SubscriptionDevice.objects.create(
            subscription=self.own_subscription,
            device=device,
            start_date=self.own_subscription.start_date,
            end_date=self.own_subscription.end_date,
        )
        self.client.force_authenticate(user=admin)
        before_operations = SubscriptionOperation.objects.count()

        patch_response = self.client.patch(
            f'/api/subscription-devices/{link.id}/',
            {'end_date': '2028-01-01'},
            format='json',
        )
        put_response = self.client.put(
            f'/api/subscription-devices/{link.id}/',
            {
                'subscription': self.own_subscription.id,
                'device': device.id,
                'start_date': '2026-11-07',
                'end_date': '2028-01-01',
            },
            format='json',
        )

        self.assertEqual(patch_response.status_code, 405)
        self.assertEqual(put_response.status_code, 405)
        link.refresh_from_db()
        self.assertEqual(link.end_date, self.own_subscription.end_date)
        self.assertEqual(SubscriptionOperation.objects.count(), before_operations)

        with patch('organizations.views.record_device_lifecycle_event'):
            delete_response = self.client.delete(f'/api/subscription-devices/{link.id}/')

        self.assertEqual(delete_response.status_code, 204)
        link.refresh_from_db()
        self.assertIsNotNone(link.unassigned_at)
        self.assertIsNotNone(link.removed_by_operation_id)
        self.assertEqual(link.removed_by_operation.operation_type, 'remove_device')
        self.assertEqual(SubscriptionOperation.objects.count(), before_operations + 1)

    def test_site_admin_cannot_update_or_delete_payment_directly(self):
        admin = User.objects.create_user(
            username='subscription-payment-admin',
            password='test-password',
            role='site_admin',
            account_type='admin',
            is_staff=True,
            is_superuser=True,
        )
        payment = SubscriptionPayment.objects.create(
            subscription=self.own_subscription,
            amount=250000,
            received_at=timezone.localdate(),
            description='رسید اولیه',
        )
        self.client.force_authenticate(user=admin)
        before_operations = SubscriptionOperation.objects.count()

        patch_response = self.client.patch(
            f'/api/subscription-payments/{payment.id}/',
            {'amount': 500000, 'description': 'تغییر بدون سابقه'},
            format='json',
        )
        delete_response = self.client.delete(f'/api/subscription-payments/{payment.id}/')

        self.assertEqual(patch_response.status_code, 405)
        self.assertEqual(delete_response.status_code, 405)
        payment.refresh_from_db()
        self.assertEqual(payment.amount, 250000)
        self.assertEqual(payment.description, 'رسید اولیه')
        self.assertTrue(SubscriptionPayment.objects.filter(pk=payment.pk).exists())
        self.assertEqual(SubscriptionOperation.objects.count(), before_operations)

    def test_personal_customer_can_view_own_contract_details(self):
        self.client.force_authenticate(user=self.personal_user)

        response = self.client.get(f'/api/subscriptions/{self.own_subscription.id}/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['id'], self.own_subscription.id)
        self.assertEqual(response.data['contract_number'], self.own_subscription.contract_number)

    def test_personal_customer_cannot_view_another_customers_contract(self):
        self.client.force_authenticate(user=self.personal_user)

        response = self.client.get(f'/api/subscriptions/{self.other_subscription.id}/')

        self.assertEqual(response.status_code, 404)

    def test_personal_customer_cannot_modify_or_change_contract_status(self):
        self.client.force_authenticate(user=self.personal_user)

        update_response = self.client.patch(
            f'/api/subscriptions/{self.own_subscription.id}/',
            {'notes': 'تغییر غیرمجاز'},
            format='json',
        )
        suspend_response = self.client.post(
            f'/api/subscriptions/{self.own_subscription.id}/suspend/',
            {},
            format='json',
        )
        cancel_response = self.client.post(
            f'/api/subscriptions/{self.own_subscription.id}/cancel/',
            {},
            format='json',
        )

        self.assertEqual(update_response.status_code, 403)
        self.assertEqual(suspend_response.status_code, 403)
        self.assertEqual(cancel_response.status_code, 403)

        self.own_subscription.refresh_from_db()
        self.assertEqual(self.own_subscription.status, 'active')
        self.assertEqual(self.own_subscription.notes, '')


class OrganizationAndBranchDeletionPermissionTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.organization = Organization.objects.create(
            name='Deletion Test Organization',
            code='DELETE-ORG-TEST',
        )
        from organizations.models import Branch
        self.branch = Branch.objects.create(
            organization=self.organization,
            name='Deletion Test Branch',
            code='DELETE-BR-TEST',
        )
        self.company_manager = User.objects.create_user(
            username='delete-test-company-manager',
            password='test-password',
            role='main_user',
            account_type='organization',
            organization=self.organization,
        )
        self.site_admin = User.objects.create_user(
            username='delete-test-site-admin',
            password='test-password',
            role='site_admin',
            account_type='admin',
            is_staff=True,
            is_superuser=True,
        )

    def test_organization_and_branch_list_include_relationship_counts(self):
        self.client.force_authenticate(user=self.site_admin)
        organization_response = self.client.get(f'/api/organizations/{self.organization.id}/')
        organization_list_response = self.client.get('/api/organizations/')
        branch_response = self.client.get('/api/branches/')

        self.assertEqual(organization_response.status_code, 200)
        self.assertIn('subscriptions_count', organization_response.data)
        self.assertIn('users_count', organization_response.data)
        self.assertEqual(organization_list_response.status_code, 200)
        list_data = organization_list_response.data['results'] if isinstance(organization_list_response.data, dict) else organization_list_response.data
        self.assertTrue(any(
            item['id'] == self.organization.id
            and 'drivers_count' in item
            and 'vehicle_types_count' in item
            for item in list_data
        ))
        self.assertEqual(branch_response.status_code, 200)
        branch_data = branch_response.data['results'] if isinstance(branch_response.data, dict) else branch_response.data
        self.assertTrue(any(
            item['id'] == self.branch.id and 'users_count' in item
            for item in branch_data
        ))

    def test_organization_detail_reports_driver_and_vehicle_type_counts(self):
        Driver.objects.create(
            organization=self.organization,
            branch=self.branch,
            first_name='Test',
            last_name='Driver',
            mobile='09120000001',
        )
        VehicleType.objects.create(
            organization=self.organization,
            name='Test Vehicle Type',
        )
        Vehicle.objects.create(
            organization=self.organization,
            branch=self.branch,
            plate='BRCOUNTTEST01',
        )
        Device.objects.create(
            imei='987654321098761',
            organization=self.organization,
            branch=self.branch,
        )
        self.client.force_authenticate(user=self.site_admin)
        response = self.client.get(f'/api/organizations/{self.organization.id}/')
        branch_response = self.client.get(f'/api/branches/{self.branch.id}/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['drivers_count'], 1)
        self.assertEqual(response.data['vehicle_types_count'], 1)
        self.assertEqual(branch_response.status_code, 200)
        self.assertEqual(branch_response.data['drivers_count'], 1)
        self.assertEqual(branch_response.data['vehicles_count'], 1)
        self.assertEqual(branch_response.data['devices_count'], 1)

    def test_subscription_list_can_be_scoped_to_organization(self):
        today = timezone.localdate()
        other_organization = Organization.objects.create(
            name='Other Test Organization',
            code='DELETE-ORG-OTHER',
        )
        own_contract = Subscription.objects.create(
            contract_number='DELETE-ORG-CONTRACT-001',
            customer_type='organization',
            organization=self.organization,
            start_date=today,
            end_date=today + timedelta(days=30),
            price=1000,
        )
        other_contract = Subscription.objects.create(
            contract_number='DELETE-ORG-CONTRACT-002',
            customer_type='organization',
            organization=other_organization,
            start_date=today,
            end_date=today + timedelta(days=30),
            price=1000,
        )
        self.client.force_authenticate(user=self.site_admin)
        response = self.client.get(f'/api/subscriptions/?organization={self.organization.id}')

        self.assertEqual(response.status_code, 200)
        contract_data = response.data['results'] if isinstance(response.data, dict) else response.data
        contract_ids = {item['id'] for item in contract_data}
        self.assertIn(own_contract.id, contract_ids)
        self.assertNotIn(other_contract.id, contract_ids)

    def test_company_manager_cannot_physically_delete_organization(self):
        self.client.force_authenticate(user=self.company_manager)
        response = self.client.delete(f'/api/organizations/{self.organization.id}/')
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Organization.objects.filter(pk=self.organization.pk).exists())

    def test_site_admin_company_delete_archives_and_preserves_all_related_records(self):
        today = timezone.localdate()
        vehicle = Vehicle.objects.create(
            organization=self.organization,
            branch=self.branch,
            plate='ORGARCHIVE01',
        )
        driver = Driver.objects.create(
            organization=self.organization,
            branch=self.branch,
            first_name='Archive',
            last_name='Driver',
            mobile='09120000002',
        )
        device = Device.objects.create(
            imei='987654321098765',
            organization=self.organization,
            branch=self.branch,
        )
        subscription = Subscription.objects.create(
            contract_number='DELETE-ORG-ARCHIVE-001',
            customer_type='organization',
            organization=self.organization,
            start_date=today,
            end_date=today + timedelta(days=30),
            price=1000,
        )
        payment = SubscriptionPayment.objects.create(
            subscription=subscription,
            amount=1000,
            received_at=today,
            description='Archived company payment history',
        )
        plan = create_installment_plan(
            subscription,
            {
                'scheduled_amount': 1000,
                'installment_count': 1,
                'interval_months': 1,
                'calculation_mode': 'equal',
                'first_due_date': today + timedelta(days=30),
            },
            created_by=self.site_admin,
        )
        allocate_payment(
            payment,
            allocation_type='contract_advance',
            allocation_amount=1000,
        )
        manager = self.company_manager

        self.client.force_authenticate(user=self.site_admin)
        response = self.client.post(f'/api/organizations/{self.organization.id}/archive/')

        self.assertEqual(response.status_code, 200)
        self.organization.refresh_from_db()
        self.assertEqual(self.organization.status, 'archived')
        self.assertIsNotNone(self.organization.archived_at)
        self.assertEqual(self.organization.archived_by, self.site_admin)
        self.assertEqual(self.organization.archived_from_status, 'active')
        self.assertTrue(self.branch.__class__.objects.filter(pk=self.branch.pk).exists())
        self.assertTrue(Vehicle.objects.filter(pk=vehicle.pk).exists())
        self.assertTrue(Device.objects.filter(pk=device.pk).exists())
        self.assertTrue(Driver.objects.filter(pk=driver.pk).exists())
        self.assertTrue(Subscription.objects.filter(pk=subscription.pk).exists())
        self.assertTrue(SubscriptionPayment.objects.filter(pk=payment.pk).exists())
        self.assertTrue(SubscriptionInstallmentPlan.objects.filter(pk=plan.pk).exists())
        self.assertTrue(SubscriptionPaymentAllocation.objects.filter(payment=payment).exists())
        manager.refresh_from_db()
        self.assertEqual(manager.organization_id, self.organization.pk)

        self.client.force_authenticate(user=self.company_manager)
        hidden_response = self.client.get(f'/api/organizations/{self.organization.id}/')
        self.assertEqual(hidden_response.status_code, 404)
        self.assertEqual(self.client.get('/api/branches/').data['count'], 0)
        self.assertEqual(self.client.get('/api/vehicles/').data['count'], 0)
        self.assertEqual(self.client.get('/api/drivers/').data['count'], 0)
        self.assertEqual(self.client.get('/api/subscriptions/').data['count'], 0)
        self.assertEqual(self.client.get('/api/users/').data['count'], 0)

    def test_site_admin_can_restore_archived_company_without_losing_history(self):
        self.organization.status = 'archived'
        self.organization.archived_from_status = 'suspended'
        self.organization.archived_at = timezone.now()
        self.organization.archived_by = self.site_admin
        self.organization.save(update_fields=['status', 'archived_from_status', 'archived_at', 'archived_by'])

        self.client.force_authenticate(user=self.site_admin)
        response = self.client.post(f'/api/organizations/{self.organization.id}/restore/')

        self.assertEqual(response.status_code, 200)
        self.organization.refresh_from_db()
        self.assertEqual(self.organization.status, 'suspended')
        self.assertIsNone(self.organization.archived_at)
        self.assertIsNone(self.organization.archived_by)


class SubscriptionPaymentMutationValidationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            username='payment-mutation-admin',
            password='test-password-123',
            account_type='admin',
            role='site_admin',
            is_staff=True,
            is_superuser=True,
        )
        self.client.force_authenticate(user=self.admin)
        user = User.objects.create_user(
            username='payment-mutation-customer',
            password='test-password-123',
            account_type='personal',
            role='personal_user',
        )
        today = timezone.localdate()
        self.subscription = Subscription.objects.create(
            contract_number='PAYMENT-MUTATION-CONTRACT',
            customer_type='personal',
            user=user,
            start_date=today - timedelta(days=10),
            end_date=today + timedelta(days=30),
            status='active',
            price=1000,
        )
        self.payment = SubscriptionPayment.objects.create(
            subscription=self.subscription,
            amount=500,
            received_at=today,
            description='Original receipt',
        )

    def test_valid_payment_edit_is_saved_and_audited(self):
        response = self.client.post(
            f'/api/subscriptions/{self.subscription.pk}/modify/',
            {
                'contract_changes': {},
                'payment_changes': [
                    {
                        'id': self.payment.pk,
                        'amount': 600,
                        'description': 'Updated receipt',
                    }
                ],
            },
            format='json',
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.amount, 600)
        self.assertEqual(self.payment.description, 'Updated receipt')
        operation = self.subscription.operations.get(operation_type='modify')
        self.assertEqual(
            set(operation.changes.values_list('field_name', flat=True)),
            {'amount', 'description'},
        )

    def test_payment_edit_rejects_non_positive_amount_without_partial_write(self):
        response = self.client.post(
            f'/api/subscriptions/{self.subscription.pk}/modify/',
            {
                'contract_changes': {},
                'payment_changes': [{'id': self.payment.pk, 'amount': 0}],
            },
            format='json',
        )
        self.assertEqual(response.status_code, 400, response.data)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.amount, 500)
        self.assertEqual(self.payment.description, 'Original receipt')
        self.assertEqual(self.subscription.operations.count(), 0)

    def test_payment_edit_rejects_future_receipt_date_without_partial_write(self):
        future_date = (timezone.localdate() + timedelta(days=1)).isoformat()
        response = self.client.post(
            f'/api/subscriptions/{self.subscription.pk}/modify/',
            {
                'contract_changes': {},
                'payment_changes': [{'id': self.payment.pk, 'payment_date': future_date}],
            },
            format='json',
        )
        self.assertEqual(response.status_code, 400, response.data)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.received_at, timezone.localdate())
        self.assertEqual(self.subscription.operations.count(), 0)

    def test_payment_edit_rejects_duplicate_receipt_ids(self):
        response = self.client.post(
            f'/api/subscriptions/{self.subscription.pk}/modify/',
            {
                'contract_changes': {},
                'payment_changes': [
                    {'id': self.payment.pk, 'description': 'First'},
                    {'id': self.payment.pk, 'description': 'Second'},
                ],
            },
            format='json',
        )
        self.assertEqual(response.status_code, 400, response.data)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.description, 'Original receipt')
        self.assertEqual(self.subscription.operations.count(), 0)


class SubscriptionDeviceCustomerAccessClosureTests(TestCase):
    """Removing a device from a contract must close access without rewriting history or ownership."""

    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            username='access-close-admin',
            password='test-password',
            role='site_admin',
            account_type='admin',
            is_staff=True,
            is_superuser=True,
        )
        self.customer = User.objects.create_user(
            username='access-close-customer',
            password='test-password',
            role='personal_user',
            account_type='personal',
        )
        today = timezone.localdate()
        self.subscription = Subscription.objects.create(
            contract_number='ACCESS-CLOSE-001',
            customer_type='personal',
            user=self.customer,
            start_date=today - timedelta(days=5),
            end_date=today + timedelta(days=90),
            price=1000,
        )
        self.device = Device.objects.create(
            imei='888888888888881',
            owner_user=self.customer,
            management_status='installed',
        )
        self.link = SubscriptionDevice.objects.create(
            subscription=self.subscription,
            device=self.device,
            start_date=self.subscription.start_date,
            end_date=self.subscription.end_date,
        )
        self.original_link_end_date = self.link.end_date
        self.access_started_at = timezone.now() - timedelta(days=2)
        self.access = DeviceCustomerAccessPeriod.objects.create(
            device=self.device,
            user=self.customer,
            subscription=self.subscription,
            started_at=self.access_started_at,
            reason='contract_assignment',
        )
        self.client.force_authenticate(user=self.admin)

    def _assert_access_closed_and_history_preserved(self):
        self.link.refresh_from_db()
        self.access.refresh_from_db()
        self.device.refresh_from_db()

        self.assertIsNotNone(self.link.unassigned_at)
        self.assertIsNotNone(self.link.removed_by_operation_id)
        self.assertEqual(self.link.end_date, self.original_link_end_date)
        self.assertTrue(SubscriptionDevice.objects.filter(pk=self.link.pk).exists())

        self.assertIsNotNone(self.access.ended_at)
        self.assertTrue(DeviceCustomerAccessPeriod.objects.filter(pk=self.access.pk).exists())
        self.assertEqual(self.access.device_id, self.device.pk)
        self.assertEqual(self.access.user_id, self.customer.pk)
        self.assertIsNone(self.access.organization_id)
        self.assertEqual(self.access.subscription_id, self.subscription.pk)
        self.assertEqual(self.access.started_at, self.access_started_at)

        # Ending access is not an ownership transfer or a device lifecycle/status change.
        self.assertEqual(self.device.owner_user_id, self.customer.pk)
        self.assertIsNone(self.device.organization_id)
        self.assertEqual(self.device.management_status, 'installed')

    def test_renew_rejects_non_string_date_without_server_error(self):
        response = self.client.post(
            f'/api/subscriptions/{self.subscription.pk}/renew/',
            {'new_end_date': 12345},
            format='json',
        )
        self.assertEqual(response.status_code, 400, response.data)
        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.end_date, timezone.localdate() + timedelta(days=90))

    def test_modify_rejects_empty_contract_date_without_server_error(self):
        response = self.client.post(
            f'/api/subscriptions/{self.subscription.pk}/modify/',
            {'contract_changes': {'end_date': ''}},
            format='json',
        )
        self.assertEqual(response.status_code, 400, response.data)
        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.end_date, timezone.localdate() + timedelta(days=90))

    def test_modify_rejects_malformed_device_removal_ids(self):
        response = self.client.post(
            f'/api/subscriptions/{self.subscription.pk}/modify/',
            {'contract_changes': {}, 'remove_device_ids': 'not-a-list'},
            format='json',
        )
        self.assertEqual(response.status_code, 400, response.data)
        self.assertIsNone(self.link.unassigned_at)

    def test_modify_rejects_malformed_add_device_payload(self):
        response = self.client.post(
            f'/api/subscriptions/{self.subscription.pk}/modify/',
            {'contract_changes': {}, 'add_devices': ['not-an-object']},
            format='json',
        )
        self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(
            self.subscription.subscription_devices.filter(unassigned_at__isnull=True).count(),
            1,
        )

    def test_renew_closes_access_when_device_is_removed(self):
        new_end_date = timezone.localdate() + timedelta(days=180)
        with patch('organizations.views.record_device_lifecycle_event'):
            response = self.client.post(
                f'/api/subscriptions/{self.subscription.pk}/renew/',
                {'new_end_date': new_end_date.isoformat(), 'remove_device_ids': [self.link.pk]},
                format='json',
            )

        self.assertEqual(response.status_code, 200, response.data)
        self._assert_access_closed_and_history_preserved()
        self.assertEqual(self.link.removed_by_operation.operation_type, 'renew')

    def test_modify_can_shorten_contract_when_outgoing_device_is_removed(self):
        new_end_date = timezone.localdate() + timedelta(days=10)
        with patch('organizations.views.record_device_lifecycle_event'):
            response = self.client.post(
                f'/api/subscriptions/{self.subscription.pk}/modify/',
                {
                    'contract_changes': {'end_date': new_end_date.isoformat()},
                    'remove_device_ids': [self.link.pk],
                },
                format='json',
            )

        self.assertEqual(response.status_code, 200, response.data)
        self.subscription.refresh_from_db()
        self.link.refresh_from_db()
        self.assertEqual(self.subscription.end_date, new_end_date)
        self.assertEqual(self.link.end_date, self.original_link_end_date)
        self.assertIsNotNone(self.link.unassigned_at)

    def test_modify_closes_access_when_device_is_removed(self):
        with patch('organizations.views.record_device_lifecycle_event'):
            response = self.client.post(
                f'/api/subscriptions/{self.subscription.pk}/modify/',
                {'contract_changes': {}, 'remove_device_ids': [self.link.pk]},
                format='json',
            )

        self.assertEqual(response.status_code, 200, response.data)
        self._assert_access_closed_and_history_preserved()
        self.assertEqual(self.link.removed_by_operation.operation_type, 'modify')

    def test_cancel_closes_access_for_each_active_device(self):
        with patch('organizations.views.record_device_lifecycle_event'):
            response = self.client.post(
                f'/api/subscriptions/{self.subscription.pk}/cancel/',
                {},
                format='json',
            )

        self.assertEqual(response.status_code, 200, response.data)
        self._assert_access_closed_and_history_preserved()
        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.status, 'cancelled')
        self.assertEqual(self.link.removed_by_operation.operation_type, 'cancel')

    def test_direct_device_link_delete_closes_access_and_preserves_records(self):
        with patch('organizations.views.record_device_lifecycle_event'):
            response = self.client.delete(
                f'/api/subscription-devices/{self.link.pk}/',
            )

        self.assertEqual(response.status_code, 204)
        self._assert_access_closed_and_history_preserved()
        self.assertEqual(self.link.removed_by_operation.operation_type, 'remove_device')

class BranchDeletionDataIntegrityTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.organization = Organization.objects.create(name='Branch Integrity Organization', code='BRANCH-INTEGRITY-ORG-001')
        self.branch = Branch.objects.create(organization=self.organization, name='Branch With History', code='BRANCH-INTEGRITY-001')
        self.site_admin = User.objects.create_user(username='branch-integrity-admin', password='test-password-123', role='site_admin', account_type='admin', is_staff=True, is_superuser=True)
        self.client.force_authenticate(user=self.site_admin)

    def test_branch_with_user_vehicle_and_access_history_cannot_be_deleted(self):
        User.objects.create_user(username='branch-integrity-user', password='test-password-123', role='branch_manager', account_type='organization', branch=self.branch)
        Vehicle.objects.create(organization=self.organization, branch=self.branch, plate='BRINTEGRITY01')
        driver = Driver.objects.create(
            organization=self.organization,
            branch=self.branch,
            first_name='Branch',
            last_name='Integrity',
            mobile='09120000000',
        )
        device = Device.objects.create(imei='987654321098799', organization=self.organization, branch=self.branch)
        access_period = DeviceCustomerAccessPeriod.objects.create(device=device, organization=self.organization, branch=self.branch, started_at=timezone.now())
        operation = DeviceOperation.objects.create(
            operation_type='lost',
            device=device,
            target_branch=self.branch,
        )
        lifecycle_event = DeviceLifecycleEvent.objects.create(
            device=device,
            event_type='received',
            branch=self.branch,
        )
        response = self.client.delete(f'/api/branches/{self.branch.pk}/')
        self.assertEqual(response.status_code, 409, response.data)
        self.assertTrue(Branch.objects.filter(pk=self.branch.pk).exists())
        access_period.refresh_from_db()
        self.assertEqual(access_period.branch_id, self.branch.pk)
        self.assertEqual(Device.objects.get(pk=device.pk).branch_id, self.branch.pk)
        driver.refresh_from_db()
        self.assertEqual(driver.branch_id, self.branch.pk)
        operation.refresh_from_db()
        lifecycle_event.refresh_from_db()
        self.assertEqual(operation.target_branch_id, self.branch.pk)
        self.assertEqual(lifecycle_event.branch_id, self.branch.pk)
        self.assertTrue(response.data['references'])

    def test_empty_branch_can_still_be_deleted(self):
        response = self.client.delete(f'/api/branches/{self.branch.pk}/')
        self.assertEqual(response.status_code, 204)
        self.assertFalse(Branch.objects.filter(pk=self.branch.pk).exists())

    def test_company_manager_cannot_delete_branch_even_when_empty(self):
        manager = User.objects.create_user(username='branch-integrity-manager', password='test-password-123', role='main_user', account_type='organization', organization=self.organization)
        self.client.force_authenticate(user=manager)
        response = self.client.delete(f'/api/branches/{self.branch.pk}/')
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Branch.objects.filter(pk=self.branch.pk).exists())


class SubscriptionCustomerProfileChangeTests(TestCase):
    def setUp(self):
        from organizations.views import _apply_customer_profile_changes

        def apply_changes(*args, **kwargs):
            with transaction.atomic():
                return _apply_customer_profile_changes(*args, **kwargs)

        self.apply_changes = apply_changes
        today = timezone.localdate()
        self.organization = Organization.objects.create(
            name='Shared Customer Profile Org',
            code='SHARED-CUSTOMER-PROFILE',
            email='old@example.com',
        )
        self.user = User.objects.create_user(
            username='shared-customer-profile-user',
            password='test-password-123',
            account_type='personal',
            role='personal_user',
            first_name='Old',
            last_name='Customer',
            mobile='09120000000',
            address='Old address',
        )
        self.org_subscription = Subscription.objects.create(
            contract_number='SHARED-CUSTOMER-ORG-CONTRACT',
            customer_type='organization',
            organization=self.organization,
            start_date=today,
            end_date=today + timedelta(days=30),
            status='active',
        )
        self.second_org_subscription = Subscription.objects.create(
            contract_number='SHARED-CUSTOMER-ORG-CONTRACT-2',
            customer_type='organization',
            organization=self.organization,
            start_date=today,
            end_date=today + timedelta(days=30),
            status='active',
        )
        self.personal_subscription = Subscription.objects.create(
            contract_number='SHARED-CUSTOMER-PERSONAL-CONTRACT',
            customer_type='personal',
            user=self.user,
            start_date=today,
            end_date=today + timedelta(days=30),
            status='active',
        )
        self.operation = SubscriptionOperation.objects.create(
            subscription=self.org_subscription,
            operation_type='modify',
        )

    def test_organization_profile_changes_are_validated_and_shared(self):
        self.apply_changes(
            self.org_subscription,
            {'name': 'Updated Shared Org', 'email': 'new@example.com'},
            self.operation,
        )
        self.organization.refresh_from_db()
        self.assertEqual(self.organization.name, 'Updated Shared Org')
        self.assertEqual(self.organization.email, 'new@example.com')
        self.assertEqual(
            set(self.operation.changes.values_list('field_name', flat=True)),
            {'name', 'email'},
        )
        # A second contract references the same shared Organization row.
        self.assertEqual(self.second_org_subscription.organization.name, 'Updated Shared Org')

    def test_invalid_organization_email_does_not_partially_update_profile(self):
        with self.assertRaises(ValidationError):
            self.apply_changes(
                self.org_subscription,
                {'name': 'Must Roll Back', 'email': 'not-an-email'},
                self.operation,
            )
        self.organization.refresh_from_db()
        self.assertEqual(self.organization.name, 'Shared Customer Profile Org')
        self.assertEqual(self.organization.email, 'old@example.com')
        self.assertFalse(self.operation.changes.exists())

    def test_duplicate_organization_code_is_rejected(self):
        duplicate = Organization.objects.create(
            name='Duplicate Code Org',
            code='DUPLICATE-SHARED-CODE',
        )
        with self.assertRaises(ValidationError):
            self.apply_changes(
                self.org_subscription,
                {'code': duplicate.code},
                self.operation,
            )
        self.organization.refresh_from_db()
        self.assertEqual(self.organization.code, 'SHARED-CUSTOMER-PROFILE')

    def test_organization_max_length_is_enforced(self):
        with self.assertRaises(ValidationError):
            self.apply_changes(
                self.org_subscription,
                {'name': 'x' * 201},
                self.operation,
            )
        self.organization.refresh_from_db()
        self.assertEqual(self.organization.name, 'Shared Customer Profile Org')

    def test_personal_customer_fields_are_validated(self):
        personal_operation = SubscriptionOperation.objects.create(
            subscription=self.personal_subscription,
            operation_type='modify',
        )
        with self.assertRaises(ValidationError):
            self.apply_changes(
                self.personal_subscription,
                {'mobile': '1' * 21},
                personal_operation,
            )
        self.user.refresh_from_db()
        self.assertEqual(self.user.mobile, '09120000000')

        self.apply_changes(
            self.personal_subscription,
            {'first_name': 'Updated', 'address': 'New address'},
            personal_operation,
        )
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Updated')
        self.assertEqual(self.user.address, 'New address')
        self.assertEqual(
            set(personal_operation.changes.values_list('field_name', flat=True)),
            {'first_name', 'address'},
        )

    def test_non_object_customer_changes_are_rejected_even_when_empty(self):
        with self.assertRaises(ValidationError):
            self.apply_changes(self.org_subscription, [], self.operation)
        self.organization.refresh_from_db()
        self.assertEqual(self.organization.name, 'Shared Customer Profile Org')
        self.assertFalse(self.operation.changes.exists())

    def test_unknown_customer_fields_are_rejected(self):
        with self.assertRaises(ValidationError):
            self.apply_changes(
                self.org_subscription,
                {'is_superuser': True},
                self.operation,
            )
        self.organization.refresh_from_db()
        self.assertFalse(self.user.is_superuser)
        self.assertFalse(self.operation.changes.exists())


class SubscriptionActivationLifecycleTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            username='subscription-lifecycle-admin',
            password='test-password-123',
            account_type='admin',
            role='site_admin',
            is_staff=True,
            is_superuser=True,
        )
        self.client.force_authenticate(user=self.admin)
        today = timezone.localdate()
        self.today = today

    def make_contract(self, number, status, end_offset=30):
        return Subscription.objects.create(
            contract_number=number,
            customer_type='personal',
            user=User.objects.create_user(
                username=f'{number.lower()}-user',
                password='test-password-123',
                account_type='personal',
                role='personal_user',
            ),
            start_date=self.today - timedelta(days=2),
            end_date=self.today + timedelta(days=end_offset),
            status=status,
        )

    def test_cancelled_contract_cannot_be_reactivated(self):
        contract = self.make_contract('ACTIVATE-CANCELLED', 'cancelled')
        response = self.client.post(
            f'/api/subscriptions/{contract.pk}/activate/', {}, format='json'
        )
        self.assertEqual(response.status_code, 409)
        contract.refresh_from_db()
        self.assertEqual(contract.status, 'cancelled')

    def test_expired_contract_cannot_be_reactivated(self):
        contract = self.make_contract('ACTIVATE-EXPIRED', 'expired', end_offset=-1)
        response = self.client.post(
            f'/api/subscriptions/{contract.pk}/activate/', {}, format='json'
        )
        self.assertEqual(response.status_code, 409)
        contract.refresh_from_db()
        self.assertEqual(contract.status, 'expired')

    def test_effectively_expired_active_contract_cannot_be_suspended(self):
        contract = self.make_contract('SUSPEND-COMPUTED-EXPIRED', 'active', end_offset=-1)
        response = self.client.post(
            f'/api/subscriptions/{contract.pk}/suspend/', {}, format='json'
        )
        self.assertEqual(response.status_code, 409)
        contract.refresh_from_db()
        self.assertEqual(contract.status, 'active')
        self.assertEqual(contract.computed_status, 'expired')

    def test_already_suspended_contract_cannot_create_duplicate_suspend_operation(self):
        contract = self.make_contract('SUSPEND-ALREADY-SUSPENDED', 'suspended')
        response = self.client.post(
            f'/api/subscriptions/{contract.pk}/suspend/', {}, format='json'
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(contract.operations.count(), 0)

    def test_suspended_unexpired_contract_can_be_reactivated(self):
        contract = self.make_contract('ACTIVATE-SUSPENDED', 'suspended')
        response = self.client.post(
            f'/api/subscriptions/{contract.pk}/activate/', {}, format='json'
        )
        self.assertEqual(response.status_code, 200)
        contract.refresh_from_db()
        self.assertEqual(contract.status, 'active')


class SubscriptionComputedStatusFilterTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            username='computed-status-filter-admin',
            password='test-password-123',
            account_type='admin',
            role='site_admin',
            is_staff=True,
            is_superuser=True,
        )
        self.client.force_authenticate(user=self.admin)
        today = timezone.localdate()
        self.expired = self.make_contract(
            'FILTER-COMPUTED-EXPIRED',
            today - timedelta(days=5),
            today - timedelta(days=1),
        )
        self.pending = self.make_contract(
            'FILTER-COMPUTED-PENDING',
            today + timedelta(days=1),
            today + timedelta(days=10),
        )
        self.active = self.make_contract(
            'FILTER-COMPUTED-ACTIVE',
            today,
            today + timedelta(days=10),
        )

    def make_contract(self, number, start_date, end_date):
        user = User.objects.create_user(
            username=f'{number.lower()}-user',
            password='test-password-123',
            account_type='personal',
            role='personal_user',
        )
        return Subscription.objects.create(
            contract_number=number,
            customer_type='personal',
            user=user,
            start_date=start_date,
            end_date=end_date,
            status='active',
        )

    def get_contract_ids(self, status_filter):
        response = self.client.get('/api/subscriptions/', {'status': status_filter})
        self.assertEqual(response.status_code, 200, response.data)
        results = response.data.get('results', response.data)
        return {item['id'] for item in results}

    def test_status_filters_use_effective_contract_dates(self):
        self.assertIn(self.expired.pk, self.get_contract_ids('expired'))
        self.assertIn(self.pending.pk, self.get_contract_ids('pending'))
        self.assertIn(self.active.pk, self.get_contract_ids('active'))
        self.assertNotIn(self.expired.pk, self.get_contract_ids('active'))
        self.assertNotIn(self.pending.pk, self.get_contract_ids('active'))


class SubscriptionActiveDeviceCountTests(TestCase):
    def test_active_device_count_requires_active_contract_and_active_link_window(self):
        today = timezone.localdate()
        user = User.objects.create_user(
            username='active-device-count-user',
            password='test-password-123',
            account_type='personal',
            role='personal_user',
        )
        subscription = Subscription.objects.create(
            contract_number='ACTIVE-DEVICE-COUNT',
            customer_type='personal',
            user=user,
            start_date=today,
            end_date=today + timedelta(days=30),
            status='active',
        )
        active_device = Device.objects.create(imei='860000000009953')
        future_device = Device.objects.create(imei='860000000009954')
        SubscriptionDevice.objects.create(
            subscription=subscription,
            device=active_device,
            start_date=today,
            end_date=today + timedelta(days=30),
        )
        SubscriptionDevice.objects.create(
            subscription=subscription,
            device=future_device,
            start_date=today + timedelta(days=2),
            end_date=today + timedelta(days=30),
        )

        from organizations.serializers import SubscriptionListSerializer, SubscriptionSerializer
        self.assertEqual(subscription.active_device_count, 1)
        self.assertEqual(
            SubscriptionSerializer(subscription).data['active_device_count'],
            1,
        )
        self.assertEqual(
            SubscriptionListSerializer(subscription).data['active_device_count'],
            1,
        )

        subscription.status = 'suspended'
        subscription.save(update_fields=['status'])
        self.assertEqual(
            SubscriptionSerializer(subscription).data['active_device_count'],
            0,
        )
        self.assertEqual(
            SubscriptionListSerializer(subscription).data['active_device_count'],
            0,
        )
        self.assertEqual(subscription.active_device_count, 0)
