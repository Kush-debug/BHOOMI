import React, { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import {
  ShieldCheck,
  Lock,
  User,
  Sparkles,
  ArrowRight,
  AlertCircle,
  BookOpen,
  Globe
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useLanguage } from '../context/LanguageContext';

export const Login = () => {
  const navigate = useNavigate();
  const { login, isAuthenticated } = useAuth();
  const { t, currentLanguage, changeLanguage, supportedLanguages } = useLanguage();

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (isAuthenticated) {
      navigate('/', { replace: true });
    }
  }, [isAuthenticated, navigate]);

  // Credentials must never ship in the bundle. This block is compiled out unless
  // VITE_ENABLE_DEV_LOGIN=true, which is set only for local development and is
  // false in the Docker build (see docker-compose.yml).
  const DEV_LOGIN_ENABLED = import.meta.env.VITE_ENABLE_DEV_LOGIN === 'true';

  const DEV_ACCOUNTS = DEV_LOGIN_ENABLED
    ? [
        { username: 'superadmin', role: 'Super Administrator' },
        { username: 'admin', role: 'State Administrator' },
        { username: 'district_officer', role: 'District Magistrate' },
        { username: 'tehsil_officer', role: 'Tehsildar' },
        { username: 'verification_officer', role: 'Verification Officer' },
        { username: 'viewer', role: 'Public Viewer' }
      ]
    : [];

  // Fills the username only. The password is always typed by the person signing in.
  const handleDevAccountSelect = (account) => {
    setUsername(account.username);
    setError('');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    const res = await login(username, password);
    setLoading(false);

    if (res && res.success) {
      navigate('/', { replace: true });
    } else {
      setError(res?.error || 'Invalid username or password.');
    }
  };

  return (
    <div className="min-h-screen bg-slate-900 flex flex-col justify-between text-slate-100 relative overflow-hidden">
      {/* Background Graphic Accents */}
      <div className="absolute top-0 right-0 w-96 h-96 bg-emerald-500/10 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute bottom-0 left-0 w-96 h-96 bg-blue-500/10 rounded-full blur-3xl pointer-events-none" />

      {/* Top Bar with Language Selector */}
      <header className="px-6 py-4 flex items-center justify-between border-b border-slate-800 bg-slate-900/80 backdrop-blur-xs relative z-10">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-emerald-600 flex items-center justify-center font-black text-lg text-white">
            भू
          </div>
          <div>
            <h1 className="font-extrabold text-white text-base tracking-tight">
              {t('header.title', 'Bhoomi AI')}
            </h1>
            <p className="text-[10px] text-slate-400">
              {t('header.gov', 'Govt of India / Revenue Department')}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Globe className="w-4 h-4 text-emerald-400" />
          <select
            value={currentLanguage}
            onChange={(e) => changeLanguage(e.target.value)}
            className="text-xs bg-slate-800 border border-slate-700 text-white rounded-lg px-2.5 py-1.5 focus:ring-emerald-500 focus:border-emerald-500 font-bold"
          >
            {supportedLanguages.map((l) => (
              <option key={l.code} value={l.code}>
                {l.flag} {l.native} ({l.name})
              </option>
            ))}
          </select>
        </div>
      </header>

      {/* Main Login Card */}
      <main className="flex-1 flex items-center justify-center p-4 relative z-10">
        <div className="w-full max-w-md bg-white text-slate-900 rounded-2xl border border-slate-200 shadow-2xl p-6 sm:p-8 space-y-6">
          <div className="text-center space-y-1">
            <div className="inline-flex p-3 rounded-2xl bg-emerald-50 text-emerald-800 mb-2">
              <ShieldCheck className="w-7 h-7" />
            </div>
            <h2 className="text-lg font-bold text-slate-900 tracking-tight">
              {t('login.title', 'Government Land Record Verification Portal')}
            </h2>
            <p className="text-xs text-slate-500">
              {t('login.subtitle', 'Sign in to access AI-powered digitization, validation and cadastral GIS workflows.')}
            </p>
          </div>

          {error && (
            <div className="p-3 bg-rose-50 border border-rose-200 text-rose-800 rounded-xl text-xs font-semibold flex items-center gap-2 animate-in fade-in">
              <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4 text-xs">
            <div>
              <label className="block font-bold text-slate-700 mb-1">
                {t('login.username', 'Username or Government Email')}
              </label>
              <div className="relative">
                <User className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
                <input
                  type="text"
                  required
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="e.g. verification_officer"
                  className="w-full pl-9 pr-3 py-2.5 border border-slate-300 rounded-xl focus:ring-emerald-500 focus:border-emerald-500 text-xs"
                />
              </div>
            </div>

            <div>
              <label className="block font-bold text-slate-700 mb-1">
                {t('login.password', 'Password')}
              </label>
              <div className="relative">
                <Lock className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full pl-9 pr-3 py-2.5 border border-slate-300 rounded-xl focus:ring-emerald-500 focus:border-emerald-500 text-xs"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 px-4 rounded-xl bg-emerald-700 hover:bg-emerald-800 text-white font-bold text-xs flex items-center justify-center gap-2 shadow-xs transition-colors disabled:opacity-50"
            >
              <Sparkles className="w-4 h-4" />
              {loading ? 'Authenticating Credentials...' : t('login.signIn', 'Sign In to Secure Portal')}
            </button>
          </form>

          {DEV_LOGIN_ENABLED && (
            <div className="pt-4 border-t border-slate-100 space-y-2">
              <span className="text-[10px] font-bold uppercase text-amber-600 block text-center">
                Development accounts &mdash; username only, password required
              </span>
              <div className="grid grid-cols-2 gap-1.5 text-[11px]">
                {DEV_ACCOUNTS.map((a) => (
                  <button
                    key={a.username}
                    type="button"
                    onClick={() => handleDevAccountSelect(a)}
                    className={`p-1.5 rounded-lg border text-left transition-colors truncate ${
                      username === a.username
                        ? 'border-emerald-500 bg-emerald-50 text-emerald-900 font-bold'
                        : 'border-slate-200 hover:bg-slate-50 text-slate-700'
                    }`}
                    title={a.role}
                  >
                    <span className="block truncate font-mono text-[10px]">{a.username}</span>
                    <span className="text-[9px] text-slate-500 block truncate">{a.role}</span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Way in for anyone without an account - the public story page
              explains what this system does before asking them to sign in. */}
          <div className="pt-4 border-t border-slate-100 text-center">
            <Link
              to="/story"
              className="inline-flex items-center gap-1.5 text-[11px] font-bold text-emerald-700 hover:text-emerald-800"
            >
              <BookOpen className="w-3.5 h-3.5" />
              New here? See what Bhoomi AI does
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>
        </div>
      </main>

      {/* Footer - describes the context these schemes provide, without claiming
          affiliation with or certification by any of them. */}
      <footer className="py-3 px-6 text-center text-[10px] text-slate-500 border-t border-slate-800">
        Built for the Digital India Land Records Modernization Programme (DILRMP) context &bull; SIH 2026 prototype, Problem Statement 26018
      </footer>
    </div>
  );
};
