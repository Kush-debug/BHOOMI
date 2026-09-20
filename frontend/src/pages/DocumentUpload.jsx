import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  UploadCloud,
  FileText,
  Sparkles,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  Eye,
  Layers,
  ArrowRight,
  Globe,
  ShieldCheck,
  Languages
} from 'lucide-react';
import api from '../services/api';
import { useLanguage } from '../context/LanguageContext';
import { DOCUMENT_TYPES } from '../utils/constants';
import { CascadingLocationPicker } from '../components/common/CascadingLocationPicker';

export const DocumentUpload = () => {
  const navigate = useNavigate();
  const { t } = useLanguage();

  const [file, setFile] = useState(null);
  const [filePreview, setFilePreview] = useState(null);
  const [formData, setFormData] = useState({
    state: 'Uttar Pradesh',
    district: 'Kanpur Nagar',
    tehsil: 'Bilhaur',
    village: 'Bilhaur Dehat',
    document_type: 'khatauni',
    document_year: 2024,
    language: 'hi'
  });

  const [uploadedDoc, setUploadedDoc] = useState(null);
  const [pipelineRunning, setPipelineRunning] = useState(false);
  const [pipelineResult, setPipelineResult] = useState(null);
  const [pipelineError, setPipelineError] = useState(null);
  const [pipelineStage, setPipelineStage] = useState(0);

  const handleFileChange = (e) => {
    const selected = e.target.files[0];
    if (selected) {
      setFile(selected);
      if (selected.type.startsWith('image/')) {
        setFilePreview(URL.createObjectURL(selected));
      } else {
        setFilePreview(null);
      }
    }
  };

  const handleUpload = async (e) => {
    e.preventDefault();
    if (!file) return;

    const data = new FormData();
    data.append('file', file);
    data.append('state', formData.state);
    data.append('district', formData.district);
    data.append('tehsil', formData.tehsil);
    data.append('village', formData.village);
    data.append('document_type', formData.document_type);
    data.append('document_year', formData.document_year.toString());
    data.append('language', formData.language);

    try {
      const res = await api.post('/documents/upload', data, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      setUploadedDoc(res.data);
    } catch (err) {
      console.error(err);

      const status = err.response?.status;
      const detail = err.response?.data?.detail;

      // The backend returns `detail` either as a plain string or as a
      // structured object ({ code, message, details }); FastAPI validation
      // errors return an array. Extract a readable string from any of these
      // shapes so the UI never renders "[object Object]".
      let message;
      if (typeof detail === 'string') {
        message = detail;
      } else if (Array.isArray(detail)) {
        message = detail
          .map((e) => e?.msg || (typeof e === 'string' ? e : JSON.stringify(e)))
          .join('; ');
      } else if (detail && typeof detail === 'object') {
        message = detail.message || detail.code || null;
      } else {
        message = null;
      }

      if (status === 409) {
        const existingId = detail?.details?.existing_document_id;
        message =
          (message || 'This exact file has already been uploaded.') +
          (existingId ? ` (existing document #${existingId})` : '');
      } else if (status === 422 && !message) {
        message = 'The uploaded file could not be processed.';
      }

      alert('Upload failed: ' + (message || 'Server error'));
    }
  };

  const handleStartPipeline = async () => {
    if (!uploadedDoc) return;
    setPipelineRunning(true);
    setPipelineStage(1);

    const stagesInterval = setInterval(() => {
      setPipelineStage((prev) => (prev < 6 ? prev + 1 : prev));
    }, 500);

    try {
      setPipelineError(null);
      const res = await api.post(`/processing/${uploadedDoc.id}/start?target_language=en`);
      clearInterval(stagesInterval);
      setPipelineStage(7);
      setPipelineResult(res.data);
    } catch (err) {
      clearInterval(stagesInterval);
      // Processing failures are real information for the officer: which stage
      // failed, why, and what to do about it. They are shown, not swallowed.
      const payload = err.response?.data?.detail || err.response?.data?.error;
      setPipelineError(
        typeof payload === 'string'
          ? { code: 'PROCESSING_FAILED', message: payload }
          : payload || { code: 'NETWORK_ERROR', message: t('documentUpload.networkError', 'Could not reach the processing service.') }
      );
    } finally {
      setPipelineRunning(false);
    }
  };

  const PipelineFailure = () =>
    pipelineError && (
      <div className="bg-red-50 border border-red-200 rounded-xl p-5 space-y-2">
        <div className="flex items-start gap-3">
          <div className="text-red-700 font-bold text-sm">{t('documentUpload.processingFailed', 'Processing failed')}</div>
          <span className="ml-auto font-mono text-[10px] bg-red-100 text-red-800 px-2 py-0.5 rounded">
            {pipelineError.code}
          </span>
        </div>
        <p className="text-xs text-red-900">{pipelineError.message}</p>
        {pipelineError.details?.text_preview && (
          <div className="text-[11px] bg-white border border-red-200 rounded-lg p-2 font-mono text-slate-700">
            <span className="block text-[10px] uppercase font-bold text-slate-500 mb-1">
              {t('documentUpload.whatOcrRead', 'What the OCR actually read')}
            </span>
            {pipelineError.details.text_preview}
          </div>
        )}
        {Array.isArray(pipelineError.details?.next_steps) && (
          <ul className="text-[11px] text-red-900 list-disc ml-4 space-y-0.5">
            {pipelineError.details.next_steps.map((step) => (
              <li key={step}>{step}</li>
            ))}
          </ul>
        )}
        {Array.isArray(pipelineError.details?.likely_causes) && (
          <ul className="text-[11px] text-red-900 list-disc ml-4 space-y-0.5">
            {pipelineError.details.likely_causes.map((cause) => (
              <li key={cause}>{cause}</li>
            ))}
          </ul>
        )}
        <p className="text-[11px] text-red-800 pt-1 border-t border-red-200">
          No values were extracted or stored for this document. The system does not
          substitute sample data when processing fails.
        </p>
      </div>
    );

  const stages = [
    { num: 1, label: 'Image Preprocessing', desc: 'OpenCV Deskew, CLAHE contrast & noise reduction' },
    { num: 2, label: 'Automatic Language Detection', desc: 'Identifies Indic script (Tamil, Telugu, Kannada, Hindi, English)' },
    { num: 3, label: 'Language-Specific Indic OCR', desc: 'Token bounding boxes [x,y,w,h] & character preservation' },
    { num: 4, label: 'Layout & Table Segmentation', desc: 'Revenue tables, headers, notes & stamp detection' },
    { num: 5, label: 'Field Extraction & Protected Translation', desc: 'Extracts names, dates & preserves Survey/Khasra numbers' },
    { num: 6, label: 'Multi-Dimensional Confidence Scoring', desc: 'Scores Language, OCR, Extraction & Translation certainty' },
    { num: 7, label: 'Multi-Tier Validation & Duplicate Check', desc: 'Cross-DB comparison against Master Land Registry' }
  ];

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-xs">
        <h2 className="text-xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
          <UploadCloud className="w-5 h-5 text-emerald-700" />
          {t('upload.title', 'Ingest Land Record Document')}
        </h2>
        <p className="text-xs text-slate-500 mt-1">
          {t('upload.subtitle', 'Upload historical scanned registers, cadastral maps, Khataunis, or mutation fards. The AI engine automatically detects language, enhances images, extracts structured fields, and validates against Master Revenue Registry.')}
        </p>
      </div>

      {/* Upload and Pipeline Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Metadata & File Upload */}
        <div className="lg:col-span-7 bg-white rounded-xl border border-slate-200 p-6 shadow-xs space-y-5">
          <h3 className="text-sm font-bold text-slate-800 uppercase tracking-wider border-b border-slate-100 pb-2">
            1. Administrative Location & Document Parameters
          </h3>

          <form onSubmit={handleUpload} className="space-y-4 text-xs">
            {/* Hierarchical Cascading Location Picker */}
            <CascadingLocationPicker
              selectedState={formData.state}
              selectedDistrict={formData.district}
              selectedTehsil={formData.tehsil}
              selectedVillage={formData.village}
              onChange={(loc) => setFormData(prev => ({
                ...prev,
                state: loc.state,
                district: loc.district,
                tehsil: loc.tehsil,
                village: loc.village
              }))}
            />

            {/* Document Format & Year */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2 border-t border-slate-100">
              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">
                  {t('upload.docType', 'Document Format Type')} *
                </label>
                <select
                  value={formData.document_type}
                  onChange={(e) => setFormData({ ...formData, document_type: e.target.value })}
                  className="w-full text-xs p-2.5 border border-slate-300 rounded-lg focus:ring-emerald-500 focus:border-emerald-500 bg-white"
                >
                  {DOCUMENT_TYPES.map((d) => (
                    <option key={d.value} value={d.value}>{d.label}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">
                  {t('upload.docYear', 'Fasli / Revenue Year')} *
                </label>
                <input
                  type="number"
                  value={formData.document_year}
                  onChange={(e) => setFormData({ ...formData, document_year: parseInt(e.target.value) || 2024 })}
                  className="w-full text-xs p-2.5 border border-slate-300 rounded-lg focus:ring-emerald-500 focus:border-emerald-500"
                />
              </div>
            </div>

            {/* Automatic Language Detection Notice */}
            <div className="p-3 bg-emerald-50/80 border border-emerald-200 rounded-xl flex items-start gap-2.5 text-[11px] text-emerald-900">
              <Languages className="w-4 h-4 text-emerald-700 shrink-0 mt-0.5" />
              <div>
                <span className="font-bold block">{t('upload.autoDetect', 'Automatic Indic Language Detection')}</span>
                <span className="text-emerald-800">
                  {t('upload.autoDetectDesc', 'The system will automatically recognize the script (Hindi, Tamil, Telugu, Kannada, English, etc.) without manual pre-selection.')}
                </span>
              </div>
            </div>

            {/* Drag and Drop Zone */}
            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1">
                {t('upload.selectFile', 'Select Land Record Document (PDF, PNG, JPG, TIFF)')} *
              </label>
              <div className="border-2 border-dashed border-slate-300 rounded-xl p-6 text-center hover:border-emerald-500 transition-colors bg-slate-50/50">
                <input
                  type="file"
                  id="doc-file-input"
                  onChange={handleFileChange}
                  accept=".pdf,.png,.jpg,.jpeg,.tiff,.tif"
                  className="hidden"
                />
                <label htmlFor="doc-file-input" className="cursor-pointer flex flex-col items-center">
                  <FileText className="w-8 h-8 text-emerald-700 mb-2" />
                  <span className="text-xs font-bold text-slate-900">
                    {file ? file.name : t('upload.dragDrop', 'Drag & drop files here or click to browse')}
                  </span>
                  <span className="text-[11px] text-slate-500 mt-1">
                    Scanned Khatauni, Khasra B1, Patta/Chitta, Adangal or Map Sheet
                  </span>
                </label>
              </div>
            </div>

            {/* Upload Button */}
            <button
              type="submit"
              disabled={!file || uploadedDoc !== null}
              className="w-full py-2.5 px-4 rounded-lg bg-emerald-700 hover:bg-emerald-800 text-white font-bold text-xs flex items-center justify-center gap-2 shadow-xs transition-colors disabled:opacity-50"
            >
              <UploadCloud className="w-4 h-4" />
              {uploadedDoc ? 'Document Uploaded & Registered' : t('upload.uploadBtn', 'Upload Document to Repository')}
            </button>
          </form>
        </div>

        {/* Right Column: AI Pipeline Stage Visualizer */}
        <div className="lg:col-span-5 bg-white rounded-xl border border-slate-200 p-6 shadow-xs flex flex-col justify-between">
          <div className="space-y-4">
            <h3 className="text-sm font-bold text-slate-800 uppercase tracking-wider border-b border-slate-100 pb-2 flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-emerald-700" />
              2. Multilingual AI Processing Pipeline
            </h3>

            {/* Stages List */}
            <div className="space-y-2.5">
              {stages.map((st) => {
                const isCurrent = pipelineStage === st.num;
                const isPassed = pipelineStage > st.num;

                return (
                  <div
                    key={st.num}
                    className={`p-2.5 rounded-lg border text-xs transition-all flex items-start gap-3 ${
                      isPassed
                        ? 'bg-emerald-50/70 border-emerald-200 text-emerald-900'
                        : isCurrent
                        ? 'bg-blue-50/80 border-blue-300 text-blue-900 shadow-2xs'
                        : 'bg-slate-50 border-slate-200 text-slate-400'
                    }`}
                  >
                    <div
                      className={`w-5 h-5 rounded-full flex items-center justify-center font-bold text-[10px] shrink-0 ${
                        isPassed
                          ? 'bg-emerald-700 text-white'
                          : isCurrent
                          ? 'bg-blue-600 text-white animate-pulse'
                          : 'bg-slate-200 text-slate-500'
                      }`}
                    >
                      {isPassed ? '✓' : st.num}
                    </div>
                    <div>
                      <div className="font-bold text-slate-900">{st.label}</div>
                      <div className="text-[10px] text-slate-500 mt-0.5">{st.desc}</div>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Pipeline Execution Result Alert */}
            {pipelineError && <PipelineFailure />}
      {pipelineResult && (
              <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-xl space-y-2 text-xs">
                <div className="flex items-center gap-2 text-emerald-900 font-bold">
                  <CheckCircle2 className="w-4 h-4 text-emerald-700" />
                  {t('documentUpload.pipelineCompleted', 'AI Pipeline Completed Successfully!')}
                </div>
                <div className="grid grid-cols-2 gap-2 text-[11px] text-slate-700 pt-1">
                  <div>
                    <span className="text-slate-500">{t('documentUpload.detectedLanguage', 'Detected Language')}:</span>
                    <span className="ml-1 font-bold text-emerald-800">{pipelineResult.detected_language_name}</span>
                  </div>
                  <div>
                    <span className="text-slate-500">{t('documentUpload.langConfidence', 'Lang Confidence')}:</span>
                    <span className="ml-1 font-bold">{pipelineResult.language_confidence == null ? t('common.notApplicable', 'n/a') : `${(pipelineResult.language_confidence * 100).toFixed(1)}%`}</span>
                  </div>
                  <div>
                    <span className="text-slate-500">{t('documentUpload.ocrConfidence', 'OCR Confidence')}:</span>
                    <span className="ml-1 font-bold">{pipelineResult.ocr_confidence == null ? t('common.notApplicable', 'n/a') : `${(pipelineResult.ocr_confidence * 100).toFixed(1)}%`}</span>
                  </div>
                  <div>
                    <span className="text-slate-500">{t('documentUpload.fieldsExtracted', 'Fields Extracted')}:</span>
                    <span className="ml-1 font-bold">{pipelineResult.fields_extracted}</span>
                  </div>
                </div>

                {pipelineResult.anomalies_found > 0 && (
                  <div className="p-2 bg-amber-100 text-amber-900 rounded font-semibold text-[11px] flex items-center gap-1.5 mt-2">
                    <AlertTriangle className="w-3.5 h-3.5 text-amber-700" />
                    {pipelineResult.anomalies_found} {t('documentUpload.validationMismatch', 'Validation Mismatch Detected (Sent to Verification Queue)')}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Action Trigger */}
          <div className="pt-4 border-t border-slate-100">
            {uploadedDoc && !pipelineResult ? (
              <button
                type="button"
                onClick={handleStartPipeline}
                disabled={pipelineRunning}
                className="w-full py-2.5 px-4 rounded-lg bg-emerald-700 hover:bg-emerald-800 text-white font-bold text-xs flex items-center justify-center gap-2 shadow-xs transition-colors"
              >
                <Sparkles className="w-4 h-4" />
                {pipelineRunning ? t('upload.pipelineRunning', 'Executing AI Multilingual Pipeline...') : t('upload.startAI', 'Start AI Processing Pipeline')}
              </button>
            ) : pipelineResult ? (
              <button
                type="button"
                onClick={() => navigate(`/verification/${uploadedDoc.id}`)}
                className="w-full py-2.5 px-4 rounded-lg bg-slate-900 hover:bg-slate-800 text-white font-bold text-xs flex items-center justify-center gap-2 shadow-xs transition-colors"
              >
                {t('verification.openWorkspace', 'Open Verification Workspace')}
                <ArrowRight className="w-4 h-4" />
              </button>
            ) : (
              <div className="text-center text-[11px] text-slate-400">
                Upload a document file to begin AI digitization pipeline.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
