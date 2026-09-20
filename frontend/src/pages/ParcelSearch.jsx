import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, MapPin, FileText, RefreshCw, Compass } from 'lucide-react';
import api from '../services/api';
import { StatusBadge } from '../components/common/Badge';
import { useLanguage } from '../context/LanguageContext';

/**
 * Entry point into Parcel Intelligence (BHUMI_FORENSICS_SPEC.md §7). Search
 * is GET /parcels?q= (Phase 3) - matches khasra/khata number in any
 * separator style, or a village name. Not the same list as "Land Registry":
 * that screen lists verified LandRecord rows one per document; this finds
 * the durable Parcel a khasra number resolves to, which is what has a
 * history to reconstruct.
 */
export const ParcelSearch = () => {
  const { t } = useLanguage();
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [searched, setSearched] = useState(false);

  const runSearch = async (e) => {
    e?.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    setSearched(true);
    try {
      const res = await api.get('/parcels', { params: { q: query.trim() } });
      setResults(res.data.parcels || []);
    } catch (err) {
      setError(err.response?.data?.detail || t('parcelSearch.searchFailed', 'Search failed.'));
      setResults(null);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-xs">
        <h2 className="text-xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
          <Compass className="w-5 h-5 text-emerald-700" />
          {t('nav.parcels', 'Parcel Intelligence')}
        </h2>
        <p className="text-xs text-slate-500 mt-1">
          {t('parcelSearch.subtitle', 'Find a parcel by Khasra number, Khata number, or village to open its full reconstructed history - Land Time Machine, evidence graph, conflicts, and evidence gaps.')}
        </p>

        <form onSubmit={runSearch} className="mt-4 flex items-center gap-2">
          <div className="relative flex-1">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
            <input
              type="text"
              autoFocus
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={t('parcelSearch.searchPlaceholder', 'e.g. 441/9, or Bilhaur Dehat')}
              className="w-full pl-9 pr-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-emerald-500 focus:border-emerald-500"
            />
          </div>
          <button
            type="submit"
            disabled={loading || !query.trim()}
            className="px-4 py-2 bg-emerald-700 hover:bg-emerald-800 text-white rounded-lg font-bold text-xs disabled:opacity-50"
          >
            {t('common.search', 'Search')}
          </button>
        </form>
      </div>

      {loading && (
        <div className="py-12 text-center text-slate-500 text-xs">
          <RefreshCw className="w-6 h-6 animate-spin mx-auto text-emerald-700 mb-2" />
          {t('parcelSearch.searchingParcels', 'Searching parcels...')}
        </div>
      )}

      {!loading && error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-xs text-red-700">{error}</div>
      )}

      {!loading && !error && searched && results && results.length === 0 && (
        <div className="p-8 text-center text-xs text-slate-500 bg-white rounded-xl border border-slate-200">
          {t('parcelSearch.noMatchPrefix', 'No parcel matches')} &ldquo;{query}&rdquo;. {t('parcelSearch.noMatchSuffix', 'A parcel only exists once a document naming that khasra number has been uploaded and processed.')}
        </div>
      )}

      {!loading && results && results.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {results.map((p) => (
            <button
              key={p.id}
              onClick={() => navigate(`/parcels/${p.id}`)}
              className="text-left bg-white rounded-xl border border-slate-200 p-4 hover:border-emerald-400 hover:shadow-xs transition-all"
            >
              <div className="flex items-center justify-between">
                <span className="font-mono font-bold text-emerald-800 text-sm">{p.khasra_number || '—'}</span>
                <StatusBadge status={p.status} />
              </div>
              {p.khata_number && (
                <div className="text-[11px] text-slate-400 mt-0.5">{t('parcelSearch.khata', 'Khata')} {p.khata_number}</div>
              )}
              <div className="text-[11px] text-slate-600 mt-2 flex items-center gap-1">
                <MapPin className="w-3 h-3 text-slate-400" />
                {p.village}, {p.tehsil}
              </div>
              <div className="text-[11px] text-slate-400 mt-1 flex items-center gap-1">
                <FileText className="w-3 h-3" />
                {p.document_count} {p.document_count === 1 ? t('parcelSearch.document', 'document') : t('parcelSearch.documents', 'documents')}
                {p.first_seen_year && (
                  <span>&bull; {p.first_seen_year}{p.last_seen_year && p.last_seen_year !== p.first_seen_year ? `–${p.last_seen_year}` : ''}</span>
                )}
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
};
