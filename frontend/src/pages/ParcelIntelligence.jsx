import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import {
  ArrowLeft,
  MapPin,
  RefreshCw,
  FileText,
  Users,
  Tags,
  HelpCircle,
  LayoutGrid,
  History,
  GitCompare,
  FileWarning,
  Briefcase
} from 'lucide-react';
import api from '../services/api';
import { useAuth } from '../context/AuthContext';
import { useLanguage } from '../context/LanguageContext';
import { StatusBadge } from '../components/common/Badge';
import { LandTimeMachine } from '../components/parcel/LandTimeMachine';
import { EvidenceDrawer } from '../components/parcel/EvidenceDrawer';
import { FindingsList } from '../components/parcel/FindingsList';
import { InvestigationPanel } from '../components/parcel/InvestigationPanel';
import { SufficiencyGauge } from '../components/parcel/SufficiencyGauge';

const TABS = [
  { key: 'current', labelKey: 'parcelIntelligence.tabCurrent', label: 'Current State', icon: LayoutGrid },
  { key: 'timeline', labelKey: 'parcelIntelligence.tabTimeline', label: 'Land Time Machine', icon: History },
  { key: 'evidence', labelKey: 'parcelIntelligence.tabEvidence', label: 'Evidence Graph', icon: FileText },
  { key: 'conflicts', labelKey: 'parcelIntelligence.tabConflicts', label: 'Conflicts', icon: GitCompare },
  { key: 'gaps', labelKey: 'parcelIntelligence.tabGaps', label: 'Evidence Gaps', icon: FileWarning },
  { key: 'investigation', labelKey: 'parcelIntelligence.tabInvestigation', label: 'Investigation', icon: Briefcase }
];

const FIELD_META = [
  { key: 'owner_name', labelKey: 'parcelIntelligence.fieldOwner', label: 'Owner' },
  { key: 'area', labelKey: 'parcelIntelligence.fieldArea', label: 'Area' },
  { key: 'classification', labelKey: 'parcelIntelligence.fieldClassification', label: 'Land classification' },
  { key: 'khata_number', labelKey: 'parcelIntelligence.fieldKhataNumber', label: 'Khata number' }
];

/**
 * The flagship screen (BHUMI_FORENSICS_SPEC.md §7 / §9 Phase 8 gate): "A
 * judge understands the product in 60 seconds." Everything on this page is
 * a real query against a parcel that actually exists - GET /parcels/{id}
 * plus its /timeline, /findings and /sufficiency siblings from Phases 4-6,
 * and the investigation-cases list from Phase 6/7. Nothing here is seeded
 * or client-computed; a demo corpus parcel and a parcel from a document a
 * judge uploads five minutes ago render through the identical code path.
 */
export const ParcelIntelligence = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const { t } = useLanguage();
  const isStaff = user?.role && user.role !== 'viewer';

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState('current');

  const [parcel, setParcel] = useState(null);
  const [snapshots, setSnapshots] = useState([]);
  const [transitions, setTransitions] = useState([]);
  const [findings, setFindings] = useState([]);
  const [sufficiency, setSufficiency] = useState(null);
  const [sufficiencyLoading, setSufficiencyLoading] = useState(true);
  const [cases, setCases] = useState([]);

  const [evidenceClaimId, setEvidenceClaimId] = useState(null);

  const loadAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [parcelRes, timelineRes, findingsRes, casesRes] = await Promise.all([
        api.get(`/parcels/${id}`),
        api.get(`/parcels/${id}/timeline`),
        api.get(`/parcels/${id}/findings`),
        api.get(`/investigation-cases`, { params: { parcel_id: id } })
      ]);
      setParcel(parcelRes.data);
      setSnapshots(timelineRes.data.snapshots || []);
      setTransitions(timelineRes.data.transitions || []);
      setFindings(findingsRes.data.findings || []);
      setCases(casesRes.data.cases || []);
    } catch (err) {
      setError(
        err.response?.status === 404
          ? t('parcelIntelligence.notFound', 'Parcel not found.')
          : err.response?.data?.detail || t('parcelIntelligence.loadError', 'Could not load this parcel.')
      );
    } finally {
      setLoading(false);
    }

    setSufficiencyLoading(true);
    try {
      const sufRes = await api.get(`/parcels/${id}/sufficiency`);
      setSufficiency(sufRes.data);
    } catch (err) {
      setSufficiency(null);
    } finally {
      setSufficiencyLoading(false);
    }
  }, [id, t]);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  const findingsById = useMemo(() => {
    const map = {};
    findings.forEach((f) => { map[f.id] = f; });
    return map;
  }, [findings]);

  const contradictions = useMemo(() => findings.filter((f) => f.finding_type === 'CONTRADICTION'), [findings]);
  const gaps = useMemo(() => findings.filter((f) => f.finding_type === 'EVIDENCE_GAP'), [findings]);
  const latestSnapshot = snapshots.length > 0 ? snapshots[snapshots.length - 1] : null;

  const openEvidence = (claimId) => setEvidenceClaimId(claimId);
  const closeEvidence = () => setEvidenceClaimId(null);

  const handleClaimCorrected = () => {
    // A correction may change the latest snapshot's supporting claims and,
    // via the Phase 7 parcel_id fix, is visible immediately - refetch rather
    // than trying to patch snapshots/claims locally.
    loadAll();
  };

  const handleFindingUpdated = (updated) => {
    setFindings((prev) => prev.map((f) => (f.id === updated.id ? updated : f)));
  };

  const handleCaseUpdated = (updated) => {
    setCases((prev) => prev.map((c) => (c.id === updated.id ? updated : c)));
  };

  if (loading) {
    return (
      <div className="py-24 text-center text-slate-500 text-xs">
        <RefreshCw className="w-8 h-8 animate-spin mx-auto text-emerald-700 mb-2" />
        {t('parcelIntelligence.reconstructing', 'Reconstructing parcel intelligence from real claims...')}
      </div>
    );
  }

  if (error || !parcel) {
    return (
      <div className="p-8 text-center text-xs text-slate-500 bg-white rounded-xl border border-slate-200">
        <p className="mb-3">{error || t('parcelIntelligence.notFound', 'Parcel not found.')}</p>
        <button
          onClick={() => navigate('/parcels')}
          className="px-3 py-1.5 border border-slate-300 rounded-lg text-slate-600 hover:bg-slate-50 font-bold"
        >
          {t('parcelIntelligence.backToSearch', 'Back to parcel search')}
        </button>
      </div>
    );
  }

  const p = parcel.parcel;

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs">
        <div className="flex flex-col lg:flex-row lg:items-start justify-between gap-4">
          <div>
            <button
              onClick={() => navigate('/parcels')}
              className="mb-2 inline-flex items-center gap-1 text-[11px] text-slate-400 hover:text-slate-700"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              {t('parcelIntelligence.parcelSearch', 'Parcel search')}
            </button>
            <h2 className="text-lg font-bold text-slate-900 tracking-tight flex items-center gap-2">
              {t('gisMap.khasraLabel', 'Khasra')} {p.khasra_number || '—'}
              {p.khata_number && <span className="text-slate-400 font-normal text-sm">/ {t('parcelSearch.khata', 'Khata')} {p.khata_number}</span>}
              <StatusBadge status={p.status} />
            </h2>
            <div className="text-[11px] text-slate-500 flex items-center gap-1.5 mt-1">
              <MapPin className="w-3.5 h-3.5" />
              {p.village}, {p.tehsil}, {p.district} ({p.state})
              <span>&bull;</span>
              <span>{p.document_count} {p.document_count === 1 ? t('parcelSearch.document', 'document') : t('parcelSearch.documents', 'documents')}</span>
              {p.first_seen_year && (
                <>
                  <span>&bull;</span>
                  <span>{p.first_seen_year}{p.last_seen_year && p.last_seen_year !== p.first_seen_year ? `–${p.last_seen_year}` : ''}</span>
                </>
              )}
            </div>
          </div>
          <div className="w-full lg:w-72 shrink-0">
            <SufficiencyGauge score={sufficiency} loading={sufficiencyLoading} />
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="bg-white rounded-xl border border-slate-200 p-1.5 flex items-center gap-1 overflow-x-auto">
        {TABS.map((tab) => {
          const Icon = tab.icon;
          const count = tab.key === 'conflicts' ? contradictions.length : tab.key === 'gaps' ? gaps.length : null;
          return (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`shrink-0 inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-bold transition-colors ${
                activeTab === tab.key ? 'bg-emerald-700 text-white' : 'text-slate-600 hover:bg-slate-50'
              }`}
            >
              <Icon className="w-3.5 h-3.5" />
              {t(tab.labelKey, tab.label)}
              {count !== null && count > 0 && (
                <span
                  className={`ml-0.5 px-1.5 rounded-full text-[10px] font-mono ${
                    activeTab === tab.key ? 'bg-white/20' : 'bg-red-100 text-red-700'
                  }`}
                >
                  {count}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Current State */}
      {activeTab === 'current' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="lg:col-span-2 space-y-4">
            <div className="bg-white rounded-xl border border-slate-200 p-5">
              <h3 className="font-bold text-slate-900 text-sm mb-3">
                {t('parcelIntelligence.currentState', 'Current state')}{latestSnapshot ? ` (${t('parcelIntelligence.asOf', 'as of')} ${latestSnapshot.as_of_year})` : ''}
              </h3>
              {!latestSnapshot ? (
                <p className="text-xs text-slate-500">{t('parcelIntelligence.noDatedClaims', 'No dated claims yet resolve to this parcel.')}</p>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                  {FIELD_META.map(({ key, labelKey, label }) => {
                    const value = key === 'area'
                      ? (latestSnapshot.area !== null && latestSnapshot.area !== undefined
                          ? `${latestSnapshot.area} ${latestSnapshot.area_unit || ''}`.trim()
                          : null)
                      : latestSnapshot[key];
                    const claimId = latestSnapshot.supporting_claim_ids?.[key];
                    return (
                      <div key={key} className="p-3 bg-slate-50 rounded-lg border border-slate-200">
                        <span className="text-[10px] font-bold uppercase text-slate-400">{t(labelKey, label)}</span>
                        <div className="mt-0.5 flex items-center">
                          <span className="font-semibold text-slate-900">{value ?? '—'}</span>
                          {claimId && (
                            <button
                              onClick={() => openEvidence(claimId)}
                              className="ml-1.5 inline-flex items-center gap-0.5 text-[10px] font-bold text-emerald-700 hover:underline"
                            >
                              <HelpCircle className="w-3 h-3" />
                              {t('parcelIntelligence.why', 'Why?')}
                            </button>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            <div className="bg-white rounded-xl border border-slate-200 p-5">
              <h3 className="font-bold text-slate-900 text-sm mb-3 flex items-center gap-1.5">
                <FileText className="w-4 h-4 text-slate-400" />
                {t('parcelIntelligence.sourceDocuments', 'Source documents')} ({parcel.documents.length})
              </h3>
              {parcel.documents.length === 0 ? (
                <p className="text-xs text-slate-500">{t('parcelIntelligence.noDocumentsLinked', 'No documents linked yet.')}</p>
              ) : (
                <ul className="space-y-1.5 text-xs">
                  {parcel.documents.map((d) => (
                    <li key={d.id} className="flex items-center justify-between border-b border-slate-50 pb-1.5 last:border-0">
                      <Link to={`/verification/${d.id}`} className="text-emerald-800 hover:underline font-medium">
                        {d.file_name}
                      </Link>
                      <span className="text-slate-400 flex items-center gap-2">
                        {d.document_year}
                        {d.source_class === 'SEED_SYNTHETIC' && (
                          <span className="text-[9px] font-bold uppercase text-purple-600">{t('parcelIntelligence.demo', 'demo')}</span>
                        )}
                        <StatusBadge status={d.status} />
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>

          <div className="space-y-4">
            <div className="bg-white rounded-xl border border-slate-200 p-5">
              <h3 className="font-bold text-slate-900 text-sm mb-3 flex items-center gap-1.5">
                <Users className="w-4 h-4 text-slate-400" />
                {t('parcelIntelligence.personsResolved', 'Persons resolved')} ({parcel.persons.length})
              </h3>
              {parcel.persons.length === 0 ? (
                <p className="text-xs text-slate-500">{t('parcelIntelligence.noPersonsResolved', 'No persons resolved yet.')}</p>
              ) : (
                <ul className="space-y-1 text-xs text-slate-700">
                  {parcel.persons.map((per) => <li key={per.id}>{per.canonical_name}</li>)}
                </ul>
              )}
            </div>

            <div className="bg-white rounded-xl border border-slate-200 p-5">
              <h3 className="font-bold text-slate-900 text-sm mb-3 flex items-center gap-1.5">
                <Tags className="w-4 h-4 text-slate-400" />
                {t('parcelIntelligence.identifierAliases', 'Identifier aliases')} ({parcel.aliases.length})
              </h3>
              {parcel.aliases.length === 0 ? (
                <p className="text-xs text-slate-500">{t('parcelIntelligence.noAliases', 'No alternate spellings recorded.')}</p>
              ) : (
                <ul className="space-y-1 text-xs text-slate-700">
                  {parcel.aliases.map((a, i) => (
                    <li key={i} className="flex items-center justify-between">
                      <span className="font-mono">{a.raw_identifier}</span>
                      <span className="text-[10px] text-slate-400">{a.match_method}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Land Time Machine */}
      {activeTab === 'timeline' && (
        <LandTimeMachine snapshots={snapshots} transitions={transitions} onWhy={openEvidence} />
      )}

      {/* Evidence Graph: every current claim on this parcel, grouped by document */}
      {activeTab === 'evidence' && (
        <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-100">
          {parcel.claims.length === 0 ? (
            <div className="p-8 text-center text-xs text-slate-500">{t('parcelIntelligence.noClaims', 'No claims resolve to this parcel yet.')}</div>
          ) : (
            parcel.claims.map((c) => (
              <div key={c.id} className="p-3.5 flex items-center justify-between gap-3 hover:bg-slate-50/60">
                <div className="min-w-0">
                  <span className="text-[10px] font-bold uppercase text-slate-400">{c.standardized_field}</span>
                  <div className="text-xs font-semibold text-slate-900 truncate">{c.field_value ?? '—'}</div>
                  <div className="text-[10px] text-slate-400">{t('parcelIntelligence.documentHash', 'document #')}{c.document_id}</div>
                </div>
                <button
                  onClick={() => openEvidence(c.id)}
                  className="shrink-0 inline-flex items-center gap-1 px-2.5 py-1.5 border border-slate-300 text-slate-600 hover:bg-slate-50 rounded-lg text-[11px] font-bold"
                >
                  <HelpCircle className="w-3.5 h-3.5" />
                  {t('parcelIntelligence.traceEvidence', 'Trace evidence')}
                </button>
              </div>
            ))
          )}
        </div>
      )}

      {/* Conflicts */}
      {activeTab === 'conflicts' && (
        <FindingsList
          findings={contradictions}
          kind="CONTRADICTION"
          canResolve={isStaff}
          onWhy={openEvidence}
          onFindingUpdated={handleFindingUpdated}
        />
      )}

      {/* Evidence Gaps */}
      {activeTab === 'gaps' && (
        <FindingsList
          findings={gaps}
          kind="EVIDENCE_GAP"
          canResolve={isStaff}
          onWhy={openEvidence}
          onFindingUpdated={handleFindingUpdated}
        />
      )}

      {/* Investigation */}
      {activeTab === 'investigation' && (
        <InvestigationPanel
          cases={cases}
          findingsById={findingsById}
          canManage={isStaff}
          currentUser={user}
          onCaseUpdated={handleCaseUpdated}
        />
      )}

      <EvidenceDrawer
        claimId={evidenceClaimId}
        isOpen={Boolean(evidenceClaimId)}
        onClose={closeEvidence}
        canCorrect={isStaff}
        onCorrected={handleClaimCorrected}
      />
    </div>
  );
};
