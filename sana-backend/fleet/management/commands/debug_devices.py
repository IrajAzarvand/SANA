from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Exists, OuterRef

from fleet.models import Device
from organizations.models import SubscriptionDevice


class Command(BaseCommand):
    help = 'دیباگ دستگاه‌ها و اتصالات قرارداد'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('\n' + '=' * 70))
        self.stdout.write(self.style.SUCCESS('دیباگ دستگاه‌ها'))
        self.stdout.write(self.style.SUCCESS('=' * 70 + '\n'))

        # ─── ۱. تعداد کل ───
        total = Device.objects.count()
        self.stdout.write(f'📊 تعداد کل دستگاه‌ها: {total}\n')

        # ─── ۲. تعداد SubscriptionDevice ───
        total_links = SubscriptionDevice.objects.count()
        active_links = SubscriptionDevice.objects.filter(unassigned_at__isnull=True).count()
        inactive_links = SubscriptionDevice.objects.filter(unassigned_at__isnull=False).count()

        self.stdout.write(f'🔗 تعداد SubscriptionDevice کل: {total_links}')
        self.stdout.write(f'   ├── فعال (unassigned_at=None): {active_links}')
        self.stdout.write(f'   └── بسته‌شده (unassigned_at پر): {inactive_links}\n')

        # ─── ۳. لیست همه‌ی دستگاه‌ها ───
        self.stdout.write('📱 لیست دستگاه‌ها:')
        self.stdout.write('-' * 70)

        for d in Device.objects.all().order_by('id'):
            self.stdout.write(f'\n🔹 Device ID: {d.id}')
            self.stdout.write(f'   IMEI: {d.imei}')
            self.stdout.write(f'   Model: {d.device_model.name if d.device_model else "—"}')
            self.stdout.write(f'   Status: {d.management_status}')
            self.stdout.write(f'   Organization: {d.organization.name if d.organization else "—"}')
            self.stdout.write(f'   Owner: {d.owner_user.username if d.owner_user else "—"}')

            # لینک‌های این دستگاه
            links = d.subscription_links.all()
            if links.count() == 0:
                self.stdout.write(self.style.WARNING('   └── هیچ SubscriptionDevice نداره'))
            else:
                for link in links:
                    status = '🟢 فعال' if link.unassigned_at is None else '⚪ بسته'
                    self.stdout.write(
                        f'   └── Link #{link.id}: {status} | '
                        f'Contract: {link.subscription.contract_number} | '
                        f'unassigned_at: {link.unassigned_at}'
                    )

            # چک is_in_warehouse property
            self.stdout.write(f'   📦 is_in_warehouse (property): {d.is_in_warehouse}')

        # ─── ۴. چک Exists/OuterRef ───
        self.stdout.write('\n' + '=' * 70)
        self.stdout.write('🧪 تست Exists/OuterRef:')
        self.stdout.write('=' * 70 + '\n')

        active_links_q = SubscriptionDevice.objects.filter(
            device=OuterRef('pk'),
            unassigned_at__isnull=True,
        )
        in_warehouse = Device.objects.annotate(
            has_active_link=Exists(active_links_q)
        ).filter(has_active_link=False)

        self.stdout.write(f'📦 دستگاه‌های در انبار (با Exists): {in_warehouse.count()}')

        for d in in_warehouse:
            self.stdout.write(f'   ✅ {d.imei}')

        # ─── ۵. چک exclude ───
        self.stdout.write('\n' + '=' * 70)
        self.stdout.write('🧪 تست exclude:')
        self.stdout.write('=' * 70 + '\n')

        in_warehouse_exclude = Device.objects.exclude(
            subscription_links__unassigned_at__isnull=True
        ).distinct()

        self.stdout.write(f'📦 دستگاه‌های در انبار (با exclude): {in_warehouse_exclude.count()}')

        for d in in_warehouse_exclude:
            self.stdout.write(f'   ✅ {d.imei}')

        # ─── ۶. همه‌ی SubscriptionDeviceهای فعال ───
        self.stdout.write('\n' + '=' * 70)
        self.stdout.write('🔗 همه‌ی SubscriptionDeviceهای فعال:')
        self.stdout.write('=' * 70 + '\n')

        for link in SubscriptionDevice.objects.filter(unassigned_at__isnull=True).select_related('device', 'subscription'):
            self.stdout.write(
                f'   Device: {link.device.imei} | '
                f'Contract: {link.subscription.contract_number} | '
                f'Assigned: {link.assigned_at} | '
                f'Start: {link.start_date} | '
                f'End: {link.end_date}'
            )

        self.stdout.write('\n' + '=' * 70 + '\n')
