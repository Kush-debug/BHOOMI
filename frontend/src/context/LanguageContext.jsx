import React, { createContext, useContext, useState, useEffect } from 'react';
import enTranslations from '../locales/en.json';
import hiTranslations from '../locales/hi.json';
import taTranslations from '../locales/ta.json';
import teTranslations from '../locales/te.json';
import knTranslations from '../locales/kn.json';
import mrTranslations from '../locales/mr.json';
import bnTranslations from '../locales/bn.json';
import guTranslations from '../locales/gu.json';
import paTranslations from '../locales/pa.json';
import mlTranslations from '../locales/ml.json';
import orTranslations from '../locales/or.json';
import asTranslations from '../locales/as.json';

const LanguageContext = createContext();

const SUPPORTED_LANGUAGES = [
  { code: 'en', name: 'English', native: 'English', flag: '🇬🇧' },
  { code: 'hi', name: 'Hindi', native: 'हिन्दी', flag: '🇮🇳' },
  { code: 'ta', name: 'Tamil', native: 'தமிழ்', flag: '🇮🇳' },
  { code: 'te', name: 'Telugu', native: 'తెలుగు', flag: '🇮🇳' },
  { code: 'kn', name: 'Kannada', native: 'ಕನ್ನಡ', flag: '🇮🇳' },
  { code: 'mr', name: 'Marathi', native: 'मराठी', flag: '🇮🇳' },
  { code: 'bn', name: 'Bengali', native: 'বাংলা', flag: '🇮🇳' },
  { code: 'gu', name: 'Gujarati', native: 'ગુજરાતી', flag: '🇮🇳' },
  { code: 'pa', name: 'Punjabi', native: 'ਪੰਜਾਬੀ', flag: '🇮🇳' },
  { code: 'ml', name: 'Malayalam', native: 'മലയാളം', flag: '🇮🇳' },
  { code: 'or', name: 'Odia', native: 'ଓଡ଼ିଆ', flag: '🇮🇳' },
  { code: 'as', name: 'Assamese', native: 'অসমীয়া', flag: '🇮🇳' }
];

const TRANSLATION_CATALOGS = {
  en: enTranslations,
  hi: hiTranslations,
  ta: taTranslations,
  te: teTranslations,
  kn: knTranslations,
  mr: mrTranslations,
  bn: bnTranslations,
  gu: guTranslations,
  pa: paTranslations,
  ml: mlTranslations,
  or: orTranslations,
  as: asTranslations
};

// Dev-only: warn once per (language, key) pair instead of spamming the console.
const warnedMissingKeys = new Set();
const warnMissingKey = (language, keyPath) => {
  if (!import.meta.env.DEV) return;
  const warnKey = `${language}::${keyPath}`;
  if (warnedMissingKeys.has(warnKey)) return;
  warnedMissingKeys.add(warnKey);
  // eslint-disable-next-line no-console
  console.warn(`[i18n] Missing translation:\n  language=${language}\n  key=${keyPath}`);
};

const resolveKey = (catalog, keys) => {
  let val = catalog;
  for (const k of keys) {
    if (val && typeof val === 'object' && k in val) {
      val = val[k];
    } else {
      return undefined;
    }
  }
  return typeof val === 'string' ? val : undefined;
};

export const LanguageProvider = ({ children }) => {
  const [currentLanguage, setCurrentLanguage] = useState(() => {
    return localStorage.getItem('bhoomi_ui_language') || 'en';
  });

  useEffect(() => {
    document.documentElement.lang = currentLanguage;
  }, [currentLanguage]);

  const changeLanguage = (langCode) => {
    setCurrentLanguage(langCode);
    localStorage.setItem('bhoomi_ui_language', langCode);
  };

  const t = (keyPath, fallback = '') => {
    const keys = keyPath.split('.');

    // Selected language catalog (falls back to English catalog only if the
    // whole language is unregistered, never silently for a single key).
    const catalog = TRANSLATION_CATALOGS[currentLanguage];
    const val = catalog ? resolveKey(catalog, keys) : undefined;
    if (val !== undefined) return val;

    // Missing in the current language: fall back to English for this key only.
    if (currentLanguage !== 'en') {
      warnMissingKey(currentLanguage, keyPath);
    }
    const enVal = resolveKey(TRANSLATION_CATALOGS.en, keys);
    if (enVal !== undefined) return enVal;

    // Missing everywhere, including English: use caller fallback or the key path.
    warnMissingKey('en', keyPath);
    return fallback || keyPath;
  };

  return (
    <LanguageContext.Provider value={{
      currentLanguage,
      changeLanguage,
      supportedLanguages: SUPPORTED_LANGUAGES,
      t
    }}>
      {children}
    </LanguageContext.Provider>
  );
};

export const useLanguage = () => {
  const context = useContext(LanguageContext);
  if (!context) {
    throw new Error('useLanguage must be used within a LanguageProvider');
  }
  return context;
};
