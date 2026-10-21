# GPS data ownership: Traccar is authoritative

## Runtime flow

1. GPS devices send their supported protocol directly to Traccar.
2. SANA registers/authorizes devices in its own fleet domain and periodically ensures each SANA-registered IMEI exists in Traccar.
3. The SANA live-map API reads the latest positions from Traccar and filters them to devices the authenticated user is allowed to see.
4. When at least one authenticated map session has a valid heartbeat in `gps.map_matching_watchers`, the GPS worker fetches recent Traccar positions and requests road matching from Neshan.
5. SANA stores only the snapped coordinates and the identifiers required to associate a match with its Traccar position: `gps.map_matched_position`. It does not copy raw coordinates, speed, payloads, or position history into SANA.
6. Watcher rows expire after missed heartbeats; when no unexpired watcher remains, the worker skips Traccar history polling and Neshan requests.

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

The SANA GPS service no longer binds the legacy SANA TCP/UDP ports and no longer accepts position webhooks. Remove any Traccar-side webhook/forwarder that POSTs positions to SANA, otherwise it will send requests to a retired endpoint. Device protocol ports and forwarding must point to Traccar. Do not remove or change Traccar's listener configuration as part of a SANA database reset.
