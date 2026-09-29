import React, { useState, useEffect, useCallback } from 'react';
import { FileText, Layers, Link2, ShieldCheck, AlertTriangle, RefreshCw, Pencil, Check, X as XIcon } from 'lucide-react';
import api from '../../services/api';
import { Modal } from '../common/Modal';
import { ConfidenceBadge } from '../common/Badge';
import { useLanguage } from '../../context/LanguageContext';

/**
 * The Evidence Graph, as a drill-down: fact -> claim -> region -> page -> document
 * (BHUMI_FORENSICS_SPEC.md §7). Given a claim id, walks GET /claims/{id}/evidence
 * and renders the real OCR region highlighted on the real page image - or an
 * honest "no source region" state, never a guessed rectangle.
 *
 * Also the one place in Phase 8 that writes: when `canCorrect` is true (the
 * signed-in user is not a viewer - matches CAN_APPROVE_RECORD server-side),
 * staff can correct the claim's value right here via Phase 7's
 * POST /verification/{doc_id}/claims/{claim_id}/correct, without leaving the
 * parcel page to go find the document in the verification queue.
 */
export const EvidenceDrawer = ({ claimId, isOpen, onClose, canCorrect, onCorrected }) => {
  const { t } = useLanguage();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [data, setData] = useState(null);

  const [pageImageUrl, setPageImageUrl] = useState(null);
  const [imageError, setImageError] = useState(false);
  const [renderedWidth, setRenderedWidth] = useState(0);

  const [correcting, setCorrecting] = useState(false);
  const [correctValue, setCorrectValue] = useState('');
  const [correctNotes, setCorrectNotes] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);

  const load = useCallback((id) => {
    if (!id) return;
    setLoading(true);
    setError(null);
    api
      .get(`/claims/${id}/evidence`)
      .then((res) => {
        setData(res.data);
        setCorrectValue(res.data?.claim?.field_value || '');
      })
      .catch((err) => {
        setError(err.response?.data?.detail || t('evidenceDrawer.loadError', 'Could not load evidence for this claim.'));
      })
      .finally(() => setLoading(false));
  }, [t]);

  useEffect(() => {
    if (isOpen && claimId) {
      setCorrecting(false);
      setSubmitError(null);
      load(claimId);
    }
  }, [isOpen, claimId, load]);

  // Same authenticated-blob technique as VerificationWorkspace.jsx - the page
  // image endpoint requires a bearer token, which a plain <img src> can't send.
  useEffect(() => {
    if (!isOpen || !data?.document?.id || !data?.evidence_region) {
      setPageImageUrl(null);
      return undefined;
    }
    let objectUrl = null;
    let alive = true;
    setImageError(false);
    setPageImageUrl(null);
    setRenderedWidth(0);

    api
      .get(`/documents/${data.document.id}/pages/${data.evidence_region.page_number}`, {
        params: { enhanced: true },
        responseType: 'blob'
      })
      .then((res) => {
        if (!alive) return;
        objectUrl = URL.createObjectURL(res.data);
        setPageImageUrl(objectUrl);
      })
      .catch(() => alive && setImageError(true));

    return () => {
      alive = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [isOpen, data]);

  const submitCorrection = async () => {
    if (!data?.document?.id || !data?.claim?.id) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      const res = await api.post(
        `/verification/${data.document.id}/claims/${data.claim.id}/correct`,
        { new_value: correctValue, notes: correctNotes || undefined }
      );
      if (res.data.status === 'unchanged') {
        setCorrecting(false);
        setSubmitting(false);
        return;
      }
      const newClaimId = res.data.new_claim.id;
      setCorrecting(false);
      onCorrected && onCorrected(newClaimId);
      load(newClaimId); // show the freshly-superseding claim, in the same drawer
    } catch (err) {
      setSubmitError(err.response?.data?.detail || t('evidenceDrawer.correctionFailed', 'Correction failed.'));
    } finally {
      setSubmitting(false);
    }
  };

  const claim = data?.claim;
  const region = data?.evidence_region;
  const scale = region?.page_width && renderedWidth ? renderedWidth / region.page_width : 1;

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={t('evidenceDrawer.title', 'Evidence: how the system knows this')} maxWidth="max-w-3xl">
      {loading && (
        <div className="py-12 text-center text-slate-500 text-xs">
          <RefreshCw className="w-6 h-6 animate-spin mx-auto text-emerald-700 mb-2" />
          {t('evidenceDrawer.walkingGraph', 'Walking the evidence graph...')}
        </div>
      )}

      {!loading && error && (
        <div className="py-8 text-center text-xs text-red-600">{error}</div>
      )}

      {!loading && !error && data && (
        <div className="space-y-4 text-xs">
          {/* The claim itself */}
          <div className="bg-slate-50 border border-slate-200 rounded-xl p-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <span className="text-[10px] font-bold uppercase text-slate-400 block">
                  {claim.standardized_field}
                </span>
                <span className="text-lg font-bold text-slate-900">{claim.field_value ?? '—'}</span>
              </div>
              <div className="flex flex-col items-end gap-1.5">
                <ConfidenceBadge confidence={claim.confidence} basis={claim.confidence_basis} />
                <span
                  className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded border ${
                    claim.asserted_by === 'OFFICER'
                      ? 'bg-purple-50 text-purple-700 border-purple-300'
                      : 'bg-blue-50 text-blue-700 border-blue-300'
                  }`}
                >
                  {claim.asserted_by === 'OFFICER' ? t('evidenceDrawer.officerEntered', 'Officer-entered') : t('evidenceDrawer.systemExtracted', 'System-extracted')}
                </span>
              </div>
            </div>
            {claim.source_text && (
              <div className="mt-2 text-[11px] text-slate-600">
                {t('evidenceDrawer.sourceTextOnPage', 'Source text on page')}: <span className="font-mono text-slate-800">&ldquo;{claim.source_text}&rdquo;</span>
              </div>
            )}
          </div>

          {/* Evidence region + real page image, or an honest absence */}
          <div>
            <h4 className="font-bold text-slate-800 uppercase text-[11px] tracking-wider mb-2 flex items-center gap-1.5">
              <Layers className="w-3.5 h-3.5 text-emerald-700" />
              {t('evidenceDrawer.sourceRegion', 'Source region')}
            </h4>
            {!data.evidence_available ? (
              <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg flex items-start gap-2 text-amber-900">
                <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
                <span>{t('evidenceDrawer.noSourceRegion', 'No source region available')} - {data.no_evidence_reason}.</span>
              </div>
            ) : (
              <div className="bg-slate-900 rounded-xl p-3 flex items-center justify-center overflow-auto max-h-[380px]">
                <div className="relative inline-block" style={{ lineHeight: 0 }}>
                  {pageImageUrl && !imageError && (
                    <img
                      src={pageImageUrl}
                      alt={`Page ${region.page_number}`}
                      onLoad={(e) => setRenderedWidth(e.currentTarget.clientWidth)}
                      className="max-w-[560px] block"
                    />
                  )}
                  {!pageImageUrl && !imageError && (
                    <div className="w-[400px] h-[300px] flex items-center justify-center text-slate-400">
                      {t('evidenceDrawer.loadingPageImage', 'Loading page image...')}
                    </div>
                  )}
                  {imageError && (
                    <div className="w-[400px] h-[200px] flex items-center justify-center text-slate-400 text-center px-6">
                      {t('evidenceDrawer.pageImageUnavailable', 'Page image unavailable on the server.')}
                    </div>
                  )}
                  {pageImageUrl && !imageError && renderedWidth > 0 && region.bbox && (
                    <div
                      className="absolute border-2 border-amber-400 bg-amber-400/25 rounded-sm pointer-events-none"
                      style={{
                        left: region.bbox.x * scale,
                        top: region.bbox.y * scale,
                        width: region.bbox.w * scale,
                        height: region.bbox.h * scale
                      }}
                    />
                  )}
                </div>
              </div>
            )}
          </div>

          {/* OCR run + document provenance */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {data.ocr_run && (
              <div className="p-3 bg-white border border-slate-200 rounded-xl">
                <span className="text-[10px] font-bold uppercase text-slate-400 block mb-1">{t('evidenceDrawer.ocrRun', 'OCR run')}</span>
                <div className="text-slate-700">
                  {data.ocr_run.engine} {data.ocr_run.engine_version || ''}
                  {data.ocr_run.mean_word_confidence !== null && data.ocr_run.mean_word_confidence !== undefined && (
                    <span className="text-slate-400"> &bull; {t('evidenceDrawer.meanConfidence', 'mean confidence')} {(data.ocr_run.mean_word_confidence * 100).toFixed(0)}%</span>
                  )}
                </div>
              </div>
            )}
            {data.document && (
              <div className="p-3 bg-white border border-slate-200 rounded-xl flex items-center gap-2">
                <FileText className="w-4 h-4 text-slate-400 shrink-0" />
                <div>
                  <span className="text-[10px] font-bold uppercase text-slate-400 block">{t('evidenceDrawer.document', 'Document')}</span>
                  <span className="text-slate-700">{data.document.file_name}</span>
                  {data.document.source_class === 'SEED_SYNTHETIC' && (
                    <span className="ml-1.5 text-[9px] font-bold uppercase text-purple-600">{t('evidenceDrawer.demoCorpus', 'demo corpus')}</span>
                  )}
                </div>
              </div>
            )}
          </div>

          {/* Supersession chain */}
          {(data.supersedes || data.superseded_by) && (
            <div className="p-3 bg-white border border-slate-200 rounded-xl space-y-1.5">
              <h4 className="font-bold text-slate-800 uppercase text-[11px] tracking-wider flex items-center gap-1.5">
                <Link2 className="w-3.5 h-3.5 text-slate-500" />
                {t('evidenceDrawer.supersessionHistory', 'Supersession history')}
              </h4>
              {data.supersedes && (
                <div className="text-slate-600">
                  {t('evidenceDrawer.supersedesEarlier', 'Supersedes an earlier value')}: <span className="font-mono text-slate-800">{data.supersedes.field_value}</span>
                  {' '}({data.supersedes.asserted_by === 'OFFICER' ? t('evidenceDrawer.officerEnteredLower', 'officer-entered') : t('evidenceDrawer.systemExtractedLower', 'system-extracted')})
                </div>
              )}
              {data.superseded_by && (
                <div className="text-slate-600">
                  {t('evidenceDrawer.laterSuperseded', 'Was itself later superseded by')}: <span className="font-mono text-slate-800">{data.superseded_by.field_value}</span>
                </div>
              )}
            </div>
          )}

          {/* Correction, staff only */}
          {canCorrect && claim.lifecycle_status === 'ACCEPTED' && (
            <div className="pt-2 border-t border-slate-100">
              {!correcting ? (
                <button
                  onClick={() => setCorrecting(true)}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold text-emerald-800 bg-emerald-50 border border-emerald-200 rounded-lg hover:bg-emerald-100"
                >
                  <Pencil className="w-3.5 h-3.5" />
                  {t('evidenceDrawer.correctValue', 'Correct this value')}
                </button>
              ) : (
                <div className="space-y-2 bg-emerald-50/40 border border-emerald-200 rounded-xl p-3">
                  <label className="block font-bold text-slate-700">{t('evidenceDrawer.correctedValue', 'Corrected value')}</label>
                  <input
                    type="text"
                    value={correctValue}
                    onChange={(e) => setCorrectValue(e.target.value)}
                    className="w-full text-xs p-2 border border-slate-300 rounded-lg focus:ring-emerald-500 focus:border-emerald-500"
                  />
                  <label className="block font-bold text-slate-700">{t('evidenceDrawer.reasonOptional', 'Reason (optional, kept on the audit trail)')}</label>
                  <textarea
                    rows={2}
                    value={correctNotes}
                    onChange={(e) => setCorrectNotes(e.target.value)}
                    className="w-full text-xs p-2 border border-slate-300 rounded-lg focus:ring-emerald-500 focus:border-emerald-500"
                  />
                  {submitError && <div className="text-red-600">{submitError}</div>}
                  <div className="flex items-center gap-2 pt-1">
                    <button
                      onClick={submitCorrection}
                      disabled={submitting || !correctValue.trim()}
                      className="inline-flex items-center gap-1 px-3 py-1.5 bg-emerald-700 hover:bg-emerald-800 text-white rounded-lg font-bold disabled:opacity-50"
                    >
                      <Check className="w-3.5 h-3.5" />
                      {submitting ? t('evidenceDrawer.saving', 'Saving...') : t('evidenceDrawer.saveCorrection', 'Save correction')}
                    </button>
                    <button
                      onClick={() => setCorrecting(false)}
                      disabled={submitting}
                      className="inline-flex items-center gap-1 px-3 py-1.5 border border-slate-300 text-slate-600 rounded-lg font-bold hover:bg-slate-50"
                    >
                      <XIcon className="w-3.5 h-3.5" />
                      {t('common.cancel', 'Cancel')}
                    </button>
                  </div>
                  <p className="text-[10px] text-slate-500 flex items-center gap-1">
                    <ShieldCheck className="w-3 h-3" />
                    {t('evidenceDrawer.correctionNote', "This never edits the original AI value - it writes a new, officer-asserted claim that supersedes it.")}
                  </p>
                </div>
              )}
            </div>
          )}

          {claim.lifecycle_status !== 'ACCEPTED' && (
            <div className="text-[10px] text-slate-400">
              {t('evidenceDrawer.claimIsPrefix', 'This claim is')} {claim.lifecycle_status.toLowerCase()} {t('evidenceDrawer.claimIsSuffix', 'and is shown for history only - it is no longer the current value.')}
            </div>
          )}
        </div>
      )}
    </Modal>
  );
};
