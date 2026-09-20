import React, { useEffect, useState } from 'react';
import { Settings as SettingsIcon, Cpu, ShieldCheck, AlertTriangle, Loader2, User as UserIcon, Globe } from 'lucide-react';
import api from '../services/api';
import { useAuth } from '../context/AuthContext';
import { useLanguage } from '../context/LanguageContext';

// This page previously presented editable threshold inputs whose submit handler
// set a "Saved" flag and called nothing. It is now a read-only view of the
// server's actual runtime configuration. Editable settings return in a later
// phase, backed by a real configuration endpoint.

const Row = ({ label, value, mono }) => (
  <div className="flex items-start justify-between gap-4 py-2 border-b border-slate-100 last:border-0">
    <span className="text-slate-600">{label}</span>
    <span className={`text-slate-900 font-semibold text-right ${mono ? 'font-mono text-[11px]' : ''}`}>
      {value}
    </span>
  </div>
);

// The OCR engine / processing policy panels below describe internal
// pipeline configuration (backend/app/auth/rbac.py gates the endpoint they
// read, /processing/engine-status, to CAN_READ_DOCUMENTS = STAFF_ROLES) -
// not something a public/citizen viewer's account settings should show.
// This is a plain account panel instead, calling no staff-only endpoint.
const ViewerSettings = () => {
  const { user } = useAuth();
  const { t, currentLanguage, changeLanguage, supportedLanguages } = useLanguage();

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-xs">
        <h2 className="text-xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
          <SettingsIcon className="w-5 h-5 text-emerald-700" />
          {t('nav.settings', 'Settings')}
        </h2>
        <p className="text-xs text-slate-500 mt-1">{t('settings.accountSubtitle', 'Your account and display preferences.')}</p>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-xs text-xs">
        <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider border-b border-slate-100 pb-2 mb-3 flex items-center gap-2">
          <UserIcon className="w-4 h-4 text-emerald-700" /> {t('settings.account', 'Account')}
        </h3>
        <Row label={t('settings.name', 'Name')} value={user?.full_name || '—'} />
        <Row label={t('settings.accountType', 'Account type')} value={t('settings.publicViewer', 'Public Viewer')} />
      </div>

      <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-xs text-xs">
        <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider border-b border-slate-100 pb-2 mb-3 flex items-center gap-2">
          <Globe className="w-4 h-4 text-emerald-700" /> {t('settings.displayLanguage', 'Display language')}
        </h3>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 pt-1">
          {supportedLanguages.map((lang) => (
            <button
              key={lang.code}
              onClick={() => changeLanguage(lang.code)}
              className={`px-3 py-2 rounded-lg border text-left transition-colors ${
                currentLanguage === lang.code
                  ? 'border-emerald-300 bg-emerald-50 font-bold text-emerald-800'
                  : 'border-slate-200 text-slate-600 hover:bg-slate-50'
              }`}
            >
              {lang.flag} {lang.native}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
};

export const Settings = () => {
  const { user } = useAuth();
  const { t } = useLanguage();
  const [ocr, setOcr] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (user?.role === 'viewer') return undefined;
    let alive = true;
    api
      .get('/processing/engine-status')
      .then((res) => alive && setOcr(res.data))
      .catch((e) => alive && setError(e.response?.data?.detail || t('settings.engineStatusError', 'Could not read engine status.')))
      .finally(() => alive && setLoading(false));
    return () => { alive = false; };
  }, [user?.role, t]);

  if (user?.role === 'viewer') {
    return <ViewerSettings />;
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-xs">
        <h2 className="text-xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
          <SettingsIcon className="w-5 h-5 text-emerald-700" />
          {t('settings.systemConfiguration', 'System configuration')}
        </h2>
        <p className="text-xs text-slate-500 mt-1">
          {t('settings.systemConfigSubtitle', "Read-only view of this server's runtime configuration.")}
        </p>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-xs text-xs">
        <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider border-b border-slate-100 pb-2 mb-3 flex items-center gap-2">
          <Cpu className="w-4 h-4 text-emerald-700" /> {t('sidebar.ocrEngine', 'OCR engine')}
        </h3>
        {loading && (
          <div className="flex items-center gap-2 text-slate-500 py-4">
            <Loader2 className="w-4 h-4 animate-spin" /> {t('settings.readingEngineStatus', 'Reading engine status...')}
          </div>
        )}
        {error && (
          <div className="flex gap-2 text-red-700 bg-red-50 border border-red-200 rounded-lg p-3">
            <AlertTriangle className="w-4 h-4 shrink-0" /> {String(error)}
          </div>
        )}
        {ocr && (
          <div>
            <Row label={t('settings.engine', 'Engine')} value={ocr.engine} />
            <Row
              label={t('common.status', 'Status')}
              value={
                ocr.available ? (
                  <span className="text-emerald-700">{t('settings.available', 'Available')}</span>
                ) : (
                  <span className="text-red-700">{t('sidebar.unavailable', 'Unavailable')}</span>
                )
              }
            />
            <Row label={t('settings.version', 'Version')} value={ocr.version} mono />
            <Row
              label={t('settings.installedLanguagePacks', 'Installed language packs')}
              value={ocr.installed_language_packs?.join(', ') || t('settings.none', 'none')}
              mono
            />
            <Row
              label={t('settings.supportedLanguages', 'Supported languages')}
              value={`${ocr.supported_language_count} (${ocr.supported_iso_languages?.join(', ') || t('settings.none', 'none')})`}
            />
            {!ocr.available && (
              <p className="mt-3 text-amber-800 bg-amber-50 border border-amber-200 rounded-lg p-3">
                {t('settings.engineUnavailableNote', 'Document processing will return an explicit error while the engine is unavailable. It will not fall back to generated text.')}
              </p>
            )}
          </div>
        )}
      </div>

      <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-xs text-xs">
        <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider border-b border-slate-100 pb-2 mb-3 flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-emerald-700" /> {t('settings.processingPolicy', 'Processing policy')}
        </h3>
        <Row label={t('settings.fabricatedOutput', 'Fabricated output on failure')} value={t('settings.disabled', 'Disabled')} />
        <Row label={t('settings.boundingBoxes', 'Bounding boxes without OCR geometry')} value={t('settings.neverGenerated', 'Never generated')} />
        <Row label={t('settings.confidenceWhenNotMeasurable', 'Confidence when not measurable')} value={t('settings.reportedAsUnknown', 'Reported as unknown')} />
        <Row label={t('settings.officerCorrections', 'Officer corrections')} value={t('settings.recordedSeparately', 'Recorded separately from AI output')} />
        <p className="mt-3 text-slate-500">
          {t('settings.thresholdsNote', 'Confidence thresholds and validation rules are configured server-side via environment variables. An editable configuration screen is planned once the settings are backed by a real endpoint.')}
        </p>
      </div>
    </div>
  );
};
