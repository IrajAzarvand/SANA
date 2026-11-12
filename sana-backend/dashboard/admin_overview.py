from __future__ import annotations

import logging
import os
import shutil
import subprocess
import time
from datetime import timedelta
from pathlib import Path

from django.db import connection
from django.db.models import Count
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from accounts.permissions import IsSiteAdmin
from fleet.models import Device, Vehicle
from fleet.traccar_api import TraccarAPIError, traccar_devices
from organizations.models import Branch, Organization, Subscription

logger = logging.getLogger(__name__)

SERVICE_UNITS = (
    "sana-backend-production.service",
    "sana-gps.service",
    "traccar.service",
    "postgresql.service",
)



def _cpu_stats():
    def read_counters():
        try:
            line = Path("/proc/stat").read_text().splitlines()[0]
            values = [int(value) for value in line.split()[1:]]
            idle = values[3] + (values[4] if len(values) > 4 else 0)
            return sum(values), idle
        except (OSError, ValueError, IndexError):
            return None

    first = read_counters()
    if first is None:
        return {"usage_percent": None, "load_average": []}
    time.sleep(0.12)
    second = read_counters()
    usage = None
    if second is not None:
        total_delta = second[0] - first[0]
        idle_delta = second[1] - first[1]
        if total_delta > 0:
            usage = round(max(0.0, min(100.0, (1 - idle_delta / total_delta) * 100)), 1)
    try:
        load = [round(value, 2) for value in os.getloadavg()]
    except (AttributeError, OSError):
        load = []
    return {"usage_percent": usage, "load_average": load}


def _memory_stats():
    values = {}
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            key, raw = line.split(":", 1)
            parts = raw.strip().split()
            if parts:
                values[key] = int(parts[0]) * 1024
        total = values.get("MemTotal", 0)
        available = values.get("MemAvailable", 0)
        used = max(total - available, 0)
        return {
            "total_bytes": total,
            "used_bytes": used,
            "available_bytes": available,
            "used_percent": round(used * 100 / total, 1) if total else None,
        }
    except (OSError, ValueError, IndexError):
        return {"total_bytes": None, "used_bytes": None, "available_bytes": None, "used_percent": None}


def _service_states():
    result = {}
    executable = shutil.which("systemctl")
    if not executable:
        return {unit: "unknown" for unit in SERVICE_UNITS}
    for unit in SERVICE_UNITS:
        try:
            completed = subprocess.run(
                [executable, "show", unit, "--property=ActiveState", "--value"],
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
            )
            state = completed.stdout.strip() if completed.returncode == 0 else "unknown"
            result[unit] = state if state in {"active", "inactive", "failed", "activating", "deactivating"} else "unknown"
        except (OSError, subprocess.SubprocessError):
            result[unit] = "unknown"
    return result


def _server_stats():
    cpu = _cpu_stats()
    try:
        disk = shutil.disk_usage("/")
        disk_stats = {
            "total_bytes": disk.total,
            "used_bytes": disk.used,
            "free_bytes": disk.free,
            "used_percent": round(disk.used * 100 / disk.total, 1) if disk.total else None,
        }
    except OSError:
        disk_stats = {"total_bytes": None, "used_bytes": None, "free_bytes": None, "used_percent": None}

    uptime_seconds = None
    try:
        uptime_seconds = int(float(Path("/proc/uptime").read_text().split()[0]))
    except (OSError, ValueError, IndexError):
        pass

    db = {"status": "unavailable", "size_bytes": None}
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_database_size(current_database())")
            row = cursor.fetchone()
        db = {"status": "connected", "size_bytes": int(row[0]) if row else None}
    except Exception:
        logger.warning("Could not read database health for admin dashboard", exc_info=True)

    return {
        "cpu": cpu,
        "memory": _memory_stats(),
        "disk": disk_stats,
        "uptime_seconds": uptime_seconds,
        "database": db,
        "services": _service_states(),
    }


class AdminDashboardOverviewView(APIView):
    """Read-only, site-admin-only operational and business overview."""

    permission_classes = [IsAuthenticated, IsSiteAdmin]

    def get(self, request):
        today = timezone.localdate()
        soon = today + timedelta(days=30)

        device_statuses = {
            row["management_status"]: row["count"]
            for row in Device.objects.values("management_status").annotate(count=Count("id"))
        }
        org_statuses = {
            row["status"]: row["count"]
            for row in Organization.objects.values("status").annotate(count=Count("id"))
        }
        branch_statuses = {
            row["status"]: row["count"]
            for row in Branch.objects.values("status").annotate(count=Count("id"))
        }

        subscriptions = Subscription.objects.all()
        operational_subscriptions = subscriptions.exclude(status__in=("suspended", "cancelled"))
        active_subscriptions = operational_subscriptions.filter(
            start_date__lte=today, end_date__gte=today
        )
        contracts = {
            "total": subscriptions.count(),
            "active": active_subscriptions.count(),
            "pending": operational_subscriptions.filter(start_date__gt=today).count(),
            "expired": operational_subscriptions.filter(end_date__lt=today).count(),
            "suspended": subscriptions.filter(status="suspended").count(),
            "cancelled": subscriptions.filter(status="cancelled").count(),
            "expiring_soon": active_subscriptions.filter(end_date__lte=soon).count(),
            "organization": subscriptions.filter(customer_type="organization").count(),
            "personal": subscriptions.filter(customer_type="personal").count(),
            "active_devices": active_subscriptions.filter(
                subscription_devices__unassigned_at__isnull=True
            ).values("subscription_devices__device_id").distinct().count(),
        }

        try:
            traccar_items = traccar_devices()
            traccar = {
                "status": "connected",
                "registered": len(traccar_items),
                "online": sum(1 for item in traccar_items if item.get("status") == "online"),
                "offline": sum(1 for item in traccar_items if item.get("status") == "offline"),
                "unknown": sum(1 for item in traccar_items if item.get("status") not in {"online", "offline"}),
            }
        except TraccarAPIError:
            traccar = {
                "status": "unavailable", "registered": None,
                "online": None, "offline": None, "unknown": None,
            }
            logger.info("Traccar unavailable while building admin dashboard")

        users = User.objects.all()
        return Response({
            "generated_at": timezone.now(),
            "server": _server_stats(),
            "customers": {
                "organizations": Organization.objects.count(),
                "active_organizations": org_statuses.get("active", 0),
                "inactive_organizations": org_statuses.get("inactive", 0),
                "suspended_organizations": org_statuses.get("suspended", 0),
                "branches": Branch.objects.count(),
                "active_branches": branch_statuses.get("active", 0),
                "personal_customers": users.filter(account_type="personal", role="personal_user").count(),
                "active_personal_customers": users.filter(
                    account_type="personal", role="personal_user", is_active=True
                ).count(),
                "organization_users": users.filter(account_type="organization").count(),
                "active_users": users.filter(is_active=True).count(),
                "inactive_users": users.filter(is_active=False).count(),
                "new_customers_30d": Organization.objects.filter(
                    created_at__date__gte=today - timedelta(days=30)
                ).count() + users.filter(
                    account_type="personal", role="personal_user",
                    date_joined__date__gte=today - timedelta(days=30),
                ).count(),
            },
            "fleet": {
                "vehicles": Vehicle.objects.count(),
                "devices": Device.objects.count(),
                "devices_by_management_status": device_statuses,
                "warehouse": Device.objects.filter(management_status="warehouse").exclude(\n                    subscription_links__unassigned_at__isnull=True\n                ).count(),
                "installed": device_statuses.get("installed", 0) + device_statuses.get("active", 0),
                "faulty": device_statuses.get("faulty", 0),
                "lost": device_statuses.get("lost", 0),
                "stolen": device_statuses.get("stolen", 0),
                "disconnected_management": device_statuses.get("disconnected", 0),
                "with_vehicle": Device.objects.filter(vehicle__isnull=False).count(),
                "without_vehicle": Device.objects.filter(vehicle__isnull=True).count(),
            },
            "traccar": traccar,
            "contracts": contracts,
        })
