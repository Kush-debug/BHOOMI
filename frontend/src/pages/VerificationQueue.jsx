import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { CheckCircle2, AlertTriangle, AlertCircle, Clock, Eye, Search, Filter, RefreshCw } from 'lucide-react';
import api from '../services/api';
import { StatusBadge, ConfidenceBadge } from '../components/common/Badge';
import { useLanguage } from '../context/LanguageContext';

export const VerificationQueue = () => {
  const { t } = useLanguage();
  const [queue, setQueue] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filterType, setFilterType] = useState('all');
  const [search, setSearch] = useState('');

  useEffect(() => {
    fetchQueue();
  }, []);

  const fetchQueue = async () => {
    setLoading(true);
    try {
      const res = await api.get('/verification/queue');
      setQueue(res.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const filteredQueue = queue.filter((item) => {
    if (filterType === 'issues' && item.anomalies_count === 0) return false;
    if (filterType === 'clean' && item.anomalies_count > 0) return false;
    if (search) {
      const q = search.toLowerCase();
      return (
        item.file_name.toLowerCase().includes(q) ||
        item.village.toLowerCase().includes(q) ||
        item.district.toLowerCase().includes(q)
      );
    }
    return true;
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900 tracking-tight">
            {t('nav.verification', 'Revenue Officer Verification Queue')}
          </h2>
          <p className="text-xs text-slate-500 mt-1">
            {t('verificationQueue.subtitle', 'Human-in-the-loop validation for OCR uncertain fields, cross-database mismatches and duplicate alerts.')}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={fetchQueue}
            className="flex items-center gap-1.5 px-3 py-2 text-xs font-semibold rounded-lg border border-slate-200 hover:bg-slate-50 text-slate-700 transition-colors"
          >
            <RefreshCw className="w-4 h-4" /> {t('common.refresh', 'Refresh')}
          </button>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-xs flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-2 w-full sm:w-80">
          <div className="relative w-full">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
            <input
              type="text"
              placeholder={t('verificationQueue.searchPlaceholder', 'Search by file name, village or district...')}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-9 pr-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-emerald-500 focus:border-emerald-500"
            />
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-slate-400" />
          <span className="text-xs font-semibold text-slate-600">{t('common.filter', 'Filter')}:</span>
          <select
            value={filterType}
            onChange={(e) => setFilterType(e.target.value)}
            className="text-xs border border-slate-300 rounded-lg p-2 focus:ring-emerald-500 focus:border-emerald-500"
          >
            <option value="all">{t('verificationQueue.allPending', 'All Pending Documents')} ({queue.length})</option>
            <option value="issues">{t('verificationQueue.withIssues', 'With Validation Issues')}</option>
            <option value="clean">{t('verificationQueue.cleanHighConfidence', 'Clean / High Confidence')}</option>
          </select>
        </div>
      </div>

      {/* Queue Cards / Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
        {loading ? (
          <div className="py-16 text-center text-slate-500 text-xs">
            <RefreshCw className="w-6 h-6 animate-spin mx-auto text-emerald-700 mb-2" />
            {t('verificationQueue.loading', 'Loading Verification Queue...')}
          </div>
        ) : filteredQueue.length === 0 ? (
          <div className="py-16 text-center text-slate-400 text-xs">
            {t('verificationQueue.noResults', 'No documents currently pending verification.')}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-slate-600 uppercase text-[10px] font-bold border-b border-slate-200">
                <tr>
                  <th className="py-3 px-4">{t('verificationQueue.tableDocDetails', 'Document Details')}</th>
                  <th className="py-3 px-4">{t('dashboard.tableLocation', 'Location')}</th>
                  <th className="py-3 px-4">{t('dashboard.tableType', 'Type')}</th>
                  <th className="py-3 px-4">{t('verificationQueue.tableAccuracy', 'Extraction Accuracy')}</th>
                  <th className="py-3 px-4">{t('verificationQueue.tableValidationStatus', 'Validation Status')}</th>
                  <th className="py-3 px-4">{t('verificationQueue.tableFlaggedIssues', 'Flagged Issues')}</th>
                  <th className="py-3 px-4 text-right">{t('verificationQueue.tableWorkspaceAction', 'Workspace Action')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filteredQueue.map((item) => (
                  <tr key={item.id} className="hover:bg-slate-50/80 transition-colors">
                    <td className="py-4 px-4">
                      <div className="font-bold text-slate-900">{item.file_name}</div>
                      <div className="text-[10px] text-slate-400 font-mono">{t('verificationQueue.docIdPrefix', 'Doc ID #')}{item.id}</div>
                    </td>
                    <td className="py-4 px-4 text-slate-700">
                      <div>{item.village}</div>
                      <div className="text-[10px] text-slate-400">{item.tehsil}, {item.district}</div>
                    </td>
                    <td className="py-4 px-4 font-mono uppercase text-[11px] text-slate-600">
                      {item.document_type.replace('_', ' ')}
                    </td>
                    <td className="py-4 px-4">
                      <ConfidenceBadge confidence={item.extraction_confidence || item.ocr_confidence} />
                    </td>
                    <td className="py-4 px-4">
                      <StatusBadge status={item.validation_status} />
                    </td>
                    <td className="py-4 px-4">
                      {item.anomalies_count > 0 ? (
                        <div className="flex flex-col gap-1">
                          <span className="inline-flex items-center gap-1 text-[11px] font-bold text-red-700 bg-red-50 px-2 py-0.5 rounded border border-red-200">
                            <AlertCircle className="w-3 h-3" /> {item.anomalies_count} {t('verificationQueue.discrepancy', 'Discrepancy')}
                          </span>
                          <span className="text-[10px] text-slate-500 truncate max-w-[200px]">
                            {item.anomalies[0]?.message}
                          </span>
                        </div>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-[11px] font-medium text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                          <CheckCircle2 className="w-3 h-3" /> {t('verificationQueue.passedAllRules', 'Passed All Rules')}
                        </span>
                      )}
                    </td>
                    <td className="py-4 px-4 text-right">
                      <Link
                        to={`/verification/${item.id}`}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-700 hover:bg-emerald-800 text-white font-bold text-xs shadow-xs transition-colors"
                      >
                        <Eye className="w-3.5 h-3.5" />
                        {t('verificationQueue.openWorkspace', 'Open Workspace')} &rarr;
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
