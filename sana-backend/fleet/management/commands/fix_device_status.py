from django.core.management.base import BaseCommand
from organizations.models import SubscriptionDevice
from fleet.models import Device


class Command(BaseCommand):
    help = 'رفع وضعیت دستگاه‌هایی که توی قراردادن ولی مدیریت‌شون warehouse مونده'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('\n' + '=' * 60))
        self.stdout.write(self.style.SUCCESS('رفع وضعیت دستگاه‌ها'))
        self.stdout.write(self.style.SUCCESS('=' * 60 + '\n'))

        # دستگاه‌هایی که توی قرارداد فعالن ولی وضعیتشون warehouse مونده
        active_links = SubscriptionDevice.objects.filter(
            unassigned_at__isnull=True,
        ).select_related('device')

        fixed = 0
        for link in active_links:
            device = link.device
            if device.management_status == 'warehouse':
                device.management_status = 'sold'
                device.save(update_fields=['management_status'])
                self.stdout.write(
                    self.style.WARNING(f'✅ {device.imei} → sold')
                )
                fixed += 1
            else:
                self.stdout.write(
                    f'⏭  {device.imei} → {device.management_status} (بدون تغییر)'
                )

        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(self.style.SUCCESS(f'تعداد اصلاح‌شده: {fixed}'))
        self.stdout.write(self.style.SUCCESS('=' * 60 + '\n'))