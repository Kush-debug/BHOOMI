import React, { useState, useEffect, useRef } from 'react';
import {
  MapPin,
  Search,
  Layers,
  CheckCircle2,
  AlertCircle,
  Eye,
  Info,
  Maximize2,
  RefreshCw,
  ExternalLink
} from 'lucide-react';
import L from 'leaflet';
import api from '../services/api';
import { StatusBadge } from '../components/common/Badge';
import { useLanguage } from '../context/LanguageContext';

export const GISMap = () => {
  const { t } = useLanguage();
  const [geoData, setGeoData] = useState(null);
  const [selectedParcel, setSelectedParcel] = useState(null);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [basemap, setBasemap] = useState('osm'); // 'osm' or 'satellite'

  const mapContainerRef = useRef(null);
  const mapInstanceRef = useRef(null);
  const geoJsonLayerRef = useRef(null);
  const tileLayerRef = useRef(null);

  useEffect(() => {
    fetchParcels();
  }, []);

  const fetchParcels = async () => {
    setLoading(true);
    try {
      const res = await api.get('/gis/parcels');
      setGeoData(res.data);
      if (res.data.features && res.data.features.length > 0) {
        setSelectedParcel(res.data.features[0].properties);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  // Initialize and Update Leaflet Map
  useEffect(() => {
    if (!mapContainerRef.current) return;

    if (!mapInstanceRef.current) {
      const map = L.map(mapContainerRef.current, {
        center: [26.8530, 80.0540],
        zoom: 16,
        scrollWheelZoom: true
      });
      mapInstanceRef.current = map;

      const tileUrl = basemap === 'osm'
        ? 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png'
        : 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}';

      tileLayerRef.current = L.tileLayer(tileUrl, {
        attribution: '&copy; OpenStreetMap contributors / NIC Bhulekh GIS',
        maxZoom: 19
      }).addTo(map);
    }

    return () => {
      // cleanup on unmount
    };
  }, []);

  // Update Basemap Layer
  useEffect(() => {
    if (!mapInstanceRef.current || !tileLayerRef.current) return;
    mapInstanceRef.current.removeLayer(tileLayerRef.current);

    const tileUrl = basemap === 'osm'
      ? 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png'
      : 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}';

    tileLayerRef.current = L.tileLayer(tileUrl, {
      attribution: '&copy; OpenStreetMap / Esri Imagery',
      maxZoom: 19
    }).addTo(mapInstanceRef.current);
  }, [basemap]);

  // Update GeoJSON Layer
  useEffect(() => {
    if (!mapInstanceRef.current || !geoData) return;

    if (geoJsonLayerRef.current) {
      mapInstanceRef.current.removeLayer(geoJsonLayerRef.current);
    }

    const getParcelStyle = (feature) => {
      const status = feature.properties.verification_status;
      let color = '#059669'; // verified green
      let fill = '#10B981';

      if (status === 'mismatch' || status === 'disputed') {
        color = '#DC2626'; // Red
        fill = '#EF4444';
      } else if (status === 'pending') {
        color = '#D97706'; // Amber
        fill = '#F59E0B';
      }

      return {
        color: color,
        weight: 2,
        fillColor: fill,
        fillOpacity: 0.45
      };
    };

    const layer = L.geoJSON(geoData, {
      style: getParcelStyle,
      onEachFeature: (feature, l) => {
        const props = feature.properties;
        l.bindTooltip(
          `<b>${t('gisMap.khasraLabel', 'Khasra')}: ${props.khasra_number}</b><br/>${props.owner_name}<br/>${props.area} ${props.area_unit}`,
          { className: 'custom-parcel-tooltip', sticky: true }
        );

        l.on({
          click: () => {
            setSelectedParcel(props);
          },
          mouseover: (e) => {
            e.target.setStyle({ fillOpacity: 0.75, weight: 3 });
          },
          mouseout: (e) => {
            e.target.setStyle({ fillOpacity: 0.45, weight: 2 });
          }
        });
      }
    }).addTo(mapInstanceRef.current);

    geoJsonLayerRef.current = layer;
    try {
      const bounds = layer.getBounds();
      if (bounds.isValid()) {
        mapInstanceRef.current.fitBounds(bounds, { padding: [30, 30] });
      }
    } catch (e) {
      // ignore
    }
  }, [geoData]);

  const handleSearch = (e) => {
    e.preventDefault();
    if (!search || !geoData) return;
    const q = search.toLowerCase();
    const match = geoData.features.find(f =>
      f.properties.khasra_number?.toLowerCase() === q ||
      f.properties.owner_name?.toLowerCase().includes(q) ||
      f.properties.khata_number?.toLowerCase() === q
    );
    if (match) {
      setSelectedParcel(match.properties);
    } else {
      alert(`${t('gisMap.noParcelFound', 'No parcel found matching')} "${search}".`);
    }
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold text-slate-900 tracking-tight flex items-center gap-2">
            <MapPin className="w-5 h-5 text-emerald-700" />
            {t('gisMap.title', 'Cadastral GIS Land Map (भू-नक्शा Viewer)')}
          </h2>
          <p className="text-xs text-slate-500">
            {t('gisMap.subtitle', 'Interactive PostGIS / GeoJSON parcel visualization with status-coded boundaries & survey attributes.')}
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setBasemap(basemap === 'osm' ? 'satellite' : 'osm')}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg border border-slate-200 bg-slate-50 hover:bg-slate-100 text-slate-700 transition-colors"
          >
            <Layers className="w-3.5 h-3.5 text-slate-500" />
            <span>{t('gisMap.layer', 'Layer')}: {basemap === 'osm' ? t('gisMap.standardMap', 'Standard Map') : t('gisMap.satelliteImagery', 'Satellite Imagery')}</span>
          </button>
          <button
            onClick={fetchParcels}
            className="p-1.5 text-slate-500 hover:text-slate-900 border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Map Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Main Leaflet Map View */}
        <div className="lg:col-span-8 bg-white rounded-xl border border-slate-200 overflow-hidden shadow-xs h-[650px] relative">
          {/* Map Top Floating Search */}
          <div className="absolute top-3 left-12 z-20 w-80 bg-white/95 backdrop-blur-xs p-1.5 rounded-lg shadow-lg border border-slate-200">
            <form onSubmit={handleSearch} className="flex items-center gap-2">
              <input
                type="text"
                placeholder={t('gisMap.searchPlaceholder', 'Search Khasra No, Khata No, Owner...')}
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full text-xs px-2.5 py-1.5 border border-slate-300 rounded focus:ring-emerald-500 focus:border-emerald-500"
              />
              <button
                type="submit"
                className="px-2.5 py-1.5 bg-emerald-700 text-white rounded text-xs font-bold hover:bg-emerald-800"
              >
                {t('common.search', 'Search')}
              </button>
            </form>
          </div>

          {/* Map Legend */}
          <div className="absolute bottom-4 right-4 z-20 bg-white/95 backdrop-blur-xs p-3 rounded-lg shadow-lg border border-slate-200 text-[11px] space-y-1.5">
            <div className="font-bold text-slate-900 uppercase text-[10px]">{t('gisMap.legendTitle', 'Parcel Status Legend')}</div>
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 rounded bg-emerald-500 border border-emerald-700" />
              <span>{t('gisMap.legendVerified', 'Verified Parcel')}</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 rounded bg-amber-500 border border-amber-700" />
              <span>{t('dashboard.pendingVerification', 'Pending Verification')}</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 rounded bg-red-500 border border-red-700" />
              <span>{t('gisMap.legendDisputed', 'Area Mismatch / Disputed')}</span>
            </div>
          </div>

          <div ref={mapContainerRef} className="h-full w-full" />
        </div>

        {/* Selected Parcel Inspector Panel */}
        <div className="lg:col-span-4 bg-white rounded-xl border border-slate-200 p-5 shadow-xs flex flex-col justify-between h-[650px] overflow-y-auto">
          {selectedParcel ? (
            <div className="space-y-4 text-xs">
              <div className="border-b border-slate-100 pb-3">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                    {t('gisMap.plotInspector', 'Cadastral Plot Inspector')}
                  </span>
                  <StatusBadge status={selectedParcel.verification_status} />
                </div>
                <h3 className="text-lg font-bold text-slate-900 mt-1">
                  {t('gisMap.khasraPlot', 'Khasra / Plot')} #{selectedParcel.khasra_number}
                </h3>
                <p className="text-slate-500 text-[11px]">
                  {selectedParcel.village}, {selectedParcel.tehsil}, {selectedParcel.district}
                </p>
              </div>

              {/* Attributes Card */}
              <div className="space-y-2.5 bg-slate-50 p-4 rounded-xl border border-slate-200">
                <div>
                  <span className="text-slate-400 block text-[10px] uppercase font-bold">{t('gisMap.landholder', 'Landholder (Owner Name)')}</span>
                  <span className="font-bold text-slate-900 text-sm">{selectedParcel.owner_name}</span>
                </div>
                <div className="grid grid-cols-2 gap-2 pt-1">
                  <div>
                    <span className="text-slate-400 block text-[10px] uppercase font-bold">{t('gisMap.khataNumber', 'Khata Number')}</span>
                    <span className="font-mono font-semibold text-slate-800">{selectedParcel.khata_number}</span>
                  </div>
                  <div>
                    <span className="text-slate-400 block text-[10px] uppercase font-bold">{t('gisMap.surveyExtent', 'Survey Extent')}</span>
                    <span className="font-bold text-slate-900">{selectedParcel.area} {selectedParcel.area_unit}</span>
                  </div>
                </div>
                <div className="pt-1">
                  <span className="text-slate-400 block text-[10px] uppercase font-bold">{t('gisMap.landClassification', 'Land Classification')}</span>
                  <span className="font-semibold text-slate-800">{selectedParcel.land_classification}</span>
                </div>
              </div>

              {/* Spatial Cadastral Coordinates Metadata */}
              <div className="bg-white p-3.5 rounded-xl border border-slate-200 space-y-1.5 text-[11px]">
                <div className="font-bold text-slate-900">{t('gisMap.spatialMetadata', 'Spatial PostGIS Metadata')}</div>
                <div className="text-slate-600">
                  <span className="text-slate-400">{t('gisMap.projection', 'Projection')}:</span> EPSG:4326 (WGS 84)
                </div>
                <div className="text-slate-600">
                  <span className="text-slate-400">{t('gisMap.geometryType', 'Geometry Type')}:</span> GeoJSON Polygon
                </div>
                <div className="text-slate-600">
                  <span className="text-slate-400">{t('gisMap.qgisCompatible', 'QGIS / GeoServer Compatible')}:</span> {t('common.yes', 'Yes')}
                </div>
              </div>
            </div>
          ) : (
            <div className="text-center py-16 text-slate-400 text-xs">
              {t('gisMap.clickToInspect', 'Click any parcel on the map to inspect ownership & cadastral attributes.')}
            </div>
          )}

          <div className="pt-4 border-t border-slate-100">
            <a
              href="/records"
              className="w-full py-2 px-4 rounded-lg bg-emerald-700 hover:bg-emerald-800 text-white font-bold text-xs flex items-center justify-center gap-1.5 shadow-xs transition-colors"
            >
              {t('gisMap.openFullRegistry', 'Open Full Land Registry')} &rarr;
            </a>
          </div>
        </div>
      </div>
    </div>
  );
};
