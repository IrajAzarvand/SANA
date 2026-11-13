import { useEffect, useState } from 'react';
import { Marker, Popup, useMap } from 'react-leaflet';
import L from 'leaflet';
import {
  getDeviceClusters,
  createClusterIcon,
} from '../deviceClusters';

export default function DeviceMarkersLayer({
  positions,
  followPosition,
  renderDeviceMarker,
}) {
  const map = useMap();
  const [clusters, setClusters] = useState([]);

  useEffect(() => {
    const refresh = () => {
      setClusters(getDeviceClusters(map, positions, followPosition));
    };

    refresh();
    map.on('zoomend moveend', refresh);

    return () => {
      map.off('zoomend moveend', refresh);
    };
  }, [map, positions, followPosition]);

  return clusters.map((item) => {
    if (item.type === 'device') {
      return renderDeviceMarker(item.position);
    }

    const cluster = item;

    return (
      <Marker
        key={cluster.id}
        position={[cluster.latitude, cluster.longitude]}
        icon={createClusterIcon(L, cluster)}
        bubblingMouseEvents={false}
        eventHandlers={{
          mouseover(event) {
            event.target.openPopup();
          },
          mouseout(event) {
            event.target.closePopup();
          },
          click(event) {
            event.originalEvent?.stopPropagation();
            event.target.openPopup();
          },
        }}
      >
        <Popup
          closeButton={false}
          closeOnClick
          autoPan={false}
          className="sana-cluster-popup"
        >
          <div
            dir="rtl"
            style={{
              minWidth: 150,
              padding: '5px 8px',
              fontFamily: 'Tahoma, sans-serif',
              fontSize: 12,
              lineHeight: 2,
              color: '#1f2937',
            }}
          >
            <strong>{cluster.total} دستگاه در این محدوده</strong>
            <div>
              <span style={{ color: '#14B8A6' }}>●</span>
              {' '}در حرکت: {cluster.counts.moving}
            </div>
            <div>
              <span style={{ color: '#F59E0B' }}>●</span>
              {' '}متوقف: {cluster.counts.stopped}
            </div>
            <div>
              <span style={{ color: '#64748B' }}>●</span>
              {' '}آفلاین: {cluster.counts.offline}
            </div>
          </div>
        </Popup>
      </Marker>
    );
  });
}
