import React from 'react';
import { useLanguage } from '../../context/LanguageContext';

export const StatusBadge = ({ status }) => {
  const { t } = useLanguage();
  const map = {
    verified: { label: t('badge.verified', 'Verified'), bg: 'bg-emerald-50 text-emerald-700 border-emerald-300' },
    valid: { label: t('badge.valid', 'Valid'), bg: 'bg-emerald-50 text-emerald-700 border-emerald-300' },
    verification_pending: { label: t('badge.verificationPending', 'Verification Pending'), bg: 'bg-amber-50 text-amber-700 border-amber-300' },
    requires_verification: { label: t('badge.needsVerification', 'Needs Verification'), bg: 'bg-amber-50 text-amber-700 border-amber-300' },
    warning: { label: t('badge.warningFlagged', 'Warning Flagged'), bg: 'bg-orange-50 text-orange-700 border-orange-300' },
    failed: { label: t('badge.validationError', 'Validation Error'), bg: 'bg-red-50 text-red-700 border-red-300' },
    processing: { label: t('badge.processing', 'Processing...'), bg: 'bg-blue-50 text-blue-700 border-blue-300 animate-pulse' },
    uploaded: { label: t('badge.uploaded', 'Uploaded'), bg: 'bg-slate-50 text-slate-700 border-slate-300' },
    rejected: { label: t('badge.rejected', 'Rejected'), bg: 'bg-rose-50 text-rose-700 border-rose-300' },
    disputed: { label: t('badge.disputedParcel', 'Disputed Parcel'), bg: 'bg-purple-50 text-purple-700 border-purple-300' },
    mismatch: { label: t('badge.areaMismatch', 'Area Mismatch'), bg: 'bg-red-50 text-red-700 border-red-300' }
  };

  const item = map[status] || { label: status, bg: 'bg-gray-50 text-gray-700 border-gray-300' };

  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold border ${item.bg}`}>
      {item.label}
    </span>
  );
};

export const ConfidenceBadge = ({ confidence, basis }) => {
  const { t } = useLanguage();
  // null/undefined means the backend could not measure this. Showing 0% would be
  // wrong and showing a default would be a fabrication, so it renders as unknown.
  if (confidence === null || confidence === undefined) {
    return (
      <span
        className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium border bg-slate-100 text-slate-600 border-slate-300"
        title={basis || t('badge.noConfidenceComputed', 'No confidence value was computed for this field.')}
      >
        {t('badge.notMeasured', 'not measured')}
      </span>
    );
  }

  const pct = Math.round(confidence * 100);
  let colorClass = 'bg-emerald-50 text-emerald-700 border-emerald-300';
  if (pct < 70) {
    colorClass = 'bg-red-50 text-red-700 border-red-300';
  } else if (pct < 90) {
    colorClass = 'bg-amber-50 text-amber-700 border-amber-300';
  }

  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-mono font-medium border ${colorClass}`}
      title={basis || undefined}
    >
      {pct}%
    </span>
  );
};

// Phase 8 additions below. Same palette/shape conventions as the badges
// above; kept in this file rather than a new one since every screen that
// needs a finding/case status pill already imports from here.

// Finding.severity and InvestigationCase.priority_band share the exact same
// enum (CRITICAL | HIGH | MEDIUM | LOW - see finding.py / priority_scorer.py),
// so one component renders both.
export const SeverityBadge = ({ severity }) => {
  const { t } = useLanguage();
  const map = {
    CRITICAL: { label: t('badge.critical', 'Critical'), bg: 'bg-red-50 text-red-700 border-red-300' },
    HIGH: { label: t('badge.high', 'High'), bg: 'bg-orange-50 text-orange-700 border-orange-300' },
    MEDIUM: { label: t('badge.medium', 'Medium'), bg: 'bg-amber-50 text-amber-700 border-amber-300' },
    LOW: { label: t('badge.low', 'Low'), bg: 'bg-slate-50 text-slate-600 border-slate-300' }
  };
  const item = map[severity] || { label: severity || t('badge.unscored', 'Unscored'), bg: 'bg-gray-50 text-gray-700 border-gray-300' };
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wide border ${item.bg}`}>
      {item.label}
    </span>
  );
};

// Finding.resolution_status: OPEN | IN_REVIEW | RESOLVED | DISMISSED (finding.py).
export const FindingStatusBadge = ({ status }) => {
  const { t } = useLanguage();
  const map = {
    OPEN: { label: t('badge.open', 'Open'), bg: 'bg-amber-50 text-amber-700 border-amber-300' },
    IN_REVIEW: { label: t('badge.inReview', 'In Review'), bg: 'bg-blue-50 text-blue-700 border-blue-300' },
    RESOLVED: { label: t('badge.resolved', 'Resolved'), bg: 'bg-emerald-50 text-emerald-700 border-emerald-300' },
    DISMISSED: { label: t('badge.dismissed', 'Dismissed'), bg: 'bg-slate-100 text-slate-600 border-slate-300' }
  };
  const item = map[status] || { label: status, bg: 'bg-gray-50 text-gray-700 border-gray-300' };
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold border ${item.bg}`}>
      {item.label}
    </span>
  );
};

// InvestigationCase.status: OPEN | IN_PROGRESS | CLOSED (investigation.py).
export const CaseStatusBadge = ({ status }) => {
  const { t } = useLanguage();
  const map = {
    OPEN: { label: t('badge.open', 'Open'), bg: 'bg-amber-50 text-amber-700 border-amber-300' },
    IN_PROGRESS: { label: t('badge.inProgress', 'In Progress'), bg: 'bg-blue-50 text-blue-700 border-blue-300' },
    CLOSED: { label: t('badge.closed', 'Closed'), bg: 'bg-emerald-50 text-emerald-700 border-emerald-300' }
  };
  const item = map[status] || { label: status, bg: 'bg-gray-50 text-gray-700 border-gray-300' };
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold border ${item.bg}`}>
      {item.label}
    </span>
  );
};
