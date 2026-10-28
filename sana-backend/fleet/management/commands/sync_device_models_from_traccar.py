from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from fleet.device_model_sync import sync_device_models_from_traccar
from fleet.traccar_api import TraccarAPIError


class Command(BaseCommand):
    help = (
        "Fill or correct device brand/model from the protocol Traccar receives. "
        "Values are written only when exactly one verified catalog model matches."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report planned changes without writing to the database.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        try:
            result = sync_device_models_from_traccar(dry_run=dry_run)
        except TraccarAPIError as exc:
            raise CommandError(f"Traccar API is unavailable: {exc}") from exc

        prefix = "[dry-run] " if dry_run else ""
        for change in result["changes"]:
            previous = change["previous"] or "no brand/model"
            self.stdout.write(
                f"{prefix}{change['imei']} ({change['protocol']}): {previous} -> {change['model']}"
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"{prefix}Device model sync complete: "
                f"scanned={result['scanned']}, assigned={result['assigned']}, "
                f"corrected={result['corrected']}, unchanged={result['unchanged']}, "
                f"unresolved={result['unresolved']}"
            )
        )
