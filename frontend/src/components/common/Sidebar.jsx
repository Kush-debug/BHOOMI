import React, { useEffect, useState } from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  UploadCloud,
  CheckSquare,
  Database,
  Compass,
  Radar,
  Map,
  Layers,
  AlertTriangle,
  BarChart3,
  ShieldCheck,
  BrainCircuit,
  Settings,
  Users
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { useLanguage } from '../../context/LanguageContext';
import api from '../../services/api';

// Mirrors backend/app/auth/rbac.py's role names, so this reads as policy
// rather than as a scattered set of `role !== 'viewer'` checks (the backend
// enforces every one of these independently - this list only decides what
// the sidebar offers to click).
const SUPER_ADMIN = 'super_admin';
const ADMIN = 'admin';
const DISTRICT_OFFICER = 'district_officer';
const TEHSIL_OFFICER = 'tehsil_officer';
const VERIFICATION_OFFICER = 'verification_officer';
const VIEWER = 'viewer';
const STAFF_ROLES = [SUPER_ADMIN, ADMIN, DISTRICT_OFFICER, TEHSIL_OFFICER, VERIFICATION_OFFICER];
const ALL_ROLES = [...STAFF_ROLES, VIEWER];

// One row per nav item: `roles` is the exhaustive list of roles that may see
// it. Adding a new role-gated page means adding its roles here, not
// threading another boolean through the component.
const NAV_CONFIG = [
  { to: '/', labelKey: 'nav.dashboard', label: 'Dashboard', icon: LayoutDashboard, exact: true, roles: ALL_ROLES },
  { to: '/upload', labelKey: 'nav.upload', label: 'Document Upload', icon: UploadCloud, roles: STAFF_ROLES },
  { to: '/verification', labelKey: 'nav.verification', label: 'Verification Queue', icon: CheckSquare, roles: STAFF_ROLES },
  { to: '/records', labelKey: 'nav.registry', label: 'Land Registry', icon: Database, roles: ALL_ROLES },
  { to: '/parcels', labelKey: 'nav.parcels', label: 'Parcel Intelligence', icon: Compass, roles: STAFF_ROLES },
  { to: '/investigations', labelKey: 'nav.investigations', label: 'Investigation Center', icon: Radar, roles: STAFF_ROLES },
  { to: '/gis', labelKey: 'nav.gisMap', label: 'Cadastral GIS Map', icon: Map, roles: ALL_ROLES },
  { to: '/vectorizer', labelKey: 'nav.vectorizer', label: 'Naksha Vectorizer', icon: Layers, roles: STAFF_ROLES },
  { to: '/validation', labelKey: 'nav.validation', label: 'Validation Center', icon: AlertTriangle, roles: STAFF_ROLES },
  { to: '/reports', labelKey: 'nav.reports', label: 'Digitization Reports', icon: BarChart3, roles: STAFF_ROLES },
  { to: '/audit', labelKey: 'nav.audit', label: 'Audit Trail Logs', icon: ShieldCheck, roles: STAFF_ROLES },
  { to: '/learning', labelKey: 'nav.learning', label: 'Active Learning Hub', icon: BrainCircuit, roles: STAFF_ROLES },
  { to: '/admin/users', labelKey: 'nav.admin', label: 'Admin Management', icon: Users, roles: [SUPER_ADMIN, ADMIN] },
  { to: '/settings', labelKey: 'nav.settings', label: 'Settings', icon: Settings, roles: ALL_ROLES }
];

export const Sidebar = () => {
  const { user } = useAuth();
  const { t } = useLanguage();
  const isViewer = user?.role === VIEWER;

  // The footer used to claim "13+ Indic Languages Online" with a live status dot
  // regardless of what was actually installed. It now reports what the server
  // says it can do. /processing/engine-status is staff-only (CAN_READ_DOCUMENTS
  // in rbac.py) and is internal processing-pipeline information the viewer
  // portal must not surface (BHUMI_FORENSICS viewer spec §3/§9) - skipped
  // entirely for that role rather than fetched and hidden with CSS.
  const [ocr, setOcr] = useState(null);
  useEffect(() => {
    if (isViewer) return undefined;
    let alive = true;
    api
      .get('/processing/engine-status')
      .then((res) => alive && setOcr(res.data))
      .catch(() => alive && setOcr({ available: false, supported_iso_languages: [] }));
    return () => {
      alive = false;
    };
  }, [isViewer]);

  const navItems = NAV_CONFIG.filter((item) => user?.role && item.roles.includes(user.role)).map((item) => ({
    ...item,
    label: t(item.labelKey, item.label)
  }));

  return (
    <aside className="w-64 bg-slate-900 text-slate-300 flex flex-col h-[calc(100vh-4rem)] sticky top-16 select-none shrink-0">
      {/* Navigation List */}
      <nav className="flex-1 py-4 px-3 space-y-1 overflow-y-auto">
        <div className="px-3 pb-2 text-[10px] font-bold uppercase tracking-wider text-slate-500">
          {t('sidebar.mainNavigation', 'Main Navigation')}
        </div>

        {navItems.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.exact}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-xs font-semibold transition-colors ${
                  isActive
                    ? 'bg-emerald-700 text-white shadow-xs'
                    : 'text-slate-300 hover:bg-slate-800 hover:text-white'
                }`
              }
            >
              <Icon className="w-4 h-4 shrink-0" />
              <span>{item.label}</span>
            </NavLink>
          );
        })}
      </nav>

      {/* OCR engine status - reported by the server, not asserted by the UI.
          Internal processing-pipeline detail: not shown to the viewer role. */}
      {!isViewer && (
      <div className="p-3 border-t border-slate-800 text-[11px] space-y-2">
        <div className="bg-slate-800/80 p-2.5 rounded-lg border border-slate-700">
          <div className="flex items-center justify-between text-slate-400 text-[10px] font-bold uppercase">
            <span>{t('sidebar.ocrEngine', 'OCR engine')}</span>
            <span
              className={`w-2 h-2 rounded-full ${
                ocr === null ? 'bg-slate-500' : ocr.available ? 'bg-emerald-400' : 'bg-red-500'
              }`}
            />
          </div>
          {ocr === null ? (
            <div className="text-slate-400 mt-1 text-xs">{t('sidebar.checking', 'Checking...')}</div>
          ) : ocr.available ? (
            <>
              <div className="text-emerald-400 font-bold mt-1 text-xs">
                {ocr.engine} {ocr.version}
              </div>
              <div className="text-slate-400 text-[10px]">
                {ocr.supported_language_count} {ocr.supported_language_count === 1 ? t('sidebar.languageSingular', 'language') : t('sidebar.languagePlural', 'languages')} {t('sidebar.installed', 'installed')}
                {ocr.supported_iso_languages?.length
                  ? `: ${ocr.supported_iso_languages.join(', ')}`
                  : ''}
              </div>
            </>
          ) : (
            <>
              <div className="text-red-400 font-bold mt-1 text-xs">{t('sidebar.unavailable', 'Unavailable')}</div>
              <div className="text-slate-400 text-[10px]">
                {t('sidebar.processingWillError', 'Document processing will report an error rather than produce output.')}
              </div>
            </>
          )}
        </div>
      </div>
      )}
    </aside>
  );
};
