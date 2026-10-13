-- Run as the PostgreSQL table owner (normally postgres) after deploying
-- the protocol auto-detection change.
--
-- The GPS runtime must not receive broad UPDATE access to fleet_device.
-- This grants it permission to update only the protocol column; the runtime's
-- SQL further limits writes to blank values and compatible model protocols.
GRANT UPDATE (protocol) ON TABLE public.fleet_device TO sana_gps;
