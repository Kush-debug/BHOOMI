import React, { useEffect, useState } from 'react';
import {
  BarChart3, Download, AlertTriangle, Info, Loader2
} from 'lucide-react';
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid
} from 'recharts';
import api from '../services/api';
import { useLanguage } from '../context/LanguageContext';

// This page previously rendered hardcoded arrays claiming measured OCR accuracy
// ("Hindi 96.2% across 18,450 documents") for evaluations that had never been
// run. Everything below is fetched from /analytics, which computes from stored
// rows, and reports engine CONFIDENCE rather than accuracy.

const EmptyState = ({ message }) => (
  <div className="h-60 flex flex-col items-center justify-center text-center text-slate-400 gap-2">
    <BarChart3 className="w-8 h-8" />
    <p className="text-xs max-w-xs">{message}</p>
  </div>
);

export const Reports = () => {
  const { t } = useLanguage();
  const [quality, setQuality] = useState(null);
  const [throughput, setThroughput] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let alive = true;
    Promise.all([api.get('/analytics/quality'), api.get('/analytics/throughput')])
      .then(([q, th]) => {
        if (!alive) return;
        setQuality(q.data);
        setThroughput(th.data);
      })
      .catch((e) => alive && setError(e.response?.data?.detail || t('reports.loadError', 'Could not load analytics.')))
      .finally(() => alive && setLoading(false));
    return () => { alive = false; };
  }, [t]);

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-slate-500 text-sm p-8">
        <Loader2 className="w-4 h-4 animate-spin" /> {t('reports.loadingAnalytics', 'Loading analytics...')}
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-xl p-5 text-sm text-red-800 flex gap-3">
        <AlertTriangle className="w-5 h-5 shrink-0" />
        <div>{String(error)}</div>
      </div>
    );
  }

  const grounding = quality?.evidence_grounding;
  const hasQuality = (quality?.documents_measured || 0) > 0;

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
            <BarChart3 className="w-5 h-5 text-emerald-700" />
            {t('nav.reports', 'Digitization Analytics')}
          </h2>
          <p className="text-xs text-slate-500 mt-1">
            {t('reports.subtitle', 'Computed from processed documents in this deployment.')}
          </p>
        </div>
        <a
          href="/api/v1/records/export/csv"
          className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-bold text-white bg-emerald-700 hover:bg-emerald-800 rounded-lg shadow-xs transition-colors"
        >
          <Download className="w-4 h-4" /> {t('reports.exportCsv', 'Export verified registry (CSV)')}
        </a>
      </div>

      <div className="bg-sky-50 border border-sky-200 rounded-xl p-4 text-xs text-sky-900 flex gap-3">
        <Info className="w-4 h-4 shrink-0 mt-0.5" />
        <p>{quality?.measurement_note}</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs">
          <h3 className="text-sm font-bold text-slate-900 mb-1">{t('reports.ocrConfidenceByLanguage', 'Mean OCR confidence by detected language')}</h3>
          <p className="text-xs text-slate-500 mb-4">
            {t('reports.ocrConfidenceByLanguageDesc', 'Engine-reported confidence, averaged per document')}
          </p>
          <div className="h-60">
            {hasQuality ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={quality.by_language}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                  <XAxis dataKey="language" tick={{ fontSize: 11 }} stroke="#94a3b8" />
                  <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} stroke="#94a3b8" />
                  <Tooltip formatter={(v, n, p) => [`${v}%`, `${p.payload.documents} ${t('reports.documentsUnit', 'document(s)')}`]} />
                  <Bar dataKey="mean_ocr_confidence" fill="#059669" name={t('reports.meanConfidencePct', 'Mean confidence %')} radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <EmptyState message={t('reports.emptyNoDocuments', 'No documents have been processed yet. Upload and process a document to populate this chart.')} />
            )}
          </div>
        </div>

        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs">
          <h3 className="text-sm font-bold text-slate-900 mb-1">{t('reports.extractionConfidenceByType', 'Mean extraction confidence by document type')}</h3>
          <p className="text-xs text-slate-500 mb-4">{t('reports.extractionConfidenceByTypeDesc', 'Derived from the OCR regions backing each field')}</p>
          <div className="h-60">
            {quality?.by_document_type?.length ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={quality.by_document_type}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                  <XAxis dataKey="document_type" tick={{ fontSize: 11 }} stroke="#94a3b8" />
                  <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} stroke="#94a3b8" />
                  <Tooltip formatter={(v, n, p) => [`${v}%`, `${p.payload.documents} ${t('reports.documentsUnit', 'document(s)')}`]} />
                  <Bar dataKey="mean_extraction_confidence" fill="#0f766e" name={t('reports.meanConfidencePct', 'Mean confidence %')} radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <EmptyState message={t('reports.emptyNoExtraction', 'No extraction confidence recorded yet.')} />
            )}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs">
          <h3 className="text-sm font-bold text-slate-900 mb-3">{t('reports.evidenceGrounding', 'Evidence grounding')}</h3>
          <p className="text-xs text-slate-500 mb-4">
            {t('reports.evidenceGroundingDesc', 'Share of extracted values that could be traced back to specific OCR word regions on the page. Ungrounded values are shown to officers without a source region rather than with a placeholder highlight.')}
          </p>
          <div className="grid grid-cols-3 gap-3 text-center">
            <div className="p-3 rounded-lg bg-emerald-50 border border-emerald-100">
              <div className="text-lg font-bold text-emerald-800">{grounding?.fields_with_source_region ?? 0}</div>
              <div className="text-[10px] uppercase font-bold text-emerald-700 mt-1">{t('reports.withRegion', 'With region')}</div>
            </div>
            <div className="p-3 rounded-lg bg-amber-50 border border-amber-100">
              <div className="text-lg font-bold text-amber-800">{grounding?.fields_without_source_region ?? 0}</div>
              <div className="text-[10px] uppercase font-bold text-amber-700 mt-1">{t('reports.withoutRegion', 'Without region')}</div>
            </div>
            <div className="p-3 rounded-lg bg-slate-50 border border-slate-200">
              <div className="text-lg font-bold text-slate-800">
                {grounding?.grounded_share_pct === null || grounding?.grounded_share_pct === undefined
                  ? '--'
                  : `${grounding.grounded_share_pct}%`}
              </div>
              <div className="text-[10px] uppercase font-bold text-slate-600 mt-1">{t('reports.grounded', 'Grounded')}</div>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs">
          <h3 className="text-sm font-bold text-slate-900 mb-3">{t('reports.processingFailures', 'Processing failures')}</h3>
          <p className="text-xs text-slate-500 mb-4">
            {t('reports.processingFailuresDesc', 'Documents the pipeline could not process, by reason. Failures are reported, never replaced with generated output.')}
          </p>
          {throughput?.processing_failures?.length ? (
            <table className="w-full text-xs">
              <thead>
                <tr className="text-left text-slate-500 border-b border-slate-100">
                  <th className="py-1.5 font-semibold">{t('reports.reason', 'Reason')}</th>
                  <th className="py-1.5 font-semibold">{t('reports.stage', 'Stage')}</th>
                  <th className="py-1.5 font-semibold text-right">{t('reports.count', 'Count')}</th>
                </tr>
              </thead>
              <tbody>
                {throughput.processing_failures.map((f) => (
                  <tr key={`${f.code}-${f.stage}`} className="border-b border-slate-50">
                    <td className="py-1.5 font-mono text-[11px]">{f.code}</td>
                    <td className="py-1.5 text-slate-600">{f.stage}</td>
                    <td className="py-1.5 text-right font-bold">{f.count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="text-xs text-slate-400 py-6 text-center">{t('reports.noFailures', 'No processing failures recorded.')}</p>
          )}
        </div>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs">
        <h3 className="text-sm font-bold text-slate-900 mb-1">{t('reports.correctionsByField', 'Human corrections by field')}</h3>
        <p className="text-xs text-slate-500 mb-4">
          {t('reports.correctionsByFieldDesc', 'Where officers most often correct the system.')} {throughput?.total_human_corrections ?? 0} {t('reports.correctionsUnit', 'correction(s) recorded.')}
        </p>
        {throughput?.human_corrections_by_field?.length ? (
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={throughput.human_corrections_by_field} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" horizontal={false} />
                <XAxis type="number" tick={{ fontSize: 11 }} stroke="#94a3b8" allowDecimals={false} />
                <YAxis type="category" dataKey="field" width={140} tick={{ fontSize: 11 }} stroke="#94a3b8" />
                <Tooltip />
                <Bar dataKey="corrections" fill="#b45309" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <EmptyState message={t('reports.emptyNoCorrections', 'No officer corrections recorded yet. This chart fills in as documents are verified.')} />
        )}
      </div>
    </div>
  );
};
