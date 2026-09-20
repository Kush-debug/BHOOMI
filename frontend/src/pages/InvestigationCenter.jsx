import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { RefreshCw, Radar, Filter } from 'lucide-react';
import api from '../services/api';
import { SeverityBadge, CaseStatusBadge } from '../components/common/Badge';
import { useLanguage } from '../context/LanguageContext';

/**
 * The prioritised investigation queue (BHUMI_FORENSICS_SPEC.md §7 -
 * "Investigation Center: prioritised queue"). GET /investigation-cases
 * already returns cases ordered by priority_score server-side
 * (investigation_cases.py); this screen is that list plus filters. Acting
 * on a case (assign/comment/resolve) happens on the parcel it belongs to -
 * see InvestigationPanel.jsx on ParcelIntelligence - so this stays a queue,
 * not a second place with the same write actions.
 *
 * `GET /investigation-cases` returns `parcel_id` but not the parcel's
 * identity (khasra/village) - `_case_dict` only attaches that when called
 * with a parcel, which the list endpoint doesn't do. Rather than add an
 * N+1 concern to the backend response shape without being asked, this
 * screen resolves each unique parcel_id in the current page with its own
 * GET /parcels/{id} call. At hackathon/pilot queue sizes (tens of open
 * cases) that's a handful of parallel requests; if this queue grows into
 * the hundreds, the real fix is a batch parcel-lookup endpoint, not more
 * client-side fan-out.
 */
export const InvestigationCenter = () => {
  const { t } = useLanguage();
  const navigate = useNavigate();
  const [cases, setCases] = useState([]);
  const [parcelsById, setParcelsById] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [statusFilter, setStatusFilter] = useState('');
  const [bandFilter, setBandFilter] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = {};
      if (statusFilter) params.status = statusFilter;
      if (bandFilter) params.band = bandFilter;
      const res = await api.get('/investigation-cases', { params });
      const rows = res.data.cases || [];
      setCases(rows);

      const uniqueParcelIds = [...new Set(rows.map((c) => c.parcel_id))];
      const fetched = await Promise.all(
        uniqueParcelIds.map((pid) =>
          api
            .get(`/parcels/${pid}`)
            .then((r) => [pid, r.data.parcel])
            .catch(() => [pid, null])
        )
      );
      setParcelsById(Object.fromEntries(fetched));
    } catch (err) {
      setError(err.response?.data?.detail || t('investigationCenter.loadError', 'Could not load the investigation queue.'));
    } finally {
      setLoading(false);
    }
  }, [statusFilter, bandFilter, t]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
            <Radar className="w-5 h-5 text-emerald-700" />
            {t('nav.investigations', 'Investigation Center')}
          </h2>
          <p className="text-xs text-slate-500 mt-1">
            {t('investigationCenter.subtitle', "Parcels with findings requiring attention, ranked by computed priority - see each case's breakdown on its parcel page.")}
          </p>
        </div>
        <button
          onClick={load}
          className="p-2 text-slate-500 hover:text-slate-900 border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors self-start"
        >
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 p-4 flex items-center gap-3 flex-wrap">
        <Filter className="w-4 h-4 text-slate-400" />
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="text-xs border border-slate-300 rounded-lg p-2 font-semibold"
        >
          <option value="">{t('investigationCenter.allStatuses', 'All statuses')}</option>
          <option value="OPEN">{t('investigationCenter.statusOpen', 'Open')}</option>
          <option value="IN_PROGRESS">{t('investigationCenter.statusInProgress', 'In progress')}</option>
          <option value="CLOSED">{t('investigationCenter.statusClosed', 'Closed')}</option>
        </select>
        <select
          value={bandFilter}
          onChange={(e) => setBandFilter(e.target.value)}
          className="text-xs border border-slate-300 rounded-lg p-2 font-semibold"
        >
          <option value="">{t('investigationCenter.allPriorityBands', 'All priority bands')}</option>
          <option value="CRITICAL">{t('investigationCenter.priorityCritical', 'Critical')}</option>
          <option value="HIGH">{t('investigationCenter.priorityHigh', 'High')}</option>
          <option value="MEDIUM">{t('investigationCenter.priorityMedium', 'Medium')}</option>
          <option value="LOW">{t('investigationCenter.priorityLow', 'Low')}</option>
        </select>
      </div>

      {loading && (
        <div className="py-16 text-center text-slate-500 text-xs">
          <RefreshCw className="w-6 h-6 animate-spin mx-auto text-emerald-700 mb-2" />
          {t('investigationCenter.loadingQueue', 'Loading prioritised queue...')}
        </div>
      )}

      {!loading && error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-xs text-red-700">{error}</div>
      )}

      {!loading && !error && cases.length === 0 && (
        <div className="p-8 text-center text-xs text-slate-500 bg-white rounded-xl border border-slate-200">
          {t('investigationCenter.noCases', 'No investigation cases match this filter.')}
        </div>
      )}

      {!loading && !error && cases.length > 0 && (
        <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-slate-600 uppercase text-[10px] font-bold border-b border-slate-200">
                <tr>
                  <th className="py-3 px-4">{t('investigationCenter.tablePriority', 'Priority')}</th>
                  <th className="py-3 px-4">{t('investigationCenter.tableParcel', 'Parcel')}</th>
                  <th className="py-3 px-4">{t('investigationCenter.tableFindings', 'Findings')}</th>
                  <th className="py-3 px-4">{t('common.status', 'Status')}</th>
                  <th className="py-3 px-4">{t('investigationCenter.tableAssigned', 'Assigned')}</th>
                  <th className="py-3 px-4">{t('investigationCenter.tableSlaDue', 'SLA due')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {cases.map((c) => {
                  const p = parcelsById[c.parcel_id];
                  return (
                    <tr
                      key={c.id}
                      onClick={() => navigate(`/parcels/${c.parcel_id}`)}
                      className="hover:bg-slate-50/80 transition-colors cursor-pointer"
                    >
                      <td className="py-3.5 px-4">
                        <div className="flex items-center gap-2">
                          <SeverityBadge severity={c.priority_band} />
                          <span className="font-mono text-slate-400">
                            {c.priority_score === null || c.priority_score === undefined
                              ? t('common.notApplicable', 'n/a')
                              : Math.round(c.priority_score * 100)}
                          </span>
                        </div>
                      </td>
                      <td className="py-3.5 px-4">
                        {p ? (
                          <>
                            <div className="font-mono font-bold text-emerald-800">{p.khasra_number || `#${c.parcel_id}`}</div>
                            <div className="text-[10px] text-slate-400">{p.village}, {p.tehsil}</div>
                          </>
                        ) : (
                          <span className="text-slate-400">{t('investigationCenter.parcelHash', 'Parcel')} #{c.parcel_id}</span>
                        )}
                      </td>
                      <td className="py-3.5 px-4 font-mono text-slate-600">{c.finding_ids?.length || 0}</td>
                      <td className="py-3.5 px-4"><CaseStatusBadge status={c.status} /></td>
                      <td className="py-3.5 px-4 text-slate-600">
                        {c.assigned_to ? `${t('investigationCenter.officerHash', 'officer')} #${c.assigned_to}` : <span className="text-slate-400">{t('investigationCenter.unassigned', 'Unassigned')}</span>}
                      </td>
                      <td className="py-3.5 px-4 text-slate-500 font-mono">
                        {c.sla_due_at ? new Date(c.sla_due_at).toLocaleDateString() : '—'}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};
