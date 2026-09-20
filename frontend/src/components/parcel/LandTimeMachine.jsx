import React, { useState, useEffect } from 'react';
import { CheckCircle2, AlertTriangle, HelpCircle, User, Ruler, Tag, TrendingUp } from 'lucide-react';
import { useLanguage } from '../../context/LanguageContext';

// area_delta_abs is a raw float subtraction (e.g. 3.9 - 4.8), so it can carry
// IEEE-754 noise like -0.8999999999999999 straight from the API - fine for a
// computation, not for a screen the spec wants a judge to trust in 60
// seconds. Rounded to the same 4 decimal places the backend's own rendered
// finding text already uses (analysis_service.py's `.4f` formatting), so the
// number here always matches what a finding's explanation already shows.
const formatAreaDelta = (value) => {
  if (value === null || value === undefined) return '—';
  const rounded = Math.round(value * 10000) / 10000;
  return rounded > 0 ? `+${rounded}` : `${rounded}`;
};

const FIELD_META = {
  owner_name: { labelKey: 'parcelIntelligence.fieldOwner', label: 'Owner', icon: User },
  area: { labelKey: 'parcelIntelligence.fieldArea', label: 'Area', icon: Ruler },
  classification: { labelKey: 'parcelIntelligence.fieldClassification', label: 'Land classification', icon: Tag },
  khata_number: { labelKey: 'parcelIntelligence.fieldKhataNumber', label: 'Khata number', icon: Tag }
};

const WhyButton = ({ claimId, onWhy }) => {
  const { t } = useLanguage();
  if (!claimId) return null;
  return (
    <button
      onClick={() => onWhy(claimId)}
      className="ml-1.5 inline-flex items-center gap-0.5 text-[10px] font-bold text-emerald-700 hover:text-emerald-900 hover:underline"
      title={t('landTimeMachine.whyTitle', 'See the evidence behind this value')}
    >
      <HelpCircle className="w-3 h-3" />
      {t('parcelIntelligence.why', 'Why?')}
    </button>
  );
};

/**
 * Phase 8 gate (BHUMI_FORENSICS_SPEC.md §9): "A judge understands the product
 * in 60 seconds." This is the screen the spec mocks up literally as a year
 * slider - `1972 - 1987 - 1996 - 2008 - 2014 - 2025` - reading live snapshots
 * and transitions from GET /parcels/{id}/timeline (Phase 4/5), never a
 * client-side interpolation.
 *
 * Ownership History / Area History (listed as their own sub-screens in the
 * spec's screen tree) are deliberately not separate tabs here - they are the
 * same `ownership_delta` / `area_delta` fields every transition already
 * carries, just filtered and laid out as their own list below the slider.
 * Building two more full screens around a subset of data this component
 * already renders would be duplication, not new information.
 */
export const LandTimeMachine = ({ snapshots, transitions, onWhy }) => {
  const { t } = useLanguage();
  const [selectedYear, setSelectedYear] = useState(null);

  useEffect(() => {
    if (snapshots && snapshots.length > 0 && selectedYear === null) {
      setSelectedYear(snapshots[snapshots.length - 1].as_of_year);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [snapshots]);

  if (!snapshots || snapshots.length === 0) {
    return (
      <div className="p-8 text-center text-xs text-slate-500 bg-white rounded-xl border border-slate-200">
        {t('landTimeMachine.noDatedClaims', 'No dated claims yet resolve to this parcel, so there is no timeline to reconstruct.')}
      </div>
    );
  }

  const selected = snapshots.find((s) => s.as_of_year === selectedYear) || snapshots[snapshots.length - 1];
  const selectedIndex = snapshots.indexOf(selected);
  const incomingTransition = selectedIndex > 0
    ? transitions.find((tr) => tr.from_year === snapshots[selectedIndex - 1].as_of_year && tr.to_year === selected.as_of_year)
    : null;

  const ownershipHistory = transitions.filter((tr) => tr.ownership_delta);
  const areaHistory = transitions.filter((tr) => tr.area_delta_abs !== null && tr.area_delta_abs !== 0);

  return (
    <div className="space-y-5">
      {/* Year slider */}
      <div className="bg-white rounded-xl border border-slate-200 p-4 overflow-x-auto">
        <div className="flex items-center gap-2 min-w-max">
          {snapshots.map((s, i) => (
            <React.Fragment key={s.as_of_year}>
              {i > 0 && <div className="w-8 h-px bg-slate-300 shrink-0" />}
              <button
                onClick={() => setSelectedYear(s.as_of_year)}
                className={`px-3.5 py-2 rounded-lg text-xs font-bold font-mono shrink-0 border transition-colors ${
                  s.as_of_year === selected.as_of_year
                    ? 'bg-emerald-700 text-white border-emerald-700 shadow-xs'
                    : 'bg-white text-slate-600 border-slate-300 hover:border-emerald-400 hover:text-emerald-800'
                }`}
              >
                {s.as_of_year}
              </button>
            </React.Fragment>
          ))}
        </div>
      </div>

      {/* Transition into the selected year */}
      {incomingTransition && (
        <div
          className={`rounded-xl border p-3.5 text-xs ${
            incomingTransition.is_material
              ? incomingTransition.explained_by_event_id
                ? 'bg-emerald-50 border-emerald-200'
                : 'bg-red-50 border-red-200'
              : 'bg-slate-50 border-slate-200'
          }`}
        >
          <div className="flex items-center gap-2 font-bold mb-1.5">
            <TrendingUp className="w-4 h-4" />
            {t('landTimeMachine.changeFrom', 'Change from')} {incomingTransition.from_year} {t('landTimeMachine.to', 'to')} {incomingTransition.to_year}
            {incomingTransition.is_material ? (
              incomingTransition.explained_by_event_id ? (
                <span className="inline-flex items-center gap-1 text-emerald-800">
                  <CheckCircle2 className="w-3.5 h-3.5" /> {t('landTimeMachine.explained', 'explained')}
                  {incomingTransition.match_confidence !== null && incomingTransition.match_confidence !== undefined && (
                    <span className="font-mono font-normal">
                      ({Math.round(incomingTransition.match_confidence * 100)}% {t('landTimeMachine.match', 'match')})
                    </span>
                  )}
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 text-red-800">
                  <AlertTriangle className="w-3.5 h-3.5" /> {t('landTimeMachine.unexplained', 'unexplained - no supporting record on file')}
                </span>
              )
            ) : (
              <span className="text-slate-500 font-normal">{t('landTimeMachine.notMaterial', 'not material')}</span>
            )}
          </div>
          <ul className="pl-1 space-y-0.5 text-slate-700">
            {incomingTransition.ownership_delta && (
              <li>
                {t('landTimeMachine.owner', 'Owner')}: <span className="font-semibold">{incomingTransition.ownership_delta.from_name || '—'}</span>
                {' → '}
                <span className="font-semibold">{incomingTransition.ownership_delta.to_name || '—'}</span>
              </li>
            )}
            {incomingTransition.area_delta_abs !== null && incomingTransition.area_delta_abs !== 0 && (
              <li>
                {t('landTimeMachine.areaChangedBy', 'Area changed by')} <span className="font-mono font-semibold">{formatAreaDelta(incomingTransition.area_delta_abs)}</span>
                {incomingTransition.area_delta_pct !== null && (
                  <span className="font-mono text-slate-500"> ({incomingTransition.area_delta_pct > 0 ? '+' : ''}{incomingTransition.area_delta_pct.toFixed(1)}%)</span>
                )}
              </li>
            )}
            {incomingTransition.classification_delta && (
              <li>
                {t('parcelIntelligence.fieldClassification', 'Classification')}: <span className="font-semibold">{incomingTransition.classification_delta.from}</span>
                {' → '}
                <span className="font-semibold">{incomingTransition.classification_delta.to}</span>
              </li>
            )}
            {incomingTransition.changed_predicates.length === 0 && <li className="text-slate-400">{t('landTimeMachine.noPredicateChanged', 'No tracked predicate changed.')}</li>}
          </ul>
        </div>
      )}

      {/* Selected year's snapshot */}
      <div className="bg-white rounded-xl border border-slate-200 p-5">
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-bold text-slate-900 text-sm">{t('landTimeMachine.stateAsOf', 'State as of')} {selected.as_of_year}</h3>
          {selected.snapshot_sufficiency !== null && selected.snapshot_sufficiency !== undefined && (
            <span className="text-[10px] font-mono text-slate-400">
              {t('landTimeMachine.sufficiency', 'sufficiency')} {Math.round(selected.snapshot_sufficiency * 100)}%
            </span>
          )}
        </div>

        {selected.contested_predicates.length > 0 && (
          <div className="mb-3 p-2.5 bg-purple-50 border border-purple-200 rounded-lg text-[11px] text-purple-800 flex items-start gap-2">
            <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
            <span>
              {selected.contested_predicates.join(', ')} {t('landTimeMachine.contestedThisYear', 'contested this year - independent documents disagree. See the Conflicts tab.')}
            </span>
          </div>
        )}

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
          {Object.entries(FIELD_META).map(([key, meta]) => {
            const Icon = meta.icon;
            const value = key === 'area'
              ? (selected.area !== null && selected.area !== undefined ? `${selected.area} ${selected.area_unit || ''}`.trim() : null)
              : selected[key];
            const claimId = selected.supporting_claim_ids?.[key];
            return (
              <div key={key} className="p-3 bg-slate-50 rounded-lg border border-slate-200">
                <span className="text-[10px] font-bold uppercase text-slate-400 flex items-center gap-1">
                  <Icon className="w-3 h-3" /> {t(meta.labelKey, meta.label)}
                </span>
                <div className="mt-0.5 flex items-center">
                  <span className="font-semibold text-slate-900">{value ?? '—'}</span>
                  <WhyButton claimId={claimId} onWhy={onWhy} />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Ownership / Area history, condensed from the same transitions */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-white rounded-xl border border-slate-200 p-4">
          <h4 className="font-bold text-slate-800 uppercase text-[11px] tracking-wider mb-2">{t('landTimeMachine.ownershipHistory', 'Ownership history')}</h4>
          {ownershipHistory.length === 0 ? (
            <p className="text-[11px] text-slate-400">{t('landTimeMachine.noOwnershipChange', 'No ownership change recorded across the years on file.')}</p>
          ) : (
            <ul className="space-y-1.5 text-[11px]">
              {ownershipHistory.map((tr, i) => (
                <li key={i} className="flex items-center justify-between border-b border-slate-50 pb-1.5 last:border-0">
                  <span>
                    <span className="font-mono text-slate-400">{tr.from_year}&rarr;{tr.to_year}</span>{' '}
                    <span className="font-semibold text-slate-800">{tr.ownership_delta.from_name || '—'}</span>
                    {' → '}
                    <span className="font-semibold text-slate-800">{tr.ownership_delta.to_name || '—'}</span>
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
        <div className="bg-white rounded-xl border border-slate-200 p-4">
          <h4 className="font-bold text-slate-800 uppercase text-[11px] tracking-wider mb-2">{t('landTimeMachine.areaHistory', 'Area history')}</h4>
          {areaHistory.length === 0 ? (
            <p className="text-[11px] text-slate-400">{t('landTimeMachine.noAreaChange', 'No area change recorded across the years on file.')}</p>
          ) : (
            <ul className="space-y-1.5 text-[11px]">
              {areaHistory.map((tr, i) => (
                <li key={i} className="flex items-center justify-between border-b border-slate-50 pb-1.5 last:border-0">
                  <span className="font-mono text-slate-400">{tr.from_year}&rarr;{tr.to_year}</span>
                  <span className="font-mono font-semibold text-slate-800">
                    {formatAreaDelta(tr.area_delta_abs)}
                    {tr.area_delta_pct !== null && ` (${tr.area_delta_pct > 0 ? '+' : ''}${tr.area_delta_pct.toFixed(1)}%)`}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
};
