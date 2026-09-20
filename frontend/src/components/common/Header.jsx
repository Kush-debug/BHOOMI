import React, { useState } from 'react';
import {
  Bell,
  Globe,
  User,
  LogOut,
  Shield,
  Layers,
  ChevronDown,
  CheckCircle2,
  Sparkles
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { useLanguage } from '../../context/LanguageContext';
import { NotificationDrawer } from './NotificationDrawer';

const ROLE_LABEL_KEYS = {
  super_admin: 'header.roleSuperAdmin',
  admin: 'header.roleAdmin',
  district_officer: 'header.roleDistrictOfficer',
  tehsil_officer: 'header.roleTehsilOfficer',
  verification_officer: 'header.roleVerificationOfficer',
  viewer: 'header.roleViewer'
};

export const Header = () => {
  const { user, logout } = useAuth();
  const { currentLanguage, changeLanguage, supportedLanguages, t } = useLanguage();
  const [notifOpen, setNotifOpen] = useState(false);
  const [langMenuOpen, setLangMenuOpen] = useState(false);

  return (
    <header className="h-16 bg-white border-b border-slate-200 sticky top-0 z-30 px-4 sm:px-6 flex items-center justify-between shadow-2xs">
      {/* Left: Branding & Govt Identity */}
      <div className="flex items-center gap-3">
        <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-emerald-800 text-white font-black text-xl shadow-xs">
          भू
        </div>
        <div>
          <div className="flex items-center gap-2">
            <span className="font-extrabold text-slate-900 tracking-tight text-base sm:text-lg">
              {t('header.title', 'Bhoomi AI')}
            </span>
            <span className="hidden sm:inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-50 text-emerald-800 border border-emerald-200">
              <Sparkles className="w-2.5 h-2.5 text-emerald-600" /> {t('header.indicOcrBadge', 'Indic OCR & Validation')}
            </span>
          </div>
          <p className="text-[11px] text-slate-500 hidden md:block">
            {t('header.subtitle', 'National Land Record Modernization & AI Intelligence Platform')}
          </p>
        </div>
      </div>

      {/* Right Controls */}
      <div className="flex items-center gap-2 sm:gap-3">
        {/* Multilingual UI Language Selector */}
        <div className="relative">
          <button
            onClick={() => setLangMenuOpen(!langMenuOpen)}
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border border-slate-200 bg-slate-50 hover:bg-slate-100 text-slate-700 text-xs font-bold transition-colors"
            title={t('header.switchLanguage', 'Switch Portal Language')}
          >
            <Globe className="w-3.5 h-3.5 text-emerald-700" />
            <span className="hidden sm:inline">
              {supportedLanguages.find(l => l.code === currentLanguage)?.native || 'English'}
            </span>
            <ChevronDown className="w-3 h-3 text-slate-400" />
          </button>

          {langMenuOpen && (
            <div className="absolute right-0 mt-1.5 w-48 bg-white rounded-xl shadow-lg border border-slate-200 py-1.5 z-50 text-xs animate-in fade-in">
              <div className="px-3 py-1 text-[10px] font-bold uppercase text-slate-400 border-b border-slate-100">
                {t('header.language', 'Select UI Language')}
              </div>
              <div className="max-h-60 overflow-y-auto py-1">
                {supportedLanguages.map((lang) => (
                  <button
                    key={lang.code}
                    onClick={() => {
                      changeLanguage(lang.code);
                      setLangMenuOpen(false);
                    }}
                    className={`w-full px-3 py-2 text-left flex items-center justify-between hover:bg-slate-50 transition-colors ${
                      currentLanguage === lang.code ? 'font-bold text-emerald-800 bg-emerald-50/50' : 'text-slate-700'
                    }`}
                  >
                    <span className="flex items-center gap-2">
                      <span>{lang.flag}</span>
                      <span>{lang.native} ({lang.name})</span>
                    </span>
                    {currentLanguage === lang.code && (
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-700" />
                    )}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* In-App Notifications Bell */}
        <button
          onClick={() => setNotifOpen(true)}
          className="relative p-2 rounded-lg text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition-colors"
          title={t('header.notifications', 'Notifications')}
        >
          <Bell className="w-4 h-4" />
          <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-rose-500 rounded-full ring-2 ring-white animate-pulse" />
        </button>

        {/* User Info & Role Badge */}
        {user && (
          <div className="flex items-center gap-2 pl-2 border-l border-slate-200">
            <div className="w-8 h-8 rounded-full bg-emerald-100 text-emerald-800 flex items-center justify-center font-bold text-xs">
              {user.full_name?.charAt(0) || 'U'}
            </div>
            <div className="hidden lg:block text-left text-xs">
              <div className="font-bold text-slate-900 truncate max-w-[150px]">
                {user.full_name}
              </div>
              <div className="text-[10px] text-slate-500 flex items-center gap-1">
                <span className="capitalize font-mono text-emerald-700 font-bold">
                  {ROLE_LABEL_KEYS[user.role] ? t(ROLE_LABEL_KEYS[user.role], user.role.replace('_', ' ')) : user.role.replace('_', ' ')}
                </span>
              </div>
            </div>
            <button
              onClick={logout}
              className="p-1.5 rounded-lg text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition-colors ml-1"
              title={t('header.logout', 'Sign Out')}
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        )}
      </div>

      <NotificationDrawer isOpen={notifOpen} onClose={() => setNotifOpen(false)} />
    </header>
  );
};
