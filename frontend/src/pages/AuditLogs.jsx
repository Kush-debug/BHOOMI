import React, { useState, useEffect } from 'react';
import { ShieldCheck, Search, Filter, RefreshCw } from 'lucide-react';
import api from '../services/api';
import { useLanguage } from '../context/LanguageContext';

export const AuditLogs = () => {
  const { t } = useLanguage();
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');

  useEffect(() => {
    fetchLogs();
  }, []);

  const fetchLogs = async () => {
    setLoading(true);
    try {
      const res = await api.get('/audit/logs?limit=100');
      setLogs(res.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const filteredLogs = logs.filter(l => {
    if (!search) return true;
    const q = search.toLowerCase();
    return (
      l.action.toLowerCase().includes(q) ||
      JSON.stringify(l.details).toLowerCase().includes(q)
    );
  });

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
            <ShieldCheck className="w-5 h-5 text-emerald-700" />
            {t('nav.audit', 'Security & Operational Audit Trail Logs')}
          </h2>
          <p className="text-xs text-slate-500 mt-1">
            {t('auditLogs.subtitle', 'Immutable system logs recording uploads, AI extractions, field corrections, and revenue officer verifications.')}
          </p>
        </div>

        <button
          onClick={fetchLogs}
          className="p-2 text-slate-500 hover:text-slate-900 border border-slate-200 rounded-lg hover:bg-slate-50"
        >
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
        {loading ? (
          <div className="py-16 text-center text-slate-500 text-xs">
            <RefreshCw className="w-6 h-6 animate-spin mx-auto text-emerald-700 mb-2" />
            {t('auditLogs.loading', 'Loading Audit Logs...')}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-slate-600 uppercase text-[10px] font-bold border-b border-slate-200">
                <tr>
                  <th className="py-3 px-4">{t('auditLogs.timestamp', 'Timestamp (UTC)')}</th>
                  <th className="py-3 px-4">{t('auditLogs.actionEvent', 'Action Event')}</th>
                  <th className="py-3 px-4">{t('auditLogs.documentRecord', 'Document / Record')}</th>
                  <th className="py-3 px-4">{t('auditLogs.eventDetails', 'Event Details & Metadata')}</th>
                  <th className="py-3 px-4">{t('auditLogs.ipAddress', 'IP Address')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 font-mono text-[11px]">
                {filteredLogs.map((l) => (
                  <tr key={l.id} className="hover:bg-slate-50 transition-colors">
                    <td className="py-3 px-4 text-slate-500 whitespace-nowrap">
                      {new Date(l.timestamp).toLocaleString()}
                    </td>
                    <td className="py-3 px-4 font-bold text-slate-900">
                      {l.action}
                    </td>
                    <td className="py-3 px-4 text-slate-600">
                      {l.document_id ? `${t('dashboard.docNumberPrefix', 'Doc #')}${l.document_id}` : t('auditLogs.system', 'System')}
                    </td>
                    <td className="py-3 px-4 text-slate-700 max-w-md truncate font-sans text-xs">
                      {JSON.stringify(l.details)}
                    </td>
                    <td className="py-3 px-4 text-slate-400">
                      {l.ip_address}
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
