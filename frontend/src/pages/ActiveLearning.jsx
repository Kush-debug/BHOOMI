import React, { useState, useEffect } from 'react';
import { BrainCircuit, BookOpen, CheckCircle2, Download, RefreshCw } from 'lucide-react';
import api from '../services/api';
import { useLanguage } from '../context/LanguageContext';

export const ActiveLearning = () => {
  const { t } = useLanguage();
  const [corrections, setCorrections] = useState([]);
  const [terminology, setTerminology] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [corrRes, termRes] = await Promise.all([
        api.get('/learning/corrections'),
        api.get('/learning/terminology')
      ]);
      setCorrections(corrRes.data);
      setTerminology(termRes.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-xs">
        <h2 className="text-xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
          <BrainCircuit className="w-5 h-5 text-emerald-700" />
          {t('nav.learning', 'Active Learning & State Terminology Dictionary Hub')}
        </h2>
        <p className="text-xs text-slate-500 mt-1">
          {t('activeLearning.subtitle', 'Human-in-the-loop training corrections captured for future OCR fine-tuning, active learning, and multi-state revenue terminology aliases.')}
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Verified Corrections */}
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs space-y-4">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-700" /> {t('activeLearning.verifiedPairs', 'Verified Training Pairs')} ({corrections.length})
            </h3>
            <span className="text-[10px] text-slate-500 font-mono">{t('activeLearning.fineTuningDataset', 'Fine-Tuning Dataset')}</span>
          </div>

          <div className="space-y-2.5 max-h-[500px] overflow-y-auto">
            {corrections.length === 0 ? (
              <div className="text-center py-12 text-slate-400 text-xs">{t('activeLearning.noCorrections', 'No human corrections recorded yet.')}</div>
            ) : (
              corrections.map((c) => (
                <div key={c.id} className="p-3 rounded-lg border border-slate-200 bg-slate-50 text-xs space-y-1">
                  <div className="flex items-center justify-between font-bold text-slate-900">
                    <span className="font-mono text-emerald-800">{c.field_name}</span>
                    <span className="text-[10px] text-slate-400">{t('dashboard.docNumberPrefix', 'Doc #')}{c.document_id}</span>
                  </div>
                  <div className="flex items-center gap-3 font-mono text-[11px] pt-1">
                    <span className="text-red-700 line-through">{t('activeLearning.aiLabel', 'AI')}: {c.original_value || t('activeLearning.none', 'None')}</span>
                    <span className="text-emerald-700 font-bold">{t('activeLearning.officerLabel', 'Officer')}: {c.corrected_value}</span>
                  </div>
                  {c.notes && <div className="text-[10px] text-slate-500 italic mt-1">{c.notes}</div>}
                </div>
              ))
            )}
          </div>
        </div>

        {/* State Terminology Dictionary */}
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs space-y-4">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
              <BookOpen className="w-4 h-4 text-blue-700" /> {t('activeLearning.terminologyMapping', 'Multi-State Terminology Mapping')}
            </h3>
            <span className="text-[10px] text-slate-500 font-mono">{t('activeLearning.devanagariRegional', 'Devanagari & Regional')}</span>
          </div>

          <div className="space-y-3 text-xs max-h-[500px] overflow-y-auto">
            {terminology && Object.entries(terminology.dictionary).map(([key, def]) => (
              <div key={key} className="p-3 rounded-lg border border-slate-200 bg-white">
                <div className="flex items-center justify-between font-bold text-slate-900">
                  <span>{def.display_name_en}</span>
                  <span className="font-mono text-[10px] text-slate-500">{key}</span>
                </div>
                <div className="text-emerald-700 font-semibold mt-0.5 text-[11px]">{def.display_name_hi}</div>
                <div className="mt-1.5 flex flex-wrap gap-1">
                  {def.aliases.map((alias, i) => (
                    <span key={i} className="px-1.5 py-0.5 bg-slate-100 text-slate-700 rounded text-[10px] border border-slate-200">
                      {alias}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
