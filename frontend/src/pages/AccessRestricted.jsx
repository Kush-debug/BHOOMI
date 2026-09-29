import React from 'react';
import { Link } from 'react-router-dom';
import { ShieldAlert } from 'lucide-react';
import { useLanguage } from '../context/LanguageContext';

// Shown when an authenticated user's role does not permit the route they
// navigated to directly (typed URL, bookmark, etc.). Replaces a blank page
// or a raw backend 403 with a plain, non-technical explanation.
export const AccessRestricted = () => {
  const { t } = useLanguage();
  return (
    <div className="flex items-center justify-center min-h-[60vh]">
      <div className="max-w-sm text-center bg-white border border-slate-200 rounded-xl shadow-xs p-8 space-y-4">
        <div className="w-14 h-14 mx-auto rounded-full bg-red-50 border border-red-200 flex items-center justify-center">
          <ShieldAlert className="w-7 h-7 text-red-600" />
        </div>
        <div>
          <h2 className="text-base font-bold text-slate-900">{t('accessRestricted.title', 'Access Restricted')}</h2>
          <p className="text-xs text-slate-500 mt-1.5 leading-relaxed">
            {t('accessRestricted.message', 'You do not have permission to access this section.')}
          </p>
        </div>
        <Link
          to="/"
          className="inline-flex items-center justify-center gap-1.5 px-4 py-2 text-xs font-bold text-white bg-emerald-700 hover:bg-emerald-800 rounded-lg shadow-xs transition-colors"
        >
          {t('accessRestricted.returnToDashboard', 'Return to Dashboard')}
        </Link>
      </div>
    </div>
  );
};
