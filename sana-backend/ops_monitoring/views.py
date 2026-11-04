from __future__ import annotations

import json
import logging
import os
import queue
import shutil
import signal
import subprocess
import threading
from typing import Iterator

from django.http import StreamingHttpResponse, JsonResponse
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.exceptions import PermissionDenied

from accounts.permissions import IsSiteAdmin
from fleet.models import DeviceModel
from fleet.traccar_api import (
    TraccarAPIError,
    traccar_current_positions,
    traccar_devices,
)

logger = logging.getLogger(__name__)

# Legacy raw-capture helper still used by the separate port-diagnostics workflow.
CAPTURE_TEST_PORT = 1256

# Each fixed source has its own reader process. The browser receives all sources
# through one multiplexed SSE connection and filters them locally.
STREAM_COMMANDS = {
    "gps": [
        "journalctl", "--no-pager", "--follow", "--lines=50",
        "--unit=sana-gps.service", "--output=short-iso",
    ],
    "traccar": [
        "journalctl", "--no-pager", "--follow", "--lines=50",
        "--unit=traccar.service", "--output=short-iso",
    ],
    "backend": [
        "journalctl", "--no-pager", "--follow", "--lines=50",
        "--unit=sana-backend.service", "--output=short-iso",
    ],
    "postgres": [
        "journalctl", "--no-pager", "--follow", "--lines=50",
        "--unit=postgresql.service", "--output=short-iso",
    ],
    "system": [
        "journalctl", "--no-pager", "--follow", "--lines=50",
        "--priority=warning", "--output=short-iso",
    ],
}

LIVE_CAPTURE_HELPER = "/usr/local/sbin/sana-traccar-live-capture"


def _require_admin(request) -> None:
    if not request.user or not request.user.is_authenticated:
        raise PermissionDenied("احراز هویت لازم است.")
    if not getattr(request.user, "is_site_admin", False):
        raise PermissionDenied("این بخش فقط برای ادمین کل سایت مجاز است.")


def _event(line: str) -> str:
    return "data: " + json.dumps({"line": line.rstrip("\n")}, ensure_ascii=False) + "\n\n"


def _live_event(payload: dict) -> str:
    return "data: " + json.dumps(payload, ensure_ascii=False) + "\n\n"


def _validated_capture(port_value: str, protocol_value: str) -> tuple[int, str]:
    if not port_value.isdigit():
        raise ValueError("شماره پورت باید عددی باشد.")
    port = int(port_value)
    if not 1024 <= port <= 65535:
        raise ValueError("پورت باید بین 1024 و 65535 باشد.")
    protocol = protocol_value.strip().lower()
    if protocol not in {"tcp", "udp", "both"}:
        raise ValueError("پروتکل باید TCP، UDP یا هر دو باشد.")
    return port, protocol


class LiveLogStreamView(APIView):
    """One admin-only SSE connection multiplexing all live diagnostic sources."""

    permission_classes = [IsAuthenticated, IsSiteAdmin]

    def perform_content_negotiation(self, request, force=False):
        from rest_framework.renderers import JSONRenderer

        if "text/event-stream" in request.META.get("HTTP_ACCEPT", ""):
            return JSONRenderer(), "application/json"
        return super().perform_content_negotiation(request, force)

    def get(self, request):
        _require_admin(request)

        capture_port = request.query_params.get("capture_port", "").strip()
        capture_protocol = request.query_params.get("capture_protocol", "").strip()
        if bool(capture_port) != bool(capture_protocol):
            return JsonResponse(
                {"detail": "برای پایش شبکه، پورت و پروتکل هر دو لازم هستند."},
                status=400,
            )

        commands = dict(STREAM_COMMANDS)
        if capture_port:
            try:
                port, protocol = _validated_capture(capture_port, capture_protocol)
            except ValueError as exc:
                return JsonResponse({"detail": str(exc)}, status=400)
            commands["network"] = [
                "sudo", "-n", LIVE_CAPTURE_HELPER, str(port), protocol,
            ]

        def generate() -> Iterator[str]:
            events: queue.Queue = queue.Queue(maxsize=3000)
            stop_event = threading.Event()
            process_lock = threading.Lock()
            processes: list[subprocess.Popen] = []
            threads: list[threading.Thread] = []

            def publish(payload: dict) -> None:
                try:
                    events.put_nowait(payload)
                except queue.Full:
                    try:
                        events.get_nowait()
                    except queue.Empty:
                        pass
                    try:
                        events.put_nowait(payload)
                    except queue.Full:
                        pass

            def read_source(source: str, command: list[str]) -> None:
                process = None
                try:
                    executable = shutil.which(command[0])
                    if not executable:
                        publish({
                            "kind": "status", "source": source, "status": "error",
                            "message": f"ابزار {command[0]} روی سرور پیدا نشد.",
                        })
                        return

                    safe_command = [executable, *command[1:]]
                    process = subprocess.Popen(
                        safe_command,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        bufsize=1,
                        close_fds=True,
                        start_new_session=True,
                    )
                    with process_lock:
                        processes.append(process)
                    publish({"kind": "status", "source": source, "status": "live"})
                    assert process.stdout is not None
                    for line in process.stdout:
                        if stop_event.is_set():
                            break
                        publish({
                            "kind": "line",
                            "source": source,
                            "line": line.rstrip("\r\n"),
                        })
                    return_code = process.wait()
                    if not stop_event.is_set() and return_code:
                        publish({
                            "kind": "status", "source": source, "status": "error",
                            "message": f"فرایند منبع با کد {return_code} متوقف شد.",
                        })
                except (OSError, ValueError, subprocess.SubprocessError) as exc:
                    logger.warning("Could not start live log source %s: %s", source, exc)
                    publish({
                        "kind": "status", "source": source, "status": "error",
                        "message": "اجرای منبع لاگ ممکن نشد؛ مجوزها و نصب ابزار را بررسی کنید.",
                    })
                finally:
                    if process is not None and process.stdout is not None:
                        try:
                            process.stdout.close()
                        except OSError:
                            pass

            for source, command in commands.items():
                thread = threading.Thread(
                    target=read_source,
                    args=(source, command),
                    name=f"sana-live-log-{source}",
                    daemon=True,
                )
                threads.append(thread)
                thread.start()

            try:
                while not stop_event.is_set():
                    try:
                        payload = events.get(timeout=15)
                        yield _live_event(payload)
                    except queue.Empty:
                        yield ": keep-alive\n\n"
            finally:
                stop_event.set()
                with process_lock:
                    active_processes = list(processes)
                for process in active_processes:
                    if process.poll() is None:
                        try:
                            # Each reader owns a process group so sudo/tcpdump children
                            # are also stopped when the browser disconnects.
                            os.killpg(process.pid, signal.SIGTERM)
                        except ProcessLookupError:
                            pass
                        except OSError:
                            try:
                                process.terminate()
                            except OSError:
                                pass
                for process in active_processes:
                    try:
                        process.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        try:
                            os.killpg(process.pid, signal.SIGKILL)
                        except (ProcessLookupError, OSError):
                            try:
                                process.kill()
                            except OSError:
                                pass
                        try:
                            process.wait(timeout=2)
                        except (OSError, subprocess.SubprocessError):
                            pass
                for thread in threads:
                    thread.join(timeout=0.25)

        response = StreamingHttpResponse(generate(), content_type="text/event-stream")
        response["Cache-Control"] = "no-cache, no-transform"
        response["X-Accel-Buffering"] = "no"
        return response


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

        # API connectivity is independent of a listening-port selection. This is
        # read-only and deliberately does not invoke the privileged port helper.
        if action == "api-test":
            def generate_api_test():
                yield _event("شروع آزمون اتصال REST API ترکار…")
                try:
                    devices = traccar_devices()
                    positions = traccar_current_positions()
                    yield _event("اتصال API ترکار و احراز هویت موفق است.")
                    yield _event(f"دستگاه‌های ثبت‌شده در Traccar: {len(devices)}")
                    yield _event(f"موقعیت‌های فعلی برگشتی از API: {len(positions)}")
                    yield _event("آزمون API با موفقیت پایان یافت.")
                except TraccarAPIError as exc:
                    logger.info("Traccar API connectivity test failed: %s", exc)
                    yield _event(f"آزمون API ناموفق بود: {exc}")
                except Exception:
                    logger.exception("Unexpected error during Traccar API connectivity test")
                    yield _event("آزمون API به دلیل خطای داخلی بک‌اند متوقف شد؛ جزئیات در لاگ سرویس ثبت شده است.")

            response = StreamingHttpResponse(
                generate_api_test(), content_type="text/event-stream"
            )
            response["Cache-Control"] = "no-cache, no-transform"
            response["X-Accel-Buffering"] = "no"
            return response

        capture_actions = {"capture-toggle", "capture-start", "capture-stop", "capture-status"}
        if action in capture_actions:
            # Never trust the client-supplied port for raw capture.
            port = CAPTURE_TEST_PORT
        else:
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
        elif action in {"test", "status", "diagnostics", "restore", "repair-permissions", "capture-toggle", "capture-start", "capture-stop", "capture-status"}:
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
        if int(port) != CAPTURE_TEST_PORT:
            return JsonResponse({"detail": "شنود خام فقط روی پورت ثابت ۱۲۵۶ مجاز است."}, status=400)
        port = CAPTURE_TEST_PORT
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
                if process is not None and process.poll() is None:
                    try:
                        process.terminate()
                        process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=2)
                    except OSError:
                        logger.warning(
                            "Could not terminate capture-tail process for port %s",
                            port,
                        )
        response = StreamingHttpResponse(generate(), content_type="text/event-stream")
        response["Cache-Control"] = "no-cache, no-transform"
        response["X-Accel-Buffering"] = "no"
        response["Content-Disposition"] = f'inline; filename="sana-gps-capture-{port}.log"'
        return response
