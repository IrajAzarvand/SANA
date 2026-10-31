# GPS data ownership: Traccar is authoritative

## Runtime flow

1. GPS devices send their supported protocol directly to Traccar.
2. SANA registers/authorizes devices in its own fleet domain and periodically reconciles registered IMEIs with Traccar devices.
3. SANA's live-map and history APIs read positions from Traccar REST API and apply SANA's own authorization rules.
4. When an authenticated map session has a valid heartbeat in `gps.map_matching_watchers`, the GPS worker polls recent Traccar positions and requests road matching from Neshan.
5. SANA stores only Neshan's snapped coordinates and the identifiers needed to associate a match with a Traccar position in `gps.map_matched_position`; it does not copy raw coordinates, speed, payloads, or raw position history.
6. Watcher rows expire after missed heartbeats; without an active watcher, the worker skips Traccar polling and Neshan requests.
7. Traccar position Webhook delivery to SANA is not part of the active architecture; no SANA position-webhook receiver is deployed in the current code.

## Deliberately removed from the fresh SANA schema

- `gps.raw_packet`
- `gps.location_history`
- `gps.current_state`
- `gps.traccar_unknown_device`
- `public.fleet_gpstelemetry`
- `public.fleet_unknowngpsdata`
- Legacy event/trip/geofence GPS tables that depended on duplicate telemetry

The legacy SQL files remain in the repository for historical context, but `scripts/reset_sana_db.sh` applies only the current watcher and Traccar-authoritative schema SQL. The Django migration removes the two old public telemetry models.

## Backend environment

The Django backend needs read-only Traccar API credentials for live-map and report-history requests. Configure these in the environment file used by the `sana-backend` systemd service:

- `TRACCAR_API_URL=http://127.0.0.1:8082/api`
- `TRACCAR_API_USERNAME=...`
- `TRACCAR_API_PASSWORD=...`

The GPS worker uses `SANA_GPS_TRACCAR_API_URL`, `SANA_GPS_TRACCAR_API_USERNAME`, and `SANA_GPS_TRACCAR_API_PASSWORD` from its own service environment. Do not commit credentials.

## Operational note

Legacy protocol handlers remain only as decoder/test code; the production GPS runtime does not instantiate them, and the former telemetry repository now refuses raw writes. The unknown-device queue likewise refuses to store payloads. The SANA GPS service no longer binds the legacy SANA TCP/UDP ports and no longer accepts position webhooks. Remove any Traccar-side webhook/forwarder that POSTs positions to SANA, otherwise it will send requests to a retired endpoint. Device protocol ports and forwarding must point to Traccar. Do not remove or change Traccar's listener configuration as part of a SANA database reset.
