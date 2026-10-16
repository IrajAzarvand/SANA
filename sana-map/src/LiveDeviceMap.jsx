import NeshanLeafletMap from './providers/NeshanLeafletMap';

const providers = {
  'neshan-leaflet': NeshanLeafletMap,
};

/**
 * Provider-independent map entry point.
 * The live-position API contract does not depend on the map vendor.
 */
export default function LiveDeviceMap({ positions = [], onSelectDevice }) {
  const Provider = providers[import.meta.env.VITE_MAP_PROVIDER || 'neshan-leaflet'];

  if (!Provider) {
    return (
      <div className="flex h-full min-h-80 items-center justify-center p-6 text-center text-sm text-text-muted">
        ارائه‌دهنده نقشه تنظیم‌شده پشتیبانی نمی‌شود.
      </div>
    );
  }

  return <Provider positions={positions} onSelectDevice={onSelectDevice} />;
}
