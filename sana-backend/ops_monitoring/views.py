from __future__ import annotations

import json
import logging
import shutil
import subprocess
from typing import Iterator

from django.http import StreamingHttpResponse, JsonResponse
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.exceptions import PermissionDenied

from accounts.permissions import IsSiteAdmin
from fleet.models import DeviceModel
from fleet.traccar_api import TraccarAPIError, traccar_current_positions

logger = logging.getLogger(__name__)

# Commands and filters are deliberately fixed: request data is never passed to a shell.
# Network capture runs through a root-owned, argument-free wrapper with a narrowly
# scoped sudoers rule; the Django service itself must never run as root.
STREAM_COMMANDS = {
    "service": [
        "journalctl", "--no-pager", "--follow", "--lines=50",
        "--unit=sana-gps.service", "--output=short-iso",
    ],
    "network": [
        "sudo", "-n", "/usr/local/sbin/sana-gps-network-capture",
    ],
}


def _require_admin(request) -> None:
    if not request.user or not request.user.is_authenticated:
        raise PermissionDenied("احراز هویت لازم است.")
    if not getattr(request.user, "is_site_admin", False):
        raise PermissionDenied("این بخش فقط برای ادمین کل سایت مجاز است.")


def _event(line: str) -> str:
    return "data: " + json.dumps({"line": line.rstrip("\n")}, ensure_ascii=False) + "\n\n"


class LiveLogStreamView(APIView):
    """Admin-only server-sent log stream for fixed, read-only diagnostic commands."""

    permission_classes = [IsAuthenticated, IsSiteAdmin]

    def perform_content_negotiation(self, request, force=False):
        # The stream response is a Django StreamingHttpResponse, not a DRF Response.
        # Negotiate JSON for DRF-generated auth/error responses while allowing browsers
        # to request text/event-stream without DRF rejecting the request with HTTP 406.
        from rest_framework.renderers import JSONRenderer

        if "text/event-stream" in request.META.get("HTTP_ACCEPT", ""):
            return JSONRenderer(), "application/json"
        return super().perform_content_negotiation(request, force)

    def get(self, request, stream_name: str):
        _require_admin(request)
        command = STREAM_COMMANDS.get(stream_name)
        if command is None:
            return JsonResponse({"detail": "منبع لاگ نامعتبر است."}, status=404)

        executable = shutil.which(command[0])
        if not executable:
            message = (
                "برای ضبط ترافیک شبکه، sudo روی سرور لازم است."
                if stream_name == "network" and command[0] == "sudo"
                else f"ابزار {command[0]} روی سرور نصب نیست."
            )
            return StreamingHttpResponse(
                iter([_event(message)]),
                content_type="text/event-stream",
                status=200,
            )
        command = [executable, *command[1:]]

        def generate() -> Iterator[str]:
            process = None
            try:
                process = subprocess.Popen(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    close_fds=True,
                )
                assert process.stdout is not None
                for line in process.stdout:
                    yield _event(line)
            except (OSError, ValueError) as exc:
                logger.warning("Could not start GPS diagnostic stream %s: %s", stream_name, exc)
                yield _event(
                    "اجرای دستور ممکن نشد؛ مجوز سرویس یا نصب ابزار را بررسی کنید. "
                    "(جزئیات فنی در لاگ بک‌اند ثبت شده است.)"
                )
            finally:
                if process is not None:
                    try:
                        process.terminate()
                        process.wait(timeout=2)
                    except Exception:
                        try:
                            process.kill()
                        except Exception:
                            pass

        response = StreamingHttpResponse(generate(), content_type="text/event-stream")
        response["Cache-Control"] = "no-cache, no-transform"
        response["X-Accel-Buffering"] = "no"
        response["Content-Disposition"] = 'inline; filename="sana-gps-live.log"'
        return response


class GPSQueueView(APIView):
    """Compatibility endpoint for a retired queue of unknown-device raw packets."""

    permission_classes = [IsAuthenticated, IsSiteAdmin]

    def get(self, request):
        _require_admin(request)
        # Unknown Traccar-only devices are intentionally not staged or retained by SANA.
        return JsonResponse({
            "results": [],
            "count": 0,
            "detail": "صف داده خام دستگاه‌های ناشناس حذف شده است؛ Traccar مرجع داده خام GPS است.",
        })


class TraccarPortOperationView(APIView):
    """Admin-only streamed operations for a validated Traccar listening port."""

    permission_classes = [IsAuthenticated, IsSiteAdmin]
    helper = "/usr/local/sbin/sana-traccar-port-manager"

    def perform_content_negotiation(self, request, force=False):
        from rest_framework.renderers import JSONRenderer
        if "text/event-stream" in request.META.get("HTTP_ACCEPT", ""):
            return JSONRenderer(), "application/json"
        return super().perform_content_negotiation(request, force)

    def post(self, request):
        _require_admin(request)
        action = str(request.data.get("action", "")).strip().lower()
        raw_port = str(request.data.get("port", "")).strip()
        if not raw_port.isdigit():
            return JsonResponse({"detail": "شماره پورت باید عددی باشد."}, status=400)
        port = int(raw_port)
        if not 1024 <= port <= 65535:
            return JsonResponse({"detail": "پورت باید بین 1024 و 65535 باشد."}, status=400)

        command = ["sudo", "-n", self.helper]
        if action == "apply":
            raw_model_id = str(request.data.get("device_model_id", "")).strip()
            if not raw_model_id.isdigit():
                return JsonResponse({"detail": "برای تعیین خودکار تنظیم Traccar، مدل دستگاه را انتخاب کنید."}, status=400)
            model = DeviceModel.objects.filter(pk=int(raw_model_id), is_verified=True).first()
            if model is None:
                return JsonResponse({"detail": "مدل دستگاه معتبر و تأییدشده پیدا نشد."}, status=400)
            protocol = str(model.protocol or "").strip()
            if not protocol or not protocol.replace("_", "").replace("-", "").isalnum() or not protocol[0].isalpha():
                return JsonResponse({"detail": "مدل انتخاب‌شده نگاشت داخلی معتبر برای Traccar ندارد."}, status=400)
            command += ["apply", str(port), protocol]
        elif action in {"test", "status", "capture-toggle", "capture-start", "capture-stop", "capture-status"}:
            command += [action, str(port)]
        else:
            return JsonResponse({"detail": "عملیات نامعتبر است."}, status=400)

        def generate():
            process = None
            positions_before = None
            try:
                if action == "test":
                    try:
                        positions_before = traccar_current_positions()
                        yield _event(f"پیش از آزمون، {len(positions_before)} موقعیت فعلی از API ترکر خوانده شد.")
                    except TraccarAPIError:
                        yield _event("هشدار: اتصال API ترکر برای مقایسه موقعیت قبل/بعد در دسترس نیست؛ آزمون بسته شبکه همچنان اجرا می‌شود.")
                executable = shutil.which(command[0])
                if not executable:
                    yield _event("خطا: sudo روی سرور نصب یا در PATH سرویس در دسترس نیست.")
                    return
                safe_command = [executable, *command[1:]]
                yield _event(f"شروع عملیات «{action}» برای پورت {port}")
                process = subprocess.Popen(
                    safe_command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, bufsize=1, close_fds=True,
                )
                assert process.stdout is not None
                for line in process.stdout:
                    yield _event(line)
                return_code = process.wait()
                yield _event("عملیات با موفقیت پایان یافت." if return_code == 0 else f"عملیات ناموفق بود (کد {return_code}).")
                if action == "test" and positions_before is not None:
                    try:
                        positions_after = traccar_current_positions()
                        before_by_device = {
                            str(item.get("deviceId")): (
                                item.get("id"), item.get("serverTime"), item.get("fixTime"),
                                item.get("latitude"), item.get("longitude")
                            )
                            for item in positions_before
                        }
                        changed = [
                            item for item in positions_after
                            if before_by_device.get(str(item.get("deviceId"))) != (
                                item.get("id"), item.get("serverTime"), item.get("fixTime"),
                                item.get("latitude"), item.get("longitude")
                            )
                        ]
                        if changed:
                            yield _event(f"تأیید API ترکر: در بازه آزمون، {len(changed)} موقعیت فعلی تغییر کرده/ثبت شده است.")
                        else:
                            yield _event("تأیید ثبت جدید از API ترکر ممکن نشد: موقعیت فعلی دستگاه‌ها در بازه آزمون تغییر نکرد. اگر بسته شبکه دیده شد، بررسی لاگ Traccar و IMEI لازم است.")
                    except TraccarAPIError:
                        yield _event("ترافیک شبکه آزمون شد، اما بررسی ثبت موقعیت از API ترکر به دلیل خطای اتصال ممکن نشد.")
            except (OSError, ValueError, subprocess.SubprocessError) as exc:
                logger.warning("Traccar port operation failed: %s", exc)
                yield _event("اجرای عملیات ممکن نشد؛ نصب واسط مدیریتی و مجوز sudo را بررسی کنید.")
            finally:
                if process is not None and process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=2)
                    except Exception:
                        process.kill()

        response = StreamingHttpResponse(generate(), content_type="text/event-stream")
        response["Cache-Control"] = "no-cache, no-transform"
        response["X-Accel-Buffering"] = "no"
        return response

class TraccarCaptureLogView(APIView):
    """Admin-only live tail of the bounded raw-packet capture log."""

    permission_classes = [IsAuthenticated, IsSiteAdmin]
    helper = "/usr/local/sbin/sana-traccar-port-manager"

    def perform_content_negotiation(self, request, force=False):
        from rest_framework.renderers import JSONRenderer
        if "text/event-stream" in request.META.get("HTTP_ACCEPT", ""):
            return JSONRenderer(), "application/json"
        return super().perform_content_negotiation(request, force)

    def get(self, request, port: int):
        _require_admin(request)
        if not 1024 <= int(port) <= 65535:
            return JsonResponse({"detail": "پورت باید بین 1024 و 65535 باشد."}, status=400)
        sudo = shutil.which("sudo")
        if not sudo:
            return StreamingHttpResponse(
                iter([_event("خطا: sudo روی سرور در دسترس نیست.")]),
                content_type="text/event-stream",
            )

        def generate():
            process = None
            try:
                process = subprocess.Popen(
                    [sudo, "-n", self.helper, "capture-tail", str(port)],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, bufsize=1, close_fds=True,
                )
                assert process.stdout is not None
                for line in process.stdout:
                    yield _event(line)
            except (OSError, ValueError) as exc:
                logger.warning("Could not stream raw GPS capture for port %s: %s", port, exc)
                yield _event("خواندن لاگ زنده ممکن نشد؛ نصب helper و مجوز sudo را بررسی کنید.")
            finally:
                if process is not None:
                    try:
                        process.terminate()
                        process.wait(timeout=2)
                    except Exception:
                        try:
                            process.kill()
                        except Exception:
                            pass

        response = StreamingHttpResponse(generate(), content_type="text/event-stream")
        response["Cache-Control"] = "no-cache, no-transform"
        response["X-Accel-Buffering"] = "no"
        response["Content-Disposition"] = f'inline; filename="sana-gps-capture-{port}.log"'
        return response
