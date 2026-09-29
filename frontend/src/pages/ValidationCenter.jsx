import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { AlertTriangle, CheckCircle2, ShieldAlert, Filter, RefreshCw, Eye } from 'lucide-react';
import api from '../services/api';
import { useLanguage } from '../context/LanguageContext';

export const ValidationCenter = () => {
  const { t } = useLanguage();
  const [anomalies, setAnomalies] = useState([]);
  const [loading, setLoading] = useState(true);
  const [severityFilter, setSeverityFilter] = useState('');

  useEffect(() => {
    fetchAnomalies();
  }, [severityFilter]);

  const fetchAnomalies = async () => {
    setLoading(true);
    try {
      const url = severityFilter ? `/validation/anomalies?severity=${severityFilter}` : '/validation/anomalies';
      const res = await api.get(url);
      setAnomalies(res.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleResolve = async (id) => {
    try {
      // Resolving a finding is an officer decision: it is audited and requires a reason.
      const reason = window.prompt(t('validationCenter.resolvePrompt', 'Reason for resolving this finding (recorded in the audit trail):'));
      if (!reason || !reason.trim()) return;
      await api.put(`/validation/resolve/${id}`, null, { params: { reason: reason.trim() } });
      setAnomalies(prev => prev.filter(a => a.id !== id));
    } catch (err) {
      alert(t('validationCenter.resolveFailed', 'Failed to resolve finding.'));
    }
  };

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 text-amber-600" />
            {t('validationCenter.title', 'Validation & Discrepancy Anomaly Center')}
          </h2>
          <p className="text-xs text-slate-500 mt-1">
            {t('validationCenter.subtitle', 'Automated multi-tier validation flags: Cross-Database mismatches, location hierarchy errors & duplicate records.')}
          </p>
        </div>

        <button
          onClick={fetchAnomalies}
          className="p-2 text-slate-500 hover:text-slate-900 border border-slate-200 rounded-lg hover:bg-slate-50"
        >
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      {/* Filter */}
      <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-xs flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-slate-400" />
          <span className="text-xs font-semibold text-slate-600">{t('validationCenter.filterBySeverity', 'Filter by Severity:')}</span>
          <select
            value={severityFilter}
            onChange={(e) => setSeverityFilter(e.target.value)}
            className="text-xs border border-slate-300 rounded-lg p-2 focus:ring-emerald-500 focus:border-emerald-500"
          >
            <option value="">{t('validationCenter.allAnomalies', 'All Anomalies')} ({anomalies.length})</option>
            <option value="error">{t('validationCenter.criticalErrors', 'Critical Errors')}</option>
            <option value="warning">{t('validationCenter.warnings', 'Warnings')}</option>
          </select>
        </div>
      </div>

      {/* Anomalies List */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
        {loading ? (
          <div className="py-16 text-center text-slate-500 text-xs">
            <RefreshCw className="w-6 h-6 animate-spin mx-auto text-emerald-700 mb-2" />
            {t('validationCenter.loading', 'Loading Validation Anomalies...')}
          </div>
        ) : anomalies.length === 0 ? (
          <div className="py-16 text-center text-slate-400 text-xs">
            {t('validationCenter.noAnomalies', 'No unresolved validation anomalies found.')}
          </div>
        ) : (
          <div className="divide-y divide-slate-100">
            {anomalies.map((a) => (
              <div key={a.id} className="p-4 hover:bg-slate-50 transition-colors flex flex-col md:flex-row md:items-center justify-between gap-4 text-xs">
                <div className="space-y-1">
                  <div className="flex items-center gap-2 font-bold text-slate-900">
                    <span className={`px-2 py-0.5 rounded text-[10px] uppercase font-bold border ${
                      a.severity === 'error' ? 'bg-red-50 text-red-700 border-red-200' : 'bg-amber-50 text-amber-700 border-amber-200'
                    }`}>
                      {a.severity}
                    </span>
                    <span className="font-mono text-xs">{a.rule_name}</span>
                    <span className="text-slate-400 font-normal">&bull; {t('dashboard.docNumberPrefix', 'Doc #')}{a.document_id}</span>
                  </div>

                  <p className="text-slate-700 leading-relaxed">{a.message}</p>

                  {(a.expected_value || a.actual_value) && (
                    <div className="flex items-center gap-4 text-[11px] text-slate-500 pt-1 font-mono">
                      <span>{t('validationCenter.expected', 'Expected')}: <b className="text-slate-800">{a.expected_value}</b></span>
                      <span>{t('validationCenter.extracted', 'Extracted')}: <b className="text-red-700">{a.actual_value}</b></span>
                    </div>
                  )}
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  <Link
                    to={`/verification/${a.document_id}`}
                    className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg bg-emerald-700 hover:bg-emerald-800 text-white font-bold text-xs shadow-xs"
                  >
                    <Eye className="w-3.5 h-3.5" /> {t('dashboard.resolveInWorkspace', 'Resolve in Workspace')}
                  </Link>
                  <button
                    onClick={() => handleResolve(a.id)}
                    className="px-3 py-1.5 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-100 font-semibold"
                  >
                    {t('validationCenter.dismiss', 'Dismiss')}
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
