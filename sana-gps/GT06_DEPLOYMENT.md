# SANA GPS multi-protocol ingestion

All TCP GPS devices connect to one shared listener. The listener identifies the protocol from the opening bytes of each connection and routes the stream to that protocol's handler. Teltonika and GT06-compatible devices therefore share the same internal TCP port without sharing their decoders.

## Port mapping

- Public TCP port: `19000` (existing ISP/router forwarding)
- Server TCP port: `9000` (shared Teltonika + GT06-compatible protocol dispatcher)
- Server UDP port: `9001` (existing Teltonika UDP listener)

Keep the current NAT rule **public TCP 19000 → server TCP 9000**. Do not point the NAT rule at server port 19000 and do not change the existing UDP mapping.

## Protocol detection and device registration

- Teltonika TCP identification begins with its two-byte length-prefixed IMEI handshake.
- GT06-family TCP frames begin with `7878` or `7979`.
- After detection, the matching handler checks the identifier against a device registered in SANA. Unknown identifiers are not authenticated.
- The device's protocol is detected and saved when its first valid login/identification is accepted, provided the protocol field was empty.
- Teltonika UDP on port `9001` continues through the existing Teltonika handler.

GT06-compatible packets are captured at `/var/tmp/sana-gps-gt06-capture.log` by default and decoded position reports are saved in `fleet_gt06position`.

## Deploy

Run from the repository root after pulling the changes:

```bash
git pull --ff-only
source sana-backend/venv/bin/activate
cd sana-backend
python manage.py migrate
cd ..
sana-backend/venv/bin/python -m pytest -q sana-gps/tests
sudo systemctl restart sana-gps
sudo systemctl status sana-gps --no-pager
sudo ss -lntup | grep -E ':(8000|9000|9001)\b'
```

Expected listeners are TCP `9000` and UDP `9001`; there is intentionally no separate internal TCP listener on `19000`.

## Verify incoming data

```bash
sudo journalctl -u sana-gps -f
```

In another terminal:

```bash
sudo tail -f /var/tmp/sana-gps-gt06-capture.log
```

To inspect saved GT06-compatible positions in PostgreSQL:

```sql
SELECT d.imei, p.gps_time, p.latitude, p.longitude,
       p.speed_kmh, p.course, p.satellites, p.received_at
FROM fleet_gt06position p
JOIN fleet_device d ON d.id = p.device_id
ORDER BY p.id DESC
LIMIT 20;
```

## Adding a future protocol (for example, a Concox model)

The shared port and dispatcher are designed so a new protocol can be added as a separate detector/handler without changing the Teltonika handler, port mapping, or data path for existing devices. Registering an identifier alone cannot decode an entirely new wire protocol: the specific model's protocol must first be identified and implemented, with framing, authentication/identifier extraction, acknowledgements, decoder, persistence mapping, and tests. Many trackers share GT06-compatible framing, but Concox compatibility must be verified for the exact model. Unknown protocols must not be guessed or fed to an unrelated decoder.
