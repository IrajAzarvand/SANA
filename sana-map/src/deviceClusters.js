const CLUSTER_ZOOM_LIMIT = 11;
const CLUSTER_RADIUS = 60;

export function getDeviceStatusCounts(positions = []) {
  return positions.reduce((counts, position) => {
    if (position.status === 'moving') counts.moving += 1;
    else if (position.status === 'offline') counts.offline += 1;
    else counts.stopped += 1;
    return counts;
  }, { moving: 0, stopped: 0, offline: 0 });
}

export function getDeviceClusters(map, positions = [], followPosition = false) {
  if (!map || !Array.isArray(positions)) return [];

  const zoom = map.getZoom();

  const validPositions = positions.filter((position) => (
    Number.isFinite(Number(position.latitude))
    && Number.isFinite(Number(position.longitude))
  ));

  if (zoom >= CLUSTER_ZOOM_LIMIT || validPositions.length < 2) {
    return validPositions.map((position) => ({
      type: 'device',
      id: String(position.device_id),
      position,
      positions: [position],
    }));
  }

  const followedId = followPosition && followPosition !== true
    ? String(followPosition)
    : null;

  const projected = validPositions.map((position) => {
    const point = map.project(
      [Number(position.latitude), Number(position.longitude)],
      zoom,
    );

    return {
      position,
      id: String(position.device_id),
      x: point.x,
      y: point.y,
    };
  });

  const parent = projected.map((_, index) => index);

  const find = (index) => {
    if (parent[index] !== index) {
      parent[index] = find(parent[index]);
    }
    return parent[index];
  };

  const union = (a, b) => {
    const rootA = find(a);
    const rootB = find(b);

    if (rootA !== rootB) parent[rootB] = rootA;
  };

  for (let i = 0; i < projected.length; i += 1) {
    for (let j = i + 1; j < projected.length; j += 1) {
      const a = projected[i];
      const b = projected[j];

      if (a.id === followedId || b.id === followedId) continue;

      if (Math.hypot(a.x - b.x, a.y - b.y) <= CLUSTER_RADIUS) {
        union(i, j);
      }
    }
  }

  const groups = new Map();

  projected.forEach((item, index) => {
    const root = find(index);
    if (!groups.has(root)) groups.set(root, []);
    groups.get(root).push(item);
  });

  const result = [];

  groups.forEach((members) => {
    const clusterPositions = members.map((member) => member.position);

    if (members.length === 1) {
      result.push({
        type: 'device',
        id: members[0].id,
        position: members[0].position,
        positions: clusterPositions,
      });
      return;
    }

    const center = members.reduce(
      (sum, member) => ({
        x: sum.x + member.x,
        y: sum.y + member.y,
      }),
      { x: 0, y: 0 },
    );

    const point = map.unproject([
      center.x / members.length,
      center.y / members.length,
    ], zoom);

    result.push({
      type: 'cluster',
      id: `cluster-${members.map((member) => member.id).sort().join('-')}`,
      latitude: point.lat,
      longitude: point.lng,
      positions: clusterPositions,
      counts: getDeviceStatusCounts(clusterPositions),
      total: clusterPositions.length,
    });
  });

  return result;
}
export function createClusterIcon(L, cluster) {
  const { moving, stopped, offline } = cluster.counts;
  const total = cluster.total;

  const movingPercent = (moving / total) * 100;
  const stoppedPercent = (stopped / total) * 100;

  const iconSize = Math.min(54, 42 + Math.log2(total) * 2);

  const html = `
    <div style="
      width:${iconSize}px;
      height:${iconSize}px;
      box-sizing:border-box;
      border-radius:50%;
      background:conic-gradient(
        #14B8A6 0% ${movingPercent}%,
        #F59E0B ${movingPercent}% ${movingPercent + stoppedPercent}%,
        #64748B ${movingPercent + stoppedPercent}% 100%
      );
      display:flex;
      align-items:center;
      justify-content:center;
      box-shadow:0 2px 7px #0005;
      border:1px solid #ffffff;
    ">
      <div style="
        width:${iconSize - 12}px;
        height:${iconSize - 12}px;
        box-sizing:border-box;
        border-radius:50%;
        background:#ffffff;
        color:#1f2937;
        display:flex;
        align-items:center;
        justify-content:center;
        font-family:Tahoma,sans-serif;
        font-size:14px;
        font-weight:700;
        line-height:1;
        visibility:visible;
        opacity:1;
      ">${total}</div>
    </div>
  `;

  return L.divIcon({
    className: 'sana-map-cluster-icon',
    html,
    iconSize: [iconSize, iconSize],
    iconAnchor: [iconSize / 2, iconSize / 2],
  });
}
export function createClusterSummary(cluster) {
  const { moving, stopped, offline } = cluster.counts;

  return `
    <div dir="rtl" style="
      min-width:150px;
      padding:9px 12px;
      font-family:Tahoma,sans-serif;
      font-size:12px;
      line-height:2;
      color:#1f2937;
      background:#ffffff;
      border-radius:9px;
      box-shadow:0 2px 12px #0003;
    ">
      <div style="font-weight:700;margin-bottom:3px">
        ${cluster.total} دستگاه در این محدوده
      </div>
      <div><span style="color:#14B8A6">●</span> در حرکت: ${moving}</div>
      <div><span style="color:#F59E0B">●</span> متوقف: ${stopped}</div>
      <div><span style="color:#64748B">●</span> آفلاین: ${offline}</div>
    </div>
  `;
}
