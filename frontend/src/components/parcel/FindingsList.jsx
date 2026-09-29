import React, { useState } from 'react';
import { AlertTriangle, GitCompare, FileWarning, HelpCircle, Check, X as XIcon } from 'lucide-react';
import api from '../../services/api';
import { SeverityBadge, FindingStatusBadge } from '../common/Badge';
import { useLanguage } from '../../context/LanguageContext';

const KIND_META = {
  CONTRADICTION: {
    icon: GitCompare,
    emptyKey: 'findingsList.emptyContradiction',
    emptyEn: 'No contradictions detected across this parcel\'s documents. Independent sources currently agree.'
  },
  EVIDENCE_GAP: {
    icon: FileWarning,
    emptyKey: 'findingsList.emptyGap',
    emptyEn: 'No unexplained changes. Every material transition on this parcel is backed by a matching record.'
  }
};

const ResolveForm = ({ finding, onDone }) => {
  const { t } = useLanguage();
  const [status, setStatus] = useState('IN_REVIEW');
  const [note, setNote] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  const needsNote = status === 'RESOLVED' || status === 'DISMISSED';

  const submit = async () => {
    if (needsNote && !note.trim()) {
      setError(t('findingsList.reasonRequired', 'A reason is required to resolve or dismiss a finding.'));
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const res = await api.post(`/findings/${finding.id}/resolve`, {
        resolution_status: status,
        resolution_note: note || undefined
      });
      onDone(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || t('findingsList.couldNotResolve', 'Could not resolve this finding.'));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="mt-2 p-3 bg-white border border-slate-200 rounded-lg space-y-2">
      <div className="flex items-center gap-2">
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          className="text-xs border border-slate-300 rounded-lg p-1.5 font-semibold"
        >
          <option value="IN_REVIEW">{t('findingsList.markInReview', 'Mark in review')}</option>
          <option value="RESOLVED">{t('common.resolve', 'Resolve')}</option>
          <option value="DISMISSED">{t('validationCenter.dismiss', 'Dismiss')}</option>
        </select>
      </div>
      {needsNote && (
        <textarea
          rows={2}
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder={t('findingsList.notePlaceholder', 'Why is this being resolved or dismissed? (required, kept on the audit trail)')}
          className="w-full text-xs p-2 border border-slate-300 rounded-lg focus:ring-emerald-500 focus:border-emerald-500"
        />
      )}
      {error && <div className="text-[11px] text-red-600">{error}</div>}
      <div className="flex items-center gap-2">
        <button
          onClick={submit}
          disabled={submitting}
          className="inline-flex items-center gap-1 px-3 py-1.5 bg-emerald-700 hover:bg-emerald-800 text-white rounded-lg font-bold text-[11px] disabled:opacity-50"
        >
          <Check className="w-3.5 h-3.5" />
          {submitting ? t('findingsList.saving', 'Saving...') : t('findingsList.submit', 'Submit')}
        </button>
      </div>
    </div>
  );
};

/**
 * Renders the Conflicts and Evidence Gaps tabs (BHUMI_FORENSICS_SPEC.md §7) -
 * one component, `kind` picks the empty-state copy, since both are just
 * `Finding` rows filtered by `finding_type` server-side (GET
 * /parcels/{id}/findings). Findings render only from their backend-rendered
 * `explanation`/`recommended_action` template output - this component never
 * composes its own wording about what a finding means, so the forbidden-word
 * discipline in Phase 5's finding templates (spec §2 rule 8) can't be
 * bypassed by the UI.
 */
export const FindingsList = ({ findings, kind, canResolve, onWhy, onFindingUpdated }) => {
  const { t } = useLanguage();
  const [resolvingId, setResolvingId] = useState(null);
  const meta = KIND_META[kind];
  const Icon = meta.icon;

  if (!findings || findings.length === 0) {
    return (
      <div className="p-8 text-center text-xs text-slate-500 bg-white rounded-xl border border-slate-200 flex flex-col items-center gap-2">
        <Icon className="w-6 h-6 text-slate-300" />
        {t(meta.emptyKey, meta.emptyEn)}
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {findings.map((f) => (
        <div key={f.id} className="bg-white rounded-xl border border-slate-200 p-4">
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-center gap-2">
              <SeverityBadge severity={f.severity} />
              <FindingStatusBadge status={f.resolution_status} />
              {f.time_range?.start && (
                <span className="text-[10px] font-mono text-slate-400">
                  {f.time_range.start}{f.time_range.end && f.time_range.end !== f.time_range.start ? `–${f.time_range.end}` : ''}
                </span>
              )}
            </div>
          </div>

          <p className="mt-2 text-xs text-slate-800">{f.explanation}</p>

          {f.recommended_action && (
            <p className="mt-1 text-[11px] text-slate-500 flex items-start gap-1.5">
              <AlertTriangle className="w-3 h-3 shrink-0 mt-0.5 text-amber-500" />
              {t('findingsList.recommended', 'Recommended')}: {f.recommended_action}
            </p>
          )}

          {onWhy && f.source_claim_ids?.length > 0 && (
            <div className="mt-2 flex items-center gap-2 flex-wrap">
              <span className="text-[10px] text-slate-400">{t('findingsList.sourceClaims', 'Source claims')}:</span>
              {f.source_claim_ids.map((cid) => (
                <button
                  key={cid}
                  onClick={() => onWhy(cid)}
                  className="inline-flex items-center gap-0.5 text-[10px] font-bold text-emerald-700 hover:underline"
                >
                  <HelpCircle className="w-3 h-3" />
                  #{cid}
                </button>
              ))}
            </div>
          )}

          {canResolve && f.resolution_status !== 'RESOLVED' && f.resolution_status !== 'DISMISSED' && (
            resolvingId === f.id ? (
              <ResolveForm
                finding={f}
                onDone={(updated) => {
                  setResolvingId(null);
                  onFindingUpdated(updated);
                }}
              />
            ) : (
              <button
                onClick={() => setResolvingId(f.id)}
                className="mt-2 inline-flex items-center gap-1 px-2.5 py-1 border border-slate-300 text-slate-600 hover:bg-slate-50 rounded-lg text-[11px] font-bold"
              >
                {t('findingsList.resolveEllipsis', 'Resolve...')}
              </button>
            )
          )}

          {(f.resolution_status === 'RESOLVED' || f.resolution_status === 'DISMISSED') && f.resolution_note && (
            <div className="mt-2 p-2 bg-slate-50 rounded-lg text-[11px] text-slate-600 flex items-start gap-1.5">
              <XIcon className="w-3 h-3 shrink-0 mt-0.5 text-slate-400" />
              {f.resolution_note}
            </div>
          )}
        </div>
      ))}
    </div>
  );
};
