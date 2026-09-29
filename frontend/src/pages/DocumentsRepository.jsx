import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { FileText, Search, Filter, Trash2, Eye, RefreshCw, UploadCloud, Download } from 'lucide-react';
import api from '../services/api';
import { StatusBadge, ConfidenceBadge } from '../components/common/Badge';
import { useLanguage } from '../context/LanguageContext';

export const DocumentsRepository = () => {
  const { t } = useLanguage();
  const [docs, setDocs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');

  useEffect(() => {
    fetchDocuments();
  }, [statusFilter]);

  const fetchDocuments = async () => {
    setLoading(true);
    try {
      const url = statusFilter ? `/documents/?status=${statusFilter}` : '/documents/';
      const res = await api.get(url);
      setDocs(res.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm(`${t('documentsRepository.confirmDelete', 'Are you sure you want to delete document')} #${id}?`)) return;
    try {
      await api.delete(`/documents/${id}`);
      setDocs(prev => prev.filter(d => d.id !== id));
    } catch (err) {
      alert(t('documentsRepository.deleteFailed', 'Failed to delete document.'));
    }
  };

  const filteredDocs = docs.filter(d => {
    if (!search) return true;
    const q = search.toLowerCase();
    return (
      d.file_name.toLowerCase().includes(q) ||
      d.village.toLowerCase().includes(q) ||
      d.district.toLowerCase().includes(q)
    );
  });

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
            <FileText className="w-5 h-5 text-emerald-700" />
            {t('documentsRepository.title', 'Land Records Document Repository')}
          </h2>
          <p className="text-xs text-slate-500 mt-1">
            {t('documentsRepository.subtitle', 'Historical scanned revenue registers, cadastral maps, Khataunis and mutation fards.')}
          </p>
        </div>

        <Link
          to="/upload"
          className="inline-flex items-center gap-2 px-4 py-2 text-xs font-bold text-white bg-emerald-700 hover:bg-emerald-800 rounded-lg shadow-xs transition-colors"
        >
          <UploadCloud className="w-4 h-4" /> {t('documentsRepository.uploadDocument', 'Upload Document')}
        </Link>
      </div>

      {/* Filter and Search */}
      <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-xs flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="relative w-full sm:w-80">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
          <input
            type="text"
            placeholder={t('documentsRepository.searchPlaceholder', 'Search by file name or village...')}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-emerald-500 focus:border-emerald-500"
          />
        </div>

        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-slate-400" />
          <span className="text-xs font-semibold text-slate-600">{t('common.status', 'Status')}:</span>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="text-xs border border-slate-300 rounded-lg p-2 focus:ring-emerald-500 focus:border-emerald-500"
          >
            <option value="">{t('documentsRepository.allDocuments', 'All Documents')} ({docs.length})</option>
            <option value="verified">{t('badge.verified', 'Verified')}</option>
            <option value="verification_pending">{t('badge.verificationPending', 'Verification Pending')}</option>
            <option value="processed">{t('documentsRepository.processed', 'Processed')}</option>
            <option value="failed">{t('documentsRepository.failedDiscrepancy', 'Failed / Discrepancy')}</option>
          </select>
        </div>
      </div>

      {/* Documents Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
        {loading ? (
          <div className="py-16 text-center text-slate-500 text-xs">
            <RefreshCw className="w-6 h-6 animate-spin mx-auto text-emerald-700 mb-2" />
            {t('documentsRepository.loading', 'Loading Documents Repository...')}
          </div>
        ) : filteredDocs.length === 0 ? (
          <div className="py-16 text-center text-slate-400 text-xs">
            {t('documentsRepository.noResults', 'No documents found matching search.')}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-slate-600 uppercase text-[10px] font-bold border-b border-slate-200">
                <tr>
                  <th className="py-3 px-4">{t('documentsRepository.tableFile', 'Document File')}</th>
                  <th className="py-3 px-4">{t('documentsRepository.tableFormatYear', 'Format & Year')}</th>
                  <th className="py-3 px-4">{t('dashboard.tableLocation', 'Location')}</th>
                  <th className="py-3 px-4">{t('documentsRepository.tableOcrConfidence', 'OCR Confidence')}</th>
                  <th className="py-3 px-4">{t('common.status', 'Status')}</th>
                  <th className="py-3 px-4">{t('documentsRepository.tableUploadedDate', 'Uploaded Date')}</th>
                  <th className="py-3 px-4 text-right">{t('documentsRepository.tableActions', 'Actions')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filteredDocs.map((d) => (
                  <tr key={d.id} className="hover:bg-slate-50/80 transition-colors">
                    <td className="py-3.5 px-4 font-semibold text-slate-900">
                      <div>{d.file_name}</div>
                      <div className="text-[10px] text-slate-400 font-mono">{(d.file_size / 1024).toFixed(1)} KB &bull; {d.language.toUpperCase()}</div>
                    </td>
                    <td className="py-3.5 px-4 uppercase text-[11px] font-mono text-slate-600">
                      {d.document_type.replace('_', ' ')} ({d.document_year})
                    </td>
                    <td className="py-3.5 px-4 text-slate-700">
                      <div>{d.village}</div>
                      <div className="text-[10px] text-slate-400">{d.tehsil}, {d.district}</div>
                    </td>
                    <td className="py-3.5 px-4">
                      <ConfidenceBadge confidence={d.extraction_confidence || d.ocr_confidence} />
                    </td>
                    <td className="py-3.5 px-4">
                      <StatusBadge status={d.status} />
                    </td>
                    <td className="py-3.5 px-4 text-slate-500 font-mono text-[11px]">
                      {new Date(d.created_at).toLocaleDateString()}
                    </td>
                    <td className="py-3.5 px-4 text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        <Link
                          to={`/verification/${d.id}`}
                          className="p-1.5 rounded-lg text-slate-600 hover:text-emerald-700 hover:bg-emerald-50 transition-colors"
                          title={t('documentsRepository.openWorkspace', 'Open Verification Workspace')}
                        >
                          <Eye className="w-4 h-4" />
                        </Link>
                        <button
                          onClick={() => handleDelete(d.id)}
                          className="p-1.5 rounded-lg text-slate-400 hover:text-rose-700 hover:bg-rose-50 transition-colors"
                          title={t('documentsRepository.deleteDocument', 'Delete Document')}
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
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
