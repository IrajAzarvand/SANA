const activeAnimations = new WeakMap();

/**
 * Animate a Leaflet marker between GPS positions without changing the stored
 * coordinates. A newer target cancels the previous animation at its current
 * interpolated position, preventing visible jumps when updates arrive early.
 */
export function animateLeafletMarker(marker, target, duration = 10000) {
  if (!marker || !Array.isArray(target)) return;
  const to = { lat: Number(target[0]), lng: Number(target[1]) };
  if (!Number.isFinite(to.lat) || !Number.isFinite(to.lng)) return;

  const previousFrame = activeAnimations.get(marker);
  if (previousFrame) cancelAnimationFrame(previousFrame);

  const fromLatLng = marker.getLatLng();
  const from = { lat: fromLatLng.lat, lng: fromLatLng.lng };
  const total = Math.max(0, Number(duration) || 0);
  if (total <= 0 || (from.lat === to.lat && from.lng === to.lng)) {
    marker.setLatLng([to.lat, to.lng]);
    activeAnimations.delete(marker);
    return;
  }

  let frameId = null;
  const startedAt = performance.now();
  const tick = (now) => {
    const progress = Math.min(1, (now - startedAt) / total);
    // Smooth ease-in/ease-out; interpolation is visual only, never persisted.
    const eased = progress * progress * (3 - 2 * progress);
    marker.setLatLng([
      from.lat + (to.lat - from.lat) * eased,
      from.lng + (to.lng - from.lng) * eased,
    ]);
    if (progress < 1) {
      frameId = requestAnimationFrame(tick);
      activeAnimations.set(marker, frameId);
    } else {
      activeAnimations.delete(marker);
    }
  };

  frameId = requestAnimationFrame(tick);
  activeAnimations.set(marker, frameId);
}
