import React, { useState } from 'react';
import { Briefcase, UserPlus, MessageSquare, CheckCircle2, Send } from 'lucide-react';
import api from '../../services/api';
import { SeverityBadge, CaseStatusBadge } from '../common/Badge';
import { useLanguage } from '../../context/LanguageContext';

const TERM_LABEL_KEYS = {
  severity: 'investigationPanel.termSeverity',
  evidence_gap: 'investigationPanel.termEvidenceGap',
  ownership_involved: 'investigationPanel.termOwnershipInvolved',
  area_magnitude: 'investigationPanel.termAreaMagnitude',
  staleness: 'investigationPanel.termStaleness'
};

const TERM_LABELS_EN = {
  severity: 'Severity',
  evidence_gap: 'Evidence gap (1 - sufficiency)',
  ownership_involved: 'Ownership involved',
  area_magnitude: 'Area magnitude',
  staleness: 'Staleness'
};

const CaseCard = ({ c, findingsById, canManage, currentUser, onCaseUpdated }) => {
  const { t } = useLanguage();
  const [commentText, setCommentText] = useState('');
  const [resolution, setResolution] = useState('');
  const [showResolve, setShowResolve] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const isClosed = c.status === 'CLOSED';
  const isAssignedToMe = currentUser && c.assigned_to === currentUser.id;

  const assignToMe = async () => {
    setBusy(true);
    setError(null);
    try {
      const res = await api.post(`/investigation-cases/${c.id}/assign`, { assigned_to: currentUser.id });
      onCaseUpdated(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || t('investigationPanel.couldNotAssign', 'Could not assign this case.'));
    } finally {
      setBusy(false);
    }
  };

  const submitComment = async () => {
    if (!commentText.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const res = await api.post(`/investigation-cases/${c.id}/comment`, { text: commentText.trim() });
      setCommentText('');
      onCaseUpdated(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || t('investigationPanel.couldNotComment', 'Could not post the comment.'));
    } finally {
      setBusy(false);
    }
  };

  const submitResolve = async () => {
    if (!resolution.trim()) {
      setError(t('investigationPanel.resolutionRequired', 'A resolution summary is required to close a case.'));
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const res = await api.post(`/investigation-cases/${c.id}/resolve`, { resolution: resolution.trim() });
      setShowResolve(false);
      onCaseUpdated(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || t('investigationPanel.couldNotResolve', 'Could not resolve this case.'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-4 space-y-3">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <Briefcase className="w-4 h-4 text-slate-400" />
          <span className="font-bold text-slate-900 text-sm">{t('investigationPanel.caseHash', 'Case #')}{c.id}</span>
          <SeverityBadge severity={c.priority_band} />
          <CaseStatusBadge status={c.status} />
        </div>
        <div className="text-[11px] text-slate-400 font-mono">
          {t('investigationPanel.priority', 'priority')} {c.priority_score === null || c.priority_score === undefined ? t('common.notApplicable', 'n/a') : Math.round(c.priority_score * 100)}
          {c.sla_due_at && <span> &bull; {t('investigationPanel.due', 'due')} {new Date(c.sla_due_at).toLocaleDateString()}</span>}
        </div>
      </div>

      {/* Priority breakdown */}
      {c.priority_breakdown?.terms && (
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 text-[10px]">
          {Object.entries(c.priority_breakdown.terms).map(([key, term]) => (
            <div key={key} className="p-1.5 bg-slate-50 rounded border border-slate-200 text-center" title={term.basis}>
              <span className="text-slate-400 block">{t(TERM_LABEL_KEYS[key] || `investigationPanel.term.${key}`, TERM_LABELS_EN[key] || key)}</span>
              {term.available ? (
                <span className="font-mono font-bold text-slate-700">{Math.round(term.value * 100)}%</span>
              ) : (
                <span className="text-slate-400">{t('common.notApplicable', 'n/a')}</span>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Linked findings */}
      {c.finding_ids?.length > 0 && (
        <div>
          <span className="text-[10px] font-bold uppercase text-slate-400 block mb-1">{t('investigationPanel.linkedFindings', 'Linked findings')}</span>
          <ul className="space-y-1 text-[11px]">
            {c.finding_ids.map((fid) => {
              const f = findingsById?.[fid];
              return (
                <li key={fid} className="flex items-center gap-1.5">
                  <span className="font-mono text-slate-400">#{fid}</span>
                  <span className="text-slate-700 truncate">{f ? f.explanation : `${f?.finding_type || t('investigationPanel.finding', 'finding')}`}</span>
                </li>
              );
            })}
          </ul>
        </div>
      )}

      <div className="text-[11px] text-slate-500">
        {t('investigationPanel.assignedTo', 'Assigned to')}: {c.assigned_to ? (isAssignedToMe ? t('investigationPanel.you', 'You') : `${t('investigationCenter.officerHash', 'officer')} #${c.assigned_to}`) : t('investigationCenter.unassigned', 'Unassigned')}
      </div>

      {/* Comments */}
      {c.comments?.length > 0 && (
        <div className="space-y-1.5 max-h-40 overflow-y-auto pr-1">
          {c.comments.map((cm, i) => (
            <div key={i} className="p-2 bg-slate-50 rounded-lg text-[11px]">
              <div className="flex items-center justify-between text-slate-400 mb-0.5">
                <span className="font-bold text-slate-600">{cm.author_name}</span>
                <span>{new Date(cm.created_at).toLocaleString()}</span>
              </div>
              <div className="text-slate-700">{cm.text}</div>
            </div>
          ))}
        </div>
      )}

      {error && <div className="text-[11px] text-red-600">{error}</div>}

      {canManage && !isClosed && (
        <div className="pt-2 border-t border-slate-100 space-y-2">
          <div className="flex items-center gap-2 flex-wrap">
            {!c.assigned_to && (
              <button
                onClick={assignToMe}
                disabled={busy}
                className="inline-flex items-center gap-1 px-2.5 py-1.5 bg-blue-50 text-blue-700 border border-blue-200 rounded-lg text-[11px] font-bold hover:bg-blue-100 disabled:opacity-50"
              >
                <UserPlus className="w-3.5 h-3.5" />
                {t('investigationPanel.assignToMe', 'Assign to me')}
              </button>
            )}
            <button
              onClick={() => setShowResolve((s) => !s)}
              className="inline-flex items-center gap-1 px-2.5 py-1.5 border border-slate-300 text-slate-600 rounded-lg text-[11px] font-bold hover:bg-slate-50"
            >
              <CheckCircle2 className="w-3.5 h-3.5" />
              {t('investigationPanel.resolveCaseEllipsis', 'Resolve case...')}
            </button>
          </div>

          <div className="flex items-center gap-2">
            <input
              type="text"
              value={commentText}
              onChange={(e) => setCommentText(e.target.value)}
              placeholder={t('investigationPanel.addComment', 'Add a progress comment...')}
              className="flex-1 text-xs p-2 border border-slate-300 rounded-lg focus:ring-emerald-500 focus:border-emerald-500"
            />
            <button
              onClick={submitComment}
              disabled={busy || !commentText.trim()}
              className="p-2 bg-slate-100 hover:bg-slate-200 rounded-lg text-slate-600 disabled:opacity-50"
              title={t('investigationPanel.postComment', 'Post comment')}
            >
              <Send className="w-3.5 h-3.5" />
            </button>
          </div>

          {showResolve && (
            <div className="p-3 bg-emerald-50/40 border border-emerald-200 rounded-xl space-y-2">
              <textarea
                rows={2}
                value={resolution}
                onChange={(e) => setResolution(e.target.value)}
                placeholder={t('investigationPanel.resolutionPlaceholder', 'What was found and how was it resolved? (required)')}
                className="w-full text-xs p-2 border border-slate-300 rounded-lg focus:ring-emerald-500 focus:border-emerald-500"
              />
              <button
                onClick={submitResolve}
                disabled={busy}
                className="px-3 py-1.5 bg-emerald-700 hover:bg-emerald-800 text-white rounded-lg font-bold text-[11px] disabled:opacity-50"
              >
                {busy ? t('investigationPanel.closing', 'Closing...') : t('investigationPanel.closeCase', 'Close case')}
              </button>
            </div>
          )}
        </div>
      )}

      {isClosed && c.resolution && (
        <div className="p-2.5 bg-emerald-50 border border-emerald-200 rounded-lg text-[11px] text-emerald-900 flex items-start gap-1.5">
          <CheckCircle2 className="w-3.5 h-3.5 shrink-0 mt-0.5" />
          {c.resolution}
        </div>
      )}
    </div>
  );
};

/**
 * Phase 7's officer workflow (assign/comment/resolve), surfaced on the
 * parcel it belongs to rather than as a separate global queue screen - see
 * InvestigationCenter.jsx for the cross-parcel prioritised list the spec's
 * screen tree also calls for. Reassigning a case to someone other than
 * yourself needs a staff user directory, which is admin-only
 * (`GET /admin/users`); rather than either exposing that broadly or
 * building a picker only admins can use, this panel offers the action every
 * role in CAN_MANAGE_INVESTIGATIONS can actually take without another
 * permission - "assign to me", i.e. picking up your own case.
 */
export const InvestigationPanel = ({ cases, findingsById, canManage, currentUser, onCaseUpdated }) => {
  const { t } = useLanguage();
  if (!cases || cases.length === 0) {
    return (
      <div className="p-8 text-center text-xs text-slate-500 bg-white rounded-xl border border-slate-200 flex flex-col items-center gap-2">
        <MessageSquare className="w-6 h-6 text-slate-300" />
        {t('investigationPanel.noCaseOpened', 'No investigation case has been opened for this parcel. A case opens automatically once processing finds something that needs attention.')}
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {cases.map((c) => (
        <CaseCard
          key={c.id}
          c={c}
          findingsById={findingsById}
          canManage={canManage}
          currentUser={currentUser}
          onCaseUpdated={onCaseUpdated}
        />
      ))}
    </div>
  );
};
