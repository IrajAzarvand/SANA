from __future__ import annotations

from html.parser import HTMLParser
from urllib.request import Request, urlopen
import re

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from fleet.models import DeviceModel


SOURCE_URL = "https://www.traccar.org/devices/"
CATALOG_VERSION = "official-current"

# Known multi-word manufacturer names are matched longest-first. For entries
# without a recognizable manufacturer prefix, the full official device label
# is retained under "Other / generic" so no listed entry is silently dropped.
KNOWN_MANUFACTURERS = [
    "Atlanta Systems", "Jagco Technology", "ZY International",
    "Four-Faith", "Multi-Tech", "HuaSheng", "Jimi IoT", "TopFlyTech",
    "SinoTrack", "AnioSmart", "ExtremTrac", "Freematics", "ZGPAX",
    "T-WIN", "i-Startek", "iStartek", "i-Trac", "TrackPro",
    "Rayoid", "Seeworld", "WanWay", "Suntech", "Queclink",
    "Concox", "Ruptela", "Meitrack", "Teltonika", "Topten",
    "Coban", "Xexun", "Kingneed", "Artway Technology", "Moralwinhk",
    "Signal", "Navis", "Start", "Jointech", "Carscop", "Huabao",
    "Gosafe", "SinoTrack", "TopFlyTech", "Bofan", "Cantrack",
    "Oner", "T-Zone", "Pengsent", "Benway", "WeTrack",
    "Topin", "Fox", "Arknav", "Supermate", "Appello",
    "HuaSheng", "Granit", "Carcell", "HunterPro", "Raveon",
    "CradlePoint", "AutoGrade", "Oigo", "Dingtek", "Portman",
    "ExtremTrac", "Piccolo", "Icomera", "VNET", "PST",
    "Gelix", "GoPass", "Maxon", "Totem", "Keson", "ZGPAX",
    "Gotop", "Heacent", "Starsnav", "i-Trac", "TrackPro",
    "Rayoid", "VNET", "NIOT", "IDPL", "GPS103",
]
KNOWN_MANUFACTURERS = sorted(set(KNOWN_MANUFACTURERS), key=len, reverse=True)


class DeviceTableParser(HTMLParser):
    """Read the public Traccar devices table without third-party dependencies."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.in_row = False
        self.in_cell = False
        self.cell_parts = []
        self.row = []
        self.rows = []

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.in_row = True
            self.row = []
        elif self.in_row and tag in ("td", "th"):
            self.in_cell = True
            self.cell_parts = []

    def handle_data(self, data):
        if self.in_row and self.in_cell:
            self.cell_parts.append(data)

    def handle_endtag(self, tag):
        if self.in_row and self.in_cell and tag in ("td", "th"):
            value = " ".join("".join(self.cell_parts).split())
            value = value.replace("\u200b", "").replace("\ufeff", "")
            value = re.sub(r"\s+RECOMMENDED\s*$", "", value, flags=re.I).strip()
            self.row.append(value)
            self.in_cell = False
        elif tag == "tr" and self.in_row:
            if len(self.row) >= 3 and self.row[0].lower() != "device":
                self.rows.append(self.row[:3])
            self.in_row = False
            self.in_cell = False


def split_manufacturer(device_label: str) -> tuple[str, str]:
    label = " ".join(device_label.split()).strip()
    for manufacturer in KNOWN_MANUFACTURERS:
        if label.casefold() == manufacturer.casefold():
            return manufacturer, label
        prefix = manufacturer + " "
        if label.casefold().startswith(prefix.casefold()):
            model = label[len(prefix):].strip()
            if model:
                return manufacturer, model
    # Most labels use "Manufacturer Model". Preserve single-token/unknown
    # labels intact instead of inventing a model name.
    parts = label.split(maxsplit=1)
    if len(parts) == 2:
        return parts[0], parts[1]
    return "Other / generic", label


def fetch_catalog():
    request = Request(
        SOURCE_URL,
        headers={"User-Agent": "SANA-Traccar-Catalog-Sync/1.0"},
    )
    try:
        with urlopen(request, timeout=30) as response:
            html = response.read().decode("utf-8", errors="replace")
    except Exception as exc:
        raise CommandError(
            f"Could not download the official Traccar device list from {SOURCE_URL}: {exc}"
        ) from exc

    parser = DeviceTableParser()
    parser.feed(html)
    catalog = {}
    for device_label, protocol_label, port_label in parser.rows:
        device_label = " ".join(device_label.split())
        if not device_label:
            continue
        manufacturer, model_name = split_manufacturer(device_label)
        if not model_name:
            continue

        protocol = protocol_label.strip().lower()
        if protocol in ("", "-"):
            protocol = "clones" if "clone" in port_label.lower() else "unknown"

        match = re.search(r"\b(\d{2,5})\b", port_label)
        port = int(match.group(1)) if match else None
        key = (manufacturer.casefold(), model_name.casefold())
        entry = {
            "manufacturer": manufacturer[:100],
            "name": model_name[:100],
            "protocol": protocol[:50],
            "port": port,
            "code": re.sub(
                r"[^a-z0-9]+", "-",
                f"{manufacturer}-{model_name}".lower()
            ).strip("-")[:50] or "traccar-device",
            "source_url": SOURCE_URL,
            "traccar_version": CATALOG_VERSION,
            "is_verified": True,
        }
        existing = catalog.get(key)
        # If the same label appears as a generic clone and with a concrete
        # protocol elsewhere in the official table, keep the concrete entry.
        if existing is None or (
            existing["protocol"] in {"clones", "unknown"}
            and protocol not in {"clones", "unknown"}
        ):
            catalog[key] = entry

    if len(catalog) < 500:
        raise CommandError(
            f"Only {len(catalog)} unique device entries were parsed; refusing to change the database."
        )
    return list(catalog.values())


class Command(BaseCommand):
    help = (
        "Replace the selectable SANA device-model catalog with the full device "
        "table published on the official Traccar website."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Download and parse the catalog without changing the database.",
        )

    def handle(self, *args, **options):
        catalog = fetch_catalog()
        manufacturers = {item["manufacturer"] for item in catalog}
        self.stdout.write(
            f"Parsed {len(catalog)} unique device entries from {SOURCE_URL}"
        )
        self.stdout.write(f"Manufacturers after name parsing: {len(manufacturers)}")

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("Dry run: database was not changed."))
            return

        created = 0
        updated = 0
        with transaction.atomic():
            # Hide the old curated list from the picker first. Keep its rows in
            # place so existing Device foreign keys and historical data survive.
            DeviceModel.objects.update(is_verified=False)

            for item in catalog:
                _, was_created = DeviceModel.objects.update_or_create(
                    manufacturer=item["manufacturer"],
                    name=item["name"],
                    traccar_version=CATALOG_VERSION,
                    defaults={
                        "code": item["code"],
                        "protocol": item["protocol"],
                        "port": item["port"],
                        "source_url": item["source_url"],
                        "is_verified": True,
                    },
                )
                if was_created:
                    created += 1
                else:
                    updated += 1

        self.stdout.write(self.style.SUCCESS(
            f"Catalog sync complete: {len(catalog)} entries, "
            f"{len(manufacturers)} parsed manufacturers, "
            f"{created} created, {updated} updated."
        ))
        self.stdout.write(
            "Note: this is the current public website list, not a version-pinned "
            "guarantee that every entry is supported by the installed Traccar 6.16.0."
        )
