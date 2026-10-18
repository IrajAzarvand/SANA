const activeAnimations = new WeakMap();

export function getFollowedPosition(positions, followPosition) {
  if (!followPosition || !Array.isArray(positions) || !positions.length) return null;
  if (followPosition === true) {
    return positions.length === 1 ? positions[0] : null;
  }
  return positions.find((item) => String(item.device_id) === String(followPosition)) || null;
}

function centerMapOn(map, lat, lng, zoom) {
  if (!map) return;
  if (Number.isFinite(zoom) && zoom !== map.getZoom()) {
    map.setView([lat, lng], zoom, { animate: false });
    return;
  }
  map.panTo([lat, lng], { animate: false, noMoveStart: true });
}

/**
 * Animate a Leaflet marker between GPS positions without changing the stored
 * coordinates. A newer target cancels the previous animation at its current
 * interpolated position, preventing visible jumps when updates arrive early.
 *
 * When keepCentered is set, the map pans with the marker so the icon stays in
 * the middle of the viewport and only heading/icon changes are visible.
 */
export function animateLeafletMarker(marker, target, duration = 10000, options = {}) {
  if (!marker || !Array.isArray(target)) return;
  const to = { lat: Number(target[0]), lng: Number(target[1]) };
  if (!Number.isFinite(to.lat) || !Number.isFinite(to.lng)) return;

  const map = options.map;
  const keepCentered = Boolean(options.keepCentered && map);

  const previousFrame = activeAnimations.get(marker);
  if (previousFrame) cancelAnimationFrame(previousFrame);

  const fromLatLng = marker.getLatLng();
  const from = { lat: fromLatLng.lat, lng: fromLatLng.lng };
  const apply = (lat, lng) => {
    marker.setLatLng([lat, lng]);
    if (keepCentered) centerMapOn(map, lat, lng);
  };

  const total = Math.max(0, Number(duration) || 0);
  if (total <= 0 || (from.lat === to.lat && from.lng === to.lng)) {
    apply(to.lat, to.lng);
    activeAnimations.delete(marker);
    return;
  }

  let frameId = null;
  const startedAt = performance.now();
  const tick = (now) => {
    const progress = Math.min(1, (now - startedAt) / total);
    // Linear interpolation avoids the repeated slow-down/speed-up feeling
    // when the next GPS point arrives and the animation is retargeted.
    const eased = progress;
    apply(
      from.lat + (to.lat - from.lat) * eased,
      from.lng + (to.lng - from.lng) * eased,
    );
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
