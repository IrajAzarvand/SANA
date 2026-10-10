# GT06 GPS ingestion

The GPS runtime has a dedicated GT06 TCP listener. It does not share the Teltonika handler.

## Defaults

- Teltonika TCP: `9000`
- Teltonika UDP: `9001`
- GT06 TCP: `19000`
- GT06 raw packet capture: `/var/tmp/sana-gps-gt06-capture.log`

Override the GT06 values in the systemd environment file with:

```ini
SANA_GPS_GT06_TCP_PORT=19000
SANA_GPS_GT06_CAPTURE_FILE=/var/tmp/sana-gps-gt06-capture.log
```

The GT06 handler supports the common short-frame `7878` format, login packets (`0x01`), GPS packets (`0x12`), heartbeat packets (`0x13`), and alarm packets (`0x16`). Login identifiers are checked against registered device IMEIs; an empty protocol value is set to `gt06` after successful registration lookup. Decoded classic GPS reports are stored in `fleet_gt06position`, with the raw packet retained for diagnostics.

## Deploy on the server

Run from the repository root after the change is available on `main`:

```bash
git pull
source sana-backend/venv/bin/activate
cd sana-backend
python manage.py migrate
cd ..
sudo systemctl restart sana-gps
sudo systemctl status sana-gps --no-pager
sudo ss -lntup | grep -E ':(8000|9000|9001|19000)\\b'
```

The router/NAT and any host firewall must allow **TCP** port `19000` to reach this server. Do not change the existing Teltonika port mappings.

## Verify incoming data

```bash
sudo journalctl -u sana-gps -f
```

In another terminal:

```bash
sudo tail -f /var/tmp/sana-gps-gt06-capture.log
```

After the tracker connects, verify persisted positions in PostgreSQL:

```sql
SELECT d.imei, p.gps_time, p.latitude, p.longitude,
       p.speed_kmh, p.course, p.satellites, p.received_at
FROM fleet_gt06position p
JOIN fleet_device d ON d.id = p.device_id
ORDER BY p.id DESC
LIMIT 20;
```

The exact device identifier representation varies across GT06-family firmware. If the login packet does not match a registered IMEI, the raw capture is the source of truth for adjusting identifier decoding. Likewise, GPS decoding currently targets the common classic `0x12` information layout; use the captured frames to confirm the particular firmware's variant.
