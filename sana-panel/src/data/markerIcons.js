// نگاشت وضعیت به آیکون PNG
// فایل‌ها توی public/markers/ هستن

export const markerIcons = {
  moving:   '/markers/arrow.png',
  stopped:  '/markers/park.png',
  offline:  '/markers/offline.png',
  alert:    '/markers/alarm-sos.png',
  sos:      '/markers/alarm-sos.png',
  fault:    '/markers/battery-fault.png',
  geofence: '/markers/geofence-in-out.png',
  towing:   '/markers/towing.png',
  stop:     '/markers/stop.png',
};

export function getMarkerIcon(status) {
  return markerIcons[status] || markerIcons.offline;
}