import React, { useState } from 'react';
import { ChevronDown, ChevronUp, Gauge } from 'lucide-react';
import { useLanguage } from '../../context/LanguageContext';

const COMPONENT_LABEL_KEYS = {
  extraction_quality: 'sufficiencyGauge.extractionQuality',
  cross_document_agreement: 'sufficiencyGauge.crossDocumentAgreement',
  temporal_continuity: 'sufficiencyGauge.temporalContinuity',
  event_evidence: 'sufficiencyGauge.eventEvidence',
  identity_confidence: 'sufficiencyGauge.identityConfidence',
  spatial_consistency: 'sufficiencyGauge.spatialConsistency'
};

const COMPONENT_LABELS_EN = {
  extraction_quality: 'Extraction quality',
  cross_document_agreement: 'Cross-document agreement',
  temporal_continuity: 'Temporal continuity',
  event_evidence: 'Event evidence',
  identity_confidence: 'Identity confidence',
  spatial_consistency: 'Spatial consistency'
};

const scoreColor = (v) => {
  if (v === null || v === undefined) return 'text-slate-400';
  if (v >= 0.75) return 'text-emerald-700';
  if (v >= 0.5) return 'text-amber-600';
  return 'text-red-700';
};

const scoreRing = (v) => {
  if (v === null || v === undefined) return 'border-slate-200 bg-slate-50';
  if (v >= 0.75) return 'border-emerald-300 bg-emerald-50';
  if (v >= 0.5) return 'border-amber-300 bg-amber-50';
  return 'border-red-300 bg-red-50';
};

/**
 * EvidenceSufficiencyScorer's output (Phase 6 gate: "score breakdown visible
 * and reproducible" - BHUMI_FORENSICS_SPEC.md §9). `score` is the raw
 * GET /parcels/{id}/sufficiency response. A component with available:false
 * is rendered as "not available" text, never folded into the number or
 * defaulted to zero - the scorer already excludes it from the weighted
 * average and renormalises the remaining weights.
 */
export const SufficiencyGauge = ({ score, loading }) => {
  const { t } = useLanguage();
  const [expanded, setExpanded] = useState(false);

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-xs text-slate-400">
        <Gauge className="w-4 h-4 animate-pulse" />
        {t('sufficiencyGauge.computing', 'Computing evidence sufficiency...')}
      </div>
    );
  }
  if (!score) return null;

  const pct = score.overall_score === null || score.overall_score === undefined
    ? null
    : Math.round(score.overall_score * 100);

  return (
    <div className={`rounded-xl border p-3 ${scoreRing(score.overall_score)}`}>
      <button
        onClick={() => setExpanded((e) => !e)}
        className="w-full flex items-center justify-between text-xs"
      >
        <span className="flex items-center gap-1.5 font-bold text-slate-700 uppercase tracking-wide text-[10px]">
          <Gauge className="w-3.5 h-3.5" />
          {t('sufficiencyGauge.evidenceSufficiency', 'Evidence sufficiency')}
        </span>
        <span className="flex items-center gap-1.5">
          <span className={`text-lg font-bold font-mono ${scoreColor(score.overall_score)}`}>
            {pct === null ? t('common.notApplicable', 'n/a') : `${pct}%`}
          </span>
          {expanded ? <ChevronUp className="w-3.5 h-3.5 text-slate-400" /> : <ChevronDown className="w-3.5 h-3.5 text-slate-400" />}
        </span>
      </button>

      {expanded && (
        <div className="mt-3 space-y-1.5 border-t border-black/5 pt-2">
          {Object.entries(score.components || {}).map(([key, c]) => (
            <div key={key} className="flex items-center justify-between text-[11px]">
              <span className="text-slate-600">{t(COMPONENT_LABEL_KEYS[key] || `sufficiencyGauge.component.${key}`, COMPONENT_LABELS_EN[key] || key)}</span>
              {c.available ? (
                <span className={`font-mono font-bold ${scoreColor(c.value)}`}>
                  {Math.round((c.value ?? 0) * 100)}%
                  <span className="text-slate-400 font-normal"> ({t('sufficiencyGauge.weight', 'weight')} {Math.round(c.weight * 100)}%)</span>
                </span>
              ) : (
                <span className="text-slate-400 italic" title={c.basis || undefined}>
                  {t('sufficiencyGauge.notAvailable', 'not available')}
                </span>
              )}
            </div>
          ))}
          <div className="text-[10px] text-slate-400 pt-1">
            {t('sufficiencyGauge.formula', 'Formula')} {score.formula_version} &bull; {t('sufficiencyGauge.computed', 'computed')} {new Date(score.computed_at).toLocaleString()}
          </div>
        </div>
      )}
    </div>
  );
};
