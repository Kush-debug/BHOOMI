import React, { useState } from 'react';
import { Maximize2, UploadCloud, CheckCircle2, Sparkles, Layers, RefreshCw } from 'lucide-react';
import api from '../services/api';
import { useLanguage } from '../context/LanguageContext';

export const CadastralVectorizer = () => {
  const { t } = useLanguage();
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);

  const handleVectorize = async (e) => {
    e.preventDefault();
    if (!file) return;

    setLoading(true);
    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await api.post('/gis/vectorize-map', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      setResult(res.data);
    } catch (err) {
      console.error(err);
      alert(t('vectorizer.failed', 'Cadastral map vectorization failed.'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-xs">
        <h2 className="text-xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
          <Maximize2 className="w-5 h-5 text-emerald-700" />
          {t('nav.vectorizer', 'Naksha Vectorizer')} (भू-नक्शा डिजिटाइज़र)
        </h2>
        <p className="text-xs text-slate-500 mt-1">
          {t('vectorizer.subtitle', 'Automated parcel contour boundary extraction from historical village map sheets into standard GeoJSON & PostGIS polygons.')}
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Upload Form */}
        <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-xs space-y-4">
          <h3 className="text-sm font-bold text-slate-800 uppercase tracking-wider border-b border-slate-100 pb-2">
            {t('vectorizer.step1', '1. Upload Village Cadastral Map (Sheet)')}
          </h3>

          <form onSubmit={handleVectorize} className="space-y-4">
            <div className="border-2 border-dashed border-slate-300 rounded-xl p-8 text-center hover:border-emerald-500 transition-colors bg-slate-50/50">
              <input
                type="file"
                id="naksha-input"
                onChange={(e) => setFile(e.target.files[0])}
                accept=".jpg,.jpeg,.png,.pdf,.tif,.tiff"
                className="hidden"
              />
              <label htmlFor="naksha-input" className="cursor-pointer flex flex-col items-center">
                <UploadCloud className="w-10 h-10 text-emerald-700 mb-2" />
                <span className="text-xs font-bold text-slate-900">
                  {file ? file.name : t('vectorizer.selectFile', 'Select scanned Cadastral Map image (PNG/JPG/TIFF)')}
                </span>
                <span className="text-[11px] text-slate-500 mt-1">
                  {t('vectorizer.filterDesc', 'OpenCV morphological filter detects parcel boundary lines and plot IDs')}
                </span>
              </label>
            </div>

            <button
              type="submit"
              disabled={loading || !file}
              className="w-full py-2.5 px-4 rounded-lg bg-emerald-700 hover:bg-emerald-800 text-white font-bold text-xs flex items-center justify-center gap-2 shadow-xs transition-colors disabled:opacity-50"
            >
              <Sparkles className="w-4 h-4" />
              {loading ? t('vectorizer.vectorizing', 'Vectorizing Contours & Extracting GeoJSON...') : t('vectorizer.runPipeline', 'Run Contour Vectorization Pipeline')}
            </button>
          </form>
        </div>

        {/* Vectorization Results */}
        <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-xs flex flex-col justify-between">
          <div>
            <h3 className="text-sm font-bold text-slate-800 uppercase tracking-wider border-b border-slate-100 pb-2 mb-4 flex items-center gap-2">
              <Layers className="w-4 h-4 text-emerald-700" /> {t('vectorizer.extractedLayer', 'Extracted Vector Layer (GeoJSON)')}
            </h3>

            {loading ? (
              <div className="py-16 text-center text-slate-500 text-xs">
                <RefreshCw className="w-6 h-6 animate-spin mx-auto text-emerald-700 mb-2" />
                {t('vectorizer.runningSegmentation', 'Running OpenCV contour segmentation and GeoJSON parcel generation...')}
              </div>
            ) : result ? (
              <div className="space-y-3 text-xs animate-in fade-in">
                <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-lg text-emerald-900 font-bold flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-700" />
                  {t('vectorizer.successPrefix', 'Successfully Vectorized')} {result.parcels_detected} {t('vectorizer.successSuffix', 'Cadastral Parcels!')}
                </div>

                <div className="bg-slate-900 text-emerald-400 p-3 rounded-lg font-mono text-[11px] max-h-60 overflow-y-auto">
                  <pre>{JSON.stringify(result.geojson, null, 2)}</pre>
                </div>
              </div>
            ) : (
              <div className="text-center py-16 text-slate-400 text-xs">
                {t('vectorizer.uploadPrompt', 'Upload a cadastral map sheet to preview extracted polygon geometries.')}
              </div>
            )}
          </div>

          {result && (
            <a
              href="/gis"
              className="mt-4 w-full py-2 px-4 rounded-lg bg-slate-900 hover:bg-slate-800 text-white font-bold text-xs flex items-center justify-center gap-2 shadow-xs transition-colors"
            >
              {t('vectorizer.viewInGisMap', 'View Extracted Parcels in GIS Map')} &rarr;
            </a>
          )}
        </div>
      </div>
    </div>
  );
};
