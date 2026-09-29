import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Database, Map, Search, RefreshCw, AlertTriangle, LogIn } from 'lucide-react';
import api from '../services/api';
import { useLanguage } from '../context/LanguageContext';

// The staff Dashboard (Dashboard.jsx) requests /dashboard/stats,
// /documents/?limit=6 and /validation/anomalies?limit=5 - all three are
// staff-only (CAN_READ_ANALYTICS / CAN_READ_DOCUMENTS / CAN_READ_FINDINGS in
// backend/app/auth/rbac.py), and Promise.all rejects on the first 403,
// leaving `stats` permanently null with loading already false - the
// dashboard renders "Loading..." forever with nothing left running to end
// it. This is a separate, viewer-only component so it only ever calls
// /dashboard/public-summary, an endpoint every role can read, and every
// outcome (loading, success, empty, 401, 403, 500, network failure) has its
// own explicit render branch - never a spinner with nothing behind it.

const STATUS = { LOADING: 'loading', SUCCESS: 'success', EMPTY: 'empty', UNAUTHORIZED: 'unauthorized', FORBIDDEN: 'forbidden', SERVER_ERROR: 'server_error', NETWORK_ERROR: 'network_error' };

export const ViewerDashboard = () => {
  const { t } = useLanguage();
  const [status, setStatus] = useState(STATUS.LOADING);
  const [summary, setSummary] = useState(null);

  const fetchSummary = async () => {
    setStatus(STATUS.LOADING);
    try {
      const res = await api.get('/dashboard/public-summary');
      const data = res.data || {};
      setSummary(data);
      const hasAnything = (data.verified_land_records || 0) > 0 || (data.verified_gis_parcels || 0) > 0;
      setStatus(hasAnything ? STATUS.SUCCESS : STATUS.EMPTY);
    } catch (err) {
      const code = err.response?.status;
      if (code === 401) setStatus(STATUS.UNAUTHORIZED);
      else if (code === 403) setStatus(STATUS.FORBIDDEN);
      else if (code >= 500) setStatus(STATUS.SERVER_ERROR);
      else setStatus(STATUS.NETWORK_ERROR);
    }
  };

  useEffect(() => {
    fetchSummary();
  }, []);

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-xs">
        <h2 className="text-xl font-bold text-slate-900 tracking-tight">
          {t('viewerDashboard.title', 'Public Land Record Portal')}
        </h2>
        <p className="text-xs text-slate-500 mt-1">
          {t('viewerDashboard.subtitle', 'Search verified land records and view cadastral parcel maps that have been made available for public viewing.')}
        </p>
      </div>

      {status === STATUS.LOADING && (
        <div className="flex items-center justify-center min-h-[30vh]">
          <div className="flex flex-col items-center gap-3">
            <RefreshCw className="w-7 h-7 text-emerald-700 animate-spin" />
            <span className="text-sm font-semibold text-slate-600">{t('viewerDashboard.loadingPublicRecords', 'Loading public records...')}</span>
          </div>
        </div>
      )}

      {status === STATUS.UNAUTHORIZED && (
        <ErrorPanel
          title={t('viewerDashboard.sessionExpiredTitle', 'Your session has expired')}
          message={t('viewerDashboard.sessionExpiredMessage', 'Please sign in again to continue.')}
          action={
            <Link
              to="/login"
              className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-bold text-white bg-emerald-700 hover:bg-emerald-800 rounded-lg shadow-xs transition-colors"
            >
              <LogIn className="w-3.5 h-3.5" /> {t('viewerDashboard.goToSignIn', 'Go to Sign In')}
            </Link>
          }
        />
      )}

      {status === STATUS.FORBIDDEN && (
        <ErrorPanel
          title={t('viewerDashboard.notAvailableTitle', 'Not available')}
          message={t('viewerDashboard.notAvailableMessage', 'This information is not available for your account.')}
          action={<RetryButton onClick={fetchSummary} label={t('common.tryAgain', 'Try Again')} />}
        />
      )}

      {(status === STATUS.SERVER_ERROR || status === STATUS.NETWORK_ERROR) && (
        <ErrorPanel
          title={t('viewerDashboard.unableToLoadTitle', 'Unable to load this page')}
          message={t('viewerDashboard.unableToLoadMessage', 'Please try again in a moment.')}
          action={<RetryButton onClick={fetchSummary} label={t('common.tryAgain', 'Try Again')} />}
        />
      )}

      {status === STATUS.EMPTY && (
        <div className="bg-white rounded-xl border border-slate-200 p-10 text-center">
          <Database className="w-8 h-8 text-slate-300 mx-auto mb-3" />
          <p className="text-sm font-semibold text-slate-600">{t('viewerDashboard.noPublicRecords', 'No public records available.')}</p>
          <p className="text-xs text-slate-400 mt-1">{t('viewerDashboard.checkBackLater', 'Check back once records have been verified.')}</p>
        </div>
      )}

      {status === STATUS.SUCCESS && summary && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs">
            <div className="flex items-center gap-2 text-slate-400 text-[10px] font-bold uppercase tracking-wider">
              <Database className="w-4 h-4" /> {t('viewerDashboard.availableLandRecords', 'Available Land Records')}
            </div>
            <div className="text-3xl font-bold text-slate-900 mt-2">
              {(summary.verified_land_records ?? 0).toLocaleString()}
            </div>
            <p className="text-xs text-slate-500 mt-1">{t('viewerDashboard.verifiedRecordsAvailable', 'Verified records available to search')}</p>
          </div>
          <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs">
            <div className="flex items-center gap-2 text-slate-400 text-[10px] font-bold uppercase tracking-wider">
              <Map className="w-4 h-4" /> {t('viewerDashboard.availableGisParcels', 'Available GIS Parcels')}
            </div>
            <div className="text-3xl font-bold text-slate-900 mt-2">
              {(summary.verified_gis_parcels ?? 0).toLocaleString()}
            </div>
            <p className="text-xs text-slate-500 mt-1">{t('viewerDashboard.verifiedParcelsOnMap', 'Verified parcels on the cadastral map')}</p>
          </div>
        </div>
      )}

      {(status === STATUS.SUCCESS || status === STATUS.EMPTY) && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Link
            to="/records"
            className="group bg-white rounded-xl border border-slate-200 p-5 shadow-xs hover:border-emerald-300 hover:shadow-sm transition-all flex items-center gap-4"
          >
            <div className="w-11 h-11 rounded-lg bg-emerald-50 border border-emerald-100 flex items-center justify-center shrink-0">
              <Search className="w-5 h-5 text-emerald-700" />
            </div>
            <div>
              <div className="text-sm font-bold text-slate-900 group-hover:text-emerald-800">
                {t('viewerDashboard.searchLandRecords', 'Search Land Records')}
              </div>
              <p className="text-xs text-slate-500">{t('viewerDashboard.searchLandRecordsDesc', 'Find records by Khasra, Khata, owner name, or village')}</p>
            </div>
          </Link>
          <Link
            to="/gis"
            className="group bg-white rounded-xl border border-slate-200 p-5 shadow-xs hover:border-emerald-300 hover:shadow-sm transition-all flex items-center gap-4"
          >
            <div className="w-11 h-11 rounded-lg bg-emerald-50 border border-emerald-100 flex items-center justify-center shrink-0">
              <Map className="w-5 h-5 text-emerald-700" />
            </div>
            <div>
              <div className="text-sm font-bold text-slate-900 group-hover:text-emerald-800">
                {t('nav.gisMap', 'Cadastral GIS Map')}
              </div>
              <p className="text-xs text-slate-500">{t('viewerDashboard.gisMapDesc', 'View parcel boundaries and location on the map')}</p>
            </div>
          </Link>
        </div>
      )}
    </div>
  );
};

const RetryButton = ({ onClick, label }) => (
  <button
    onClick={onClick}
    className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-bold text-white bg-emerald-700 hover:bg-emerald-800 rounded-lg shadow-xs transition-colors"
  >
    <RefreshCw className="w-3.5 h-3.5" /> {label}
  </button>
);

const ErrorPanel = ({ title, message, action }) => (
  <div className="bg-white rounded-xl border border-slate-200 p-10 text-center">
    <AlertTriangle className="w-8 h-8 text-amber-400 mx-auto mb-3" />
    <p className="text-sm font-bold text-slate-700">{title}</p>
    <p className="text-xs text-slate-500 mt-1 mb-4">{message}</p>
    <div className="flex justify-center">{action}</div>
  </div>
);
