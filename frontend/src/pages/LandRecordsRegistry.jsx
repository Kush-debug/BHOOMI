import React, { useState, useEffect } from 'react';
import {
  Database,
  Search,
  Filter,
  Download,
  Eye,
  FileText,
  CheckCircle2,
  Clock,
  MapPin,
  RefreshCw,
  ExternalLink
} from 'lucide-react';
import api from '../services/api';
import { StatusBadge } from '../components/common/Badge';
import { Modal } from '../components/common/Modal';
import { useAuth } from '../context/AuthContext';
import { useLanguage } from '../context/LanguageContext';

export const LandRecordsRegistry = () => {
  const { user } = useAuth();
  const { t } = useLanguage();
  const isViewer = user?.role === 'viewer';
  const [records, setRecords] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [stateFilter, setStateFilter] = useState('');
  const [selectedRecord, setSelectedRecord] = useState(null);
  const [recordHistory, setRecordHistory] = useState(null);
  const [modalOpen, setModalOpen] = useState(false);

  useEffect(() => {
    fetchRecords();
  }, [stateFilter]);

  const fetchRecords = async () => {
    setLoading(true);
    try {
      const url = stateFilter ? `/records/?state=${encodeURIComponent(stateFilter)}` : '/records/';
      const res = await api.get(url);
      setRecords(res.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleInspect = async (rec) => {
    setSelectedRecord(rec);
    setModalOpen(true);
    try {
      const histRes = await api.get(`/records/${rec.id}/history`);
      setRecordHistory(histRes.data);
    } catch (err) {
      setRecordHistory(null);
    }
  };

  const filteredRecords = records.filter(r => {
    if (!search) return true;
    const q = search.toLowerCase();
    return (
      r.owner_name?.toLowerCase().includes(q) ||
      r.khasra_number?.toLowerCase().includes(q) ||
      r.khata_number?.toLowerCase().includes(q) ||
      r.village?.toLowerCase().includes(q) ||
      r.district?.toLowerCase().includes(q)
    );
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
            <Database className="w-5 h-5 text-emerald-700" />
            {t('nav.registry', 'Verified Authoritative Land Records Registry')}
          </h2>
          <p className="text-xs text-slate-500 mt-1">
            {t('landRegistry.subtitle', 'Official government repository of digitized, AI-extracted, and officer-verified cadastral parcels.')}
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          {/* Bulk export is CAN_EXPORT_REGISTRY = SENIOR_ROLES server-side
              (backend/app/auth/rbac.py) - the viewer role would only get a
              raw 403 from this link since it isn't routed through the
              axios error handling api.js provides. Hidden rather than
              shown-then-failing. */}
          {!isViewer && (
          <a
            href="/api/v1/records/export/csv"
            download
            className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-bold text-slate-700 bg-white border border-slate-200 hover:bg-slate-50 rounded-lg shadow-2xs transition-colors"
          >
            <Download className="w-4 h-4 text-slate-500" />
            {t('landRegistry.exportRegistry', 'Export Registry (CSV)')}
          </a>
          )}
          <button
            onClick={fetchRecords}
            className="p-2 text-slate-500 hover:text-slate-900 border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-xs flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="relative w-full sm:w-96">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
          <input
            type="text"
            placeholder={t('landRegistry.searchPlaceholder', 'Search by Khasra No, Khata No, Owner Name, Village...')}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-emerald-500 focus:border-emerald-500"
          />
        </div>

        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-slate-400" />
          <span className="text-xs font-semibold text-slate-600">{t('landRegistry.state', 'State')}:</span>
          <select
            value={stateFilter}
            onChange={(e) => setStateFilter(e.target.value)}
            className="text-xs border border-slate-300 rounded-lg p-2 focus:ring-emerald-500 focus:border-emerald-500"
          >
            <option value="">{t('landRegistry.allStates', 'All States')} ({records.length})</option>
            <option value="Uttar Pradesh">Uttar Pradesh</option>
            <option value="Madhya Pradesh">Madhya Pradesh</option>
            <option value="Bihar">Bihar</option>
            <option value="Maharashtra">Maharashtra</option>
            <option value="Rajasthan">Rajasthan</option>
          </select>
        </div>
      </div>

      {/* Land Records Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
        {loading ? (
          <div className="py-16 text-center text-slate-500 text-xs">
            <RefreshCw className="w-6 h-6 animate-spin mx-auto text-emerald-700 mb-2" />
            {t('landRegistry.loading', 'Loading Master Land Registry...')}
          </div>
        ) : filteredRecords.length === 0 ? (
          <div className="py-16 text-center text-slate-400 text-xs">
            {t('landRegistry.noResults', 'No land records found matching search query.')}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-slate-600 uppercase text-[10px] font-bold border-b border-slate-200">
                <tr>
                  <th className="py-3 px-4">{t('landRegistry.tableKhasra', 'Khasra / Gata No.')}</th>
                  <th className="py-3 px-4">{t('landRegistry.tableKhata', 'Khata No.')}</th>
                  <th className="py-3 px-4">{t('gisMap.landholder', 'Landholder (Owner Name)')}</th>
                  <th className="py-3 px-4">{t('landRegistry.tableFatherHusband', 'Father / Husband')}</th>
                  <th className="py-3 px-4">{t('landRegistry.tableLocation', 'Location (Village, Tehsil)')}</th>
                  <th className="py-3 px-4">{t('landRegistry.tableArea', 'Area (Extent)')}</th>
                  <th className="py-3 px-4">{t('landRegistry.tableClassification', 'Classification')}</th>
                  <th className="py-3 px-4">{t('common.status', 'Status')}</th>
                  <th className="py-3 px-4 text-right">{t('landRegistry.tableDetails', 'Details')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filteredRecords.map((r) => (
                  <tr key={r.id} className="hover:bg-slate-50/80 transition-colors">
                    <td className="py-3.5 px-4 font-mono font-bold text-emerald-800 text-xs">
                      {r.khasra_number}
                    </td>
                    <td className="py-3.5 px-4 font-mono text-slate-700">
                      {r.khata_number}
                    </td>
                    <td className="py-3.5 px-4 font-bold text-slate-900">
                      {r.owner_name}
                    </td>
                    <td className="py-3.5 px-4 text-slate-600">
                      {r.father_name || '—'}
                    </td>
                    <td className="py-3.5 px-4 text-slate-700">
                      <div>{r.village}</div>
                      <div className="text-[10px] text-slate-400">{r.tehsil}, {r.district}</div>
                    </td>
                    <td className="py-3.5 px-4 font-semibold text-slate-900">
                      {r.area} {r.area_unit}
                    </td>
                    <td className="py-3.5 px-4 text-slate-600">
                      <span className="bg-slate-100 text-slate-700 px-2 py-0.5 rounded text-[11px]">
                        {r.land_classification}
                      </span>
                    </td>
                    <td className="py-3.5 px-4">
                      <StatusBadge status={r.verification_status} />
                    </td>
                    <td className="py-3.5 px-4 text-right">
                      <button
                        onClick={() => handleInspect(r)}
                        className="p-1.5 rounded-lg text-slate-500 hover:text-emerald-800 hover:bg-emerald-50 transition-colors"
                        title={t('landRegistry.viewDetails', 'View Record Details & History')}
                      >
                        <Eye className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Record Inspector Modal */}
      {selectedRecord && (
        <Modal
          isOpen={modalOpen}
          onClose={() => setModalOpen(false)}
          title={`${t('landRegistry.modalTitlePrefix', 'Land Record: Khasra')} ${selectedRecord.khasra_number} (${selectedRecord.village})`}
        >
          <div className="space-y-5 text-xs">
            {/* Grid Attributes */}
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 bg-slate-50 p-4 rounded-xl border border-slate-200">
              <div>
                <span className="text-slate-400 block text-[10px] uppercase font-bold">{t('landRegistry.ownerName', 'Owner Name')}</span>
                <span className="font-bold text-slate-900 text-sm">{selectedRecord.owner_name}</span>
              </div>
              <div>
                <span className="text-slate-400 block text-[10px] uppercase font-bold">{t('landRegistry.tableFatherHusband', 'Father / Husband')}</span>
                <span className="font-semibold text-slate-800">{selectedRecord.father_name || '—'}</span>
              </div>
              <div>
                <span className="text-slate-400 block text-[10px] uppercase font-bold">{t('landRegistry.khasraNumber', 'Khasra Number')}</span>
                <span className="font-mono font-bold text-emerald-700 text-sm">{selectedRecord.khasra_number}</span>
              </div>
              <div>
                <span className="text-slate-400 block text-[10px] uppercase font-bold">{t('gisMap.khataNumber', 'Khata Number')}</span>
                <span className="font-mono font-semibold text-slate-800">{selectedRecord.khata_number}</span>
              </div>
              <div>
                <span className="text-slate-400 block text-[10px] uppercase font-bold">{t('landRegistry.totalArea', 'Total Area')}</span>
                <span className="font-bold text-slate-900">{selectedRecord.area} {selectedRecord.area_unit}</span>
              </div>
              <div>
                <span className="text-slate-400 block text-[10px] uppercase font-bold">{t('landRegistry.landCategory', 'Land Category')}</span>
                <span className="font-semibold text-slate-800">{selectedRecord.land_classification}</span>
              </div>
              <div>
                <span className="text-slate-400 block text-[10px] uppercase font-bold">{t('landRegistry.villageTehsil', 'Village & Tehsil')}</span>
                <span className="text-slate-800">{selectedRecord.village}, {selectedRecord.tehsil}</span>
              </div>
              <div>
                <span className="text-slate-400 block text-[10px] uppercase font-bold">{t('landRegistry.districtState', 'District & State')}</span>
                <span className="text-slate-800">{selectedRecord.district}, {selectedRecord.state}</span>
              </div>
              <div>
                <span className="text-slate-400 block text-[10px] uppercase font-bold">{t('landRegistry.verificationStatus', 'Verification Status')}</span>
                <StatusBadge status={selectedRecord.verification_status} />
              </div>
            </div>

            {/* Mutation & Registration Info */}
            <div className="bg-white p-4 rounded-xl border border-slate-200 space-y-2">
              <h4 className="font-bold text-slate-900 uppercase text-[11px] tracking-wider border-b border-slate-100 pb-1">
                {t('landRegistry.mutationTrail', 'Mutation & Legal Registration Trail')}
              </h4>
              <div className="grid grid-cols-2 gap-2 text-[11px]">
                <div>
                  <span className="text-slate-500">{t('landRegistry.mutationOrderNo', 'Mutation Order No')}:</span>
                  <span className="ml-1 font-mono font-semibold text-slate-800">
                    {selectedRecord.mutation_number || t('landRegistry.notApplicable', 'N/A')}
                  </span>
                </div>
                <div>
                  <span className="text-slate-500">{t('landRegistry.mutationType', 'Mutation Type')}:</span>
                  <span className="ml-1 font-semibold text-slate-800">
                    {selectedRecord.mutation_type || t('landRegistry.inheritanceSuccession', 'Inheritance / Succession')}
                  </span>
                </div>
                <div>
                  <span className="text-slate-500">{t('landRegistry.registrationDeedNo', 'Registration Deed No')}:</span>
                  <span className="ml-1 font-mono font-semibold text-slate-800">
                    {selectedRecord.registration_number || 'UP-REG-2023-7819'}
                  </span>
                </div>
                <div>
                  <span className="text-slate-500">{t('landRegistry.registrationOffice', 'Registration Office')}:</span>
                  <span className="ml-1 font-semibold text-slate-800">
                    {selectedRecord.registration_office || selectedRecord.tehsil}
                  </span>
                </div>
              </div>
            </div>

            {/* Verification Timeline */}
            {recordHistory && recordHistory.timeline && recordHistory.timeline.length > 0 && (
              <div className="space-y-2">
                <h4 className="font-bold text-slate-900 uppercase text-[11px] tracking-wider">
                  {t('landRegistry.auditHistory', 'Audit & Verification History')}
                </h4>
                <div className="space-y-1.5">
                  {recordHistory.timeline.map((item) => (
                    <div key={item.id} className="p-2.5 rounded-lg bg-slate-50 border border-slate-200 flex items-start justify-between">
                      <div>
                        <span className="font-bold capitalize text-slate-800">{item.action.replace('_', ' ')}</span>
                        {item.notes && <p className="text-[11px] text-slate-600 mt-0.5">{item.notes}</p>}
                      </div>
                      <span className="text-[10px] text-slate-400 font-mono">
                        {new Date(item.created_at).toLocaleString()}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </Modal>
      )}
    </div>
  );
};
