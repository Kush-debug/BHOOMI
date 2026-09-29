import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ZoomIn,
  ZoomOut,
  RotateCw,
  CheckCircle2,
  AlertTriangle,
  FileCheck,
  Languages,
  Eye,
  ArrowLeft,
  Sparkles,
  ShieldCheck,
  RefreshCw,
  Globe
} from 'lucide-react';
import api from '../services/api';
import { useLanguage } from '../context/LanguageContext';
import { StatusBadge, ConfidenceBadge } from '../components/common/Badge';

export const VerificationWorkspace = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const { t } = useLanguage();

  const [document, setDocument] = useState(null);
  const [fields, setFields] = useState([]);
  const [anomalies, setAnomalies] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeFieldKey, setActiveFieldKey] = useState(null);

  // Split-screen Viewer state
  const [zoom, setZoom] = useState(1);
  const [rotation, setRotation] = useState(0);
  const [imageMode, setImageMode] = useState('enhanced'); // 'raw' or 'enhanced'
  const [activePage, setActivePage] = useState(1);
  const [renderedWidth, setRenderedWidth] = useState(0);
  const [imageError, setImageError] = useState(false);
  const [pageImageUrl, setPageImageUrl] = useState(null);
  const [viewMode, setViewMode] = useState('translated'); // 'translated', 'original', 'diff'
  const [targetLang, setTargetLang] = useState('en');

  // Human edits and verifier notes
  const [editedFields, setEditedFields] = useState({});
  const [officerNotes, setOfficerNotes] = useState('');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    fetchDocumentDetails();
  }, [id]);

  const fetchDocumentDetails = async () => {
    setLoading(true);
    try {
      const res = await api.get(`/documents/${id}`);
      setDocument(res.data);
      setFields(res.data.extracted_fields || []);
      setTargetLang(res.data.target_language || 'en');

      const initialEdits = {};
      (res.data.extracted_fields || []).forEach(f => {
        initialEdits[f.standardized_field] = f.field_value;
      });
      setEditedFields(initialEdits);

      const anomRes = await api.get('/validation/anomalies');
      const docAnomalies = anomRes.data.filter(a => a.document_id === parseInt(id));
      setAnomalies(docAnomalies);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  // The page image endpoint requires authentication, and <img src> cannot carry a
  // bearer token, so the image is fetched through the API client and shown from an
  // object URL.
  useEffect(() => {
    if (!id) return undefined;
    let objectUrl = null;
    let alive = true;
    setImageError(false);
    setPageImageUrl(null);

    api
      .get(`/documents/${id}/pages/${activePage}`, {
        params: { enhanced: imageMode === 'enhanced' },
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
  }, [id, activePage, imageMode]);

  const handleFieldChange = (fieldKey, value) => {
    setEditedFields(prev => ({ ...prev, [fieldKey]: value }));
  };

  const handleSwitchTranslation = async (newLang) => {
    setTargetLang(newLang);
    try {
      await api.post(`/processing/${id}/translate?target_lang=${newLang}`);
      fetchDocumentDetails();
    } catch (err) {
      console.error('Translation switch failed:', err);
    }
  };

  const handleSubmitVerification = async (action) => {
    setSubmitting(true);
    try {
      await api.post(`/verification/${id}/submit`, {
        action: action,
        notes: officerNotes,
        corrected_fields: editedFields
      });
      alert(`Document #${id} verification submitted successfully!`);
      navigate('/records');
    } catch (err) {
      alert('Verification submission failed.');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="py-24 text-center text-slate-500 text-xs">
        <RefreshCw className="w-8 h-8 animate-spin mx-auto text-emerald-700 mb-2" />
        Loading Human-in-the-Loop Split-Screen Workspace...
      </div>
    );
  }

  if (!document) {
    return <div className="p-8 text-center text-xs text-slate-500">{t('verificationWorkspace.documentNotFound', 'Document not found.')}</div>;
  }

  const activeFieldObj = fields.find(f => f.standardized_field === activeFieldKey);
  // A field only has geometry when OCR actually produced it. There is no
  // placeholder rectangle: a value with no region says so instead of pointing
  // the officer at an arbitrary part of the page.
  const bbox = activeFieldObj?.bbox_source === 'OCR_WORD_BOX' ? activeFieldObj.bounding_box : null;
  const activeFieldHasRegion = Boolean(bbox);

  // OCR geometry is expressed in the pixel space of the rendered page image.
  // Scale it to the size the image is actually displayed at, so the highlight
  // lands on the right words at any zoom level.
  const pageMeta = document.pages?.find((pg) => pg.page_number === activePage);
  const scale = pageMeta?.width && renderedWidth ? renderedWidth / pageMeta.width : 1;

  return (
    <div className="space-y-4">
      {/* Top Action Bar */}
      <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate('/verification')}
            className="p-1.5 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base font-bold text-slate-900 tracking-tight">
                {document.file_name}
              </h2>
              <StatusBadge status={document.status} />
            </div>
            <div className="text-[11px] text-slate-500 flex items-center gap-2 mt-0.5">
              <span>{document.village}, {document.tehsil}, {document.district} ({document.state})</span>
              <span>&bull;</span>
              <span className="font-mono">{document.document_type.replace('_', ' ').toUpperCase()}</span>
            </div>
          </div>
        </div>

        {/* Multilingual Document Indicators & Display Selector */}
        <div className="flex items-center gap-2 flex-wrap">
          <div className="flex items-center gap-1.5 px-3 py-1.5 bg-emerald-50 border border-emerald-200 rounded-lg text-xs font-bold text-emerald-900">
            <Languages className="w-3.5 h-3.5 text-emerald-700" />
            <span>Detected: {document.detected_language_name || 'Hindi'}</span>
            <span className="text-emerald-700 text-[10px] font-mono">
              ({document.language_confidence === null || document.language_confidence === undefined ? 'confidence n/a' : `${(document.language_confidence * 100).toFixed(0)}%`})
            </span>
          </div>

          <div className="flex items-center gap-1 text-xs">
            <span className="text-slate-500 font-semibold">{t('verification.translateTo', 'Display Translation')}:</span>
            <select
              value={targetLang}
              onChange={(e) => handleSwitchTranslation(e.target.value)}
              className="text-xs border border-slate-300 rounded-lg p-1.5 font-bold text-slate-800 bg-white"
            >
              <option value="en">English (Translation)</option>
              <option value="hi">हिन्दी (Hindi)</option>
              <option value="ta">தமிழ் (Tamil)</option>
              <option value="te">తెలుగు (Telugu)</option>
              <option value="kn">ಕನ್ನಡ (Kannada)</option>
            </select>
          </div>
        </div>
      </div>

      {/* Discrepancies Alert Banner */}
      {anomalies.length > 0 && (
        <div className="p-3.5 bg-amber-50 border border-amber-200 rounded-xl space-y-1.5 text-xs">
          <div className="flex items-center gap-2 font-bold text-amber-900">
            <AlertTriangle className="w-4 h-4 text-amber-700" />
            {anomalies.length} Discrepancy Flagged for Human Resolution
          </div>
          {anomalies.map(a => (
            <div key={a.id} className="text-amber-800 text-[11px] pl-6">
              &bull; <b>{a.rule_name}:</b> {a.message} (Expected: <span className="font-mono">{a.expected_value}</span>, Extracted: <span className="font-mono text-red-700">{a.actual_value}</span>)
            </div>
          ))}
        </div>
      )}

      {/* Split-Screen Workspace Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* LEFT PANE: High-Res Document Viewer (Zoom, Rotate, Bounding Box) */}
        <div className="lg:col-span-6 bg-slate-900 rounded-xl p-4 flex flex-col justify-between h-[650px] shadow-xs relative overflow-hidden">
          {/* Controls Bar */}
          <div className="flex items-center justify-between text-white text-xs z-10 bg-slate-800/90 backdrop-blur-xs p-2 rounded-lg border border-slate-700">
            <div className="flex items-center gap-1.5">
              <button
                onClick={() => setImageMode('raw')}
                className={`px-2.5 py-1 rounded text-[11px] font-bold ${imageMode === 'raw' ? 'bg-emerald-600 text-white' : 'text-slate-400 hover:text-white'}`}
              >
                {t('verification.rawScan', 'Original Scan')}
              </button>
              <button
                onClick={() => setImageMode('enhanced')}
                className={`px-2.5 py-1 rounded text-[11px] font-bold ${imageMode === 'enhanced' ? 'bg-emerald-600 text-white' : 'text-slate-400 hover:text-white'}`}
              >
                {t('verification.enhanced', 'OpenCV Enhanced')}
              </button>
            </div>

            <div className="flex items-center gap-1">
              {/* Page navigation: every page is OCR'd now, so all of them are reachable. */}
              {(document.pages?.length || 1) > 1 && (
                <div className="flex items-center gap-1 mr-2 text-[11px] text-slate-300">
                  <button
                    onClick={() => setActivePage((p) => Math.max(1, p - 1))}
                    disabled={activePage <= 1}
                    className="px-1.5 py-0.5 rounded hover:bg-slate-700 disabled:opacity-30"
                  >
                    &lsaquo;
                  </button>
                  <span className="font-mono">
                    {activePage} / {document.pages.length}
                  </span>
                  <button
                    onClick={() => setActivePage((p) => Math.min(document.pages.length, p + 1))}
                    disabled={activePage >= document.pages.length}
                    className="px-1.5 py-0.5 rounded hover:bg-slate-700 disabled:opacity-30"
                  >
                    &rsaquo;
                  </button>
                </div>
              )}
              <button
                onClick={() => setZoom(prev => Math.min(prev + 0.2, 2.5))}
                className="p-1 hover:bg-slate-700 rounded text-slate-300"
                title={t('verification.zoomIn', 'Zoom In')}
              >
                <ZoomIn className="w-4 h-4" />
              </button>
              <button
                onClick={() => setZoom(prev => Math.max(prev - 0.2, 0.6))}
                className="p-1 hover:bg-slate-700 rounded text-slate-300"
                title={t('verification.zoomOut', 'Zoom Out')}
              >
                <ZoomOut className="w-4 h-4" />
              </button>
              <button
                onClick={() => setRotation(prev => (prev + 90) % 360)}
                className="p-1 hover:bg-slate-700 rounded text-slate-300"
                title={t('verification.rotate', 'Rotate 90°')}
              >
                <RotateCw className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Document Canvas Container */}
          <div className="flex-1 overflow-auto flex items-center justify-center p-4 relative">
            <div
              style={{
                transform: `scale(${zoom}) rotate(${rotation}deg)`,
                transformOrigin: 'center center',
                transition: 'transform 0.2s ease-out'
              }}
              className="relative shadow-2xl rounded bg-white p-2"
            >
              {/* The actual rendered page image, served from the stored upload.
                  This pane previously drew a simulated paper canvas containing the
                  OCR text, so the officer never saw the real scan and the source
                  region overlay had nothing to point at. */}
              <div className="relative select-none" style={{ lineHeight: 0 }}>
                {pageImageUrl && !imageError && (
                  <img
                    src={pageImageUrl}
                    alt={`Page ${activePage} of ${document.file_name}`}
                    onLoad={(e) => setRenderedWidth(e.currentTarget.clientWidth)}
                    className="max-w-[460px] block"
                  />
                )}
                {!pageImageUrl && !imageError && (
                  <div className="w-[450px] h-[580px] bg-slate-100 border border-slate-300 flex items-center justify-center text-xs text-slate-500">
                    Loading page image...
                  </div>
                )}
                {imageError && (
                  <div className="w-[450px] h-[580px] bg-slate-100 border border-slate-300 flex flex-col items-center justify-center gap-2 text-center p-6">
                    <span className="text-xs font-bold text-slate-700">
                      Page image unavailable
                    </span>
                    <span className="text-[11px] text-slate-500">
                      The rendered page for this document is not present on the server.
                      Re-upload the file to regenerate it. The extracted values below
                      cannot be visually verified until it is available.
                    </span>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* RIGHT PANE: Structured AI Extracted Fields Editor */}
        <div className="lg:col-span-6 bg-white rounded-xl border border-slate-200 p-5 shadow-xs flex flex-col justify-between h-[650px] overflow-y-auto">
          <div className="space-y-4 text-xs">
            {/* Confidence Breakdown Header */}
            <div className="bg-slate-50 p-3 rounded-xl border border-slate-200">
              <span className="text-[10px] font-bold uppercase text-slate-500 block mb-1.5">
                Measured confidence
              </span>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-center text-[10px]">
                {[
                  ['Language', document.language_confidence, 'text-emerald-700'],
                  ['OCR', document.ocr_confidence, 'text-blue-700'],
                  ['Extraction', document.extraction_confidence, 'text-emerald-700'],
                  ['Validation', document.validation_confidence, 'text-purple-700']
                ].map(([label, value, colour]) => (
                  <div key={label} className="p-1.5 bg-white rounded border border-slate-200">
                    <span className="text-slate-400 block">{label}</span>
                    {value === null || value === undefined ? (
                      <span className="font-semibold text-slate-400">n/a</span>
                    ) : (
                      <span className={`font-bold font-mono ${colour}`}>
                        {(value * 100).toFixed(0)}%
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </div>

            {/* Full OCR + Translation */}
            <div className="space-y-2 p-3 rounded-xl border border-emerald-200 bg-emerald-50/40">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-bold text-slate-800 flex items-center gap-2">
                  <Languages className="w-4 h-4 text-emerald-700" />
                  Document Translation
                </h3>
                <span className="text-[10px] text-slate-500">
                  {document.detected_language_name || 'Detected language'} → {targetLang.toUpperCase()}
                </span>
              </div>

              <div className="grid grid-cols-1 gap-2">
                <div className="bg-white border border-slate-200 rounded-lg p-3">
                  <div className="text-[10px] font-bold uppercase text-slate-400 mb-1">
                    Original OCR
                  </div>
                  <pre className="whitespace-pre-wrap text-[11px] leading-relaxed text-slate-700 font-sans">
                    {document.original_ocr_text || 'No OCR text available.'}
                  </pre>
                </div>

                <div className="bg-white border border-emerald-200 rounded-lg p-3">
                  <div className="text-[10px] font-bold uppercase text-emerald-700 mb-1">
                    Translated Document
                  </div>
                  <pre className="whitespace-pre-wrap text-[12px] leading-relaxed text-slate-900 font-sans">
                    {document.translated_text || 'Translation not available. Run AI processing first.'}
                  </pre>
                </div>
              </div>
            </div>

            {/* Structured Fields Form */}
            <div className="space-y-3">
              <h3 className="text-sm font-bold text-slate-800 uppercase tracking-wider border-b border-slate-100 pb-1 flex items-center justify-between">
                <span>{t('verification.extractedFields', 'Structured Land Record Fields')}</span>
                <span className="text-[10px] text-slate-400 font-normal">{t('verificationWorkspace.clickFieldToLocate', 'Click field to locate on document')}</span>
              </h3>

              {fields.map((f) => {
                const isModified = editedFields[f.standardized_field] !== f.field_value;
                const isSelected = activeFieldKey === f.standardized_field;

                return (
                  <div
                    key={f.id}
                    onClick={() => setActiveFieldKey(f.standardized_field)}
                    className={`p-3 rounded-xl border transition-colors cursor-pointer ${
                      isSelected
                        ? 'border-emerald-500 bg-emerald-50/40 ring-1 ring-emerald-500'
                        : 'border-slate-200 bg-white hover:bg-slate-50'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-bold text-slate-800 text-xs">
                        {f.field_name}
                      </span>
                      <div className="flex items-center gap-1.5">
                        {isModified && (
                          <span className="px-1.5 py-0.5 bg-amber-100 text-amber-800 rounded text-[9px] font-bold">
                            {t('verificationWorkspace.modified', 'Modified')}
                          </span>
                        )}
                        <ConfidenceBadge confidence={f.confidence} basis={f.confidence_basis} />
                      </div>
                    </div>

                    <input
                      type="text"
                      value={editedFields[f.standardized_field] || ''}
                      onChange={(e) => handleFieldChange(f.standardized_field, e.target.value)}
                      className="w-full text-xs p-2 border border-slate-300 rounded-lg focus:ring-emerald-500 focus:border-emerald-500 font-medium text-slate-900"
                    />

                    {/* Original OCR Text & Transliteration metadata */}
                    <div className="flex items-center justify-between text-[10px] text-slate-400 mt-1 font-mono">
                      <span>{t('verificationWorkspace.originalOcr', 'Original OCR')}: <b className="text-slate-600">{f.original_value || f.field_value}</b></span>
                      {f.transliteration && <span>{t('verificationWorkspace.translit', 'Translit')}: {f.transliteration}</span>}
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Officer Remarks & Audit Notes */}
            <div className="space-y-1.5 pt-2 border-t border-slate-100">
              <label className="block font-bold text-slate-700 text-xs">
                {t('verification.officerNotes', 'Revenue Inspector / Verifier Remarks')}
              </label>
              <textarea
                rows={2}
                value={officerNotes}
                onChange={(e) => setOfficerNotes(e.target.value)}
                placeholder={t('verification.notesPlaceholder', 'Enter justification or verification audit notes...')}
                className="w-full text-xs p-2 border border-slate-300 rounded-lg focus:ring-emerald-500 focus:border-emerald-500"
              />
            </div>
          </div>

          {/* Action Buttons */}
          <div className="pt-4 border-t border-slate-100 flex items-center justify-end gap-2">
            <button
              onClick={() => handleSubmitVerification('rejected')}
              disabled={submitting}
              className="px-3.5 py-2 border border-rose-300 text-rose-700 hover:bg-rose-50 rounded-lg font-bold text-xs"
            >
              {t('verification.rejectRecord', 'Reject')}
            </button>
            <button
              onClick={() => handleSubmitVerification('edited_approved')}
              disabled={submitting}
              className="px-4 py-2 bg-emerald-700 hover:bg-emerald-800 text-white rounded-lg font-bold text-xs flex items-center gap-1.5 shadow-xs"
            >
              <CheckCircle2 className="w-4 h-4" />
              {t('verification.approveRecord', 'Approve & Save Verified Record')}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
