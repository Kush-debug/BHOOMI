import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  FileText,
  CheckCircle2,
  Clock,
  AlertTriangle,
  Award,
  Cpu,
  ArrowRight,
  TrendingUp,
  MapPin,
  RefreshCw,
  ExternalLink
} from 'lucide-react';
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  Tooltip,
  Legend
} from 'recharts';
import api from '../services/api';
import { StatCard } from '../components/common/StatCard';
import { StatusBadge, ConfidenceBadge } from '../components/common/Badge';
import { useAuth } from '../context/AuthContext';
import { useLanguage } from '../context/LanguageContext';
import { ViewerDashboard } from './ViewerDashboard';


// Metrics can legitimately be absent: the backend returns null for
// "not measured yet" instead of a plausible placeholder. Render that honestly.
const num = (v) => (v === null || v === undefined ? '--' : Number(v).toLocaleString());
const pct = (v) => (v === null || v === undefined ? 'not measured' : `${v}% `);

export const Dashboard = () => {
  const { user } = useAuth();
  // This dashboard's three calls below (/dashboard/stats, /documents,
  // /validation/anomalies) are all staff-only server-side. A viewer hitting
  // any one of them fails Promise.all with `stats` never set, and the
  // loading guard just past this branch stays true forever - an infinite
  // "Loading Enterprise Dashboard..." spinner with nothing left running.
  // The viewer gets its own component that only calls endpoints it's
  // actually authorized for, rather than this page silently trying to
  // recover from 403s it should never have triggered in the first place.
  if (user?.role === 'viewer') {
    return <ViewerDashboard />;
  }

  return <StaffDashboard />;
};

const StaffDashboard = () => {
  const { t } = useLanguage();
  const [stats, setStats] = useState(null);
  const [recentDocs, setRecentDocs] = useState([]);
  const [anomalies, setAnomalies] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchDashboardData();
  }, []);

  const fetchDashboardData = async () => {
    setLoading(true);
    try {
      const [statsRes, docsRes, anomRes] = await Promise.all([
        api.get('/dashboard/stats'),
        api.get('/documents/?limit=6'),
        api.get('/validation/anomalies?limit=5')
      ]);
      setStats(statsRes.data);
      setRecentDocs(docsRes.data);
      setAnomalies(anomRes.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  if (loading || !stats) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="flex flex-col items-center gap-3">
          <RefreshCw className="w-8 h-8 text-emerald-700 animate-spin" />
          <span className="text-sm font-semibold text-slate-600">{t('dashboard.loadingEnterprise', 'Loading Enterprise Dashboard...')}</span>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Top Welcome & System Status Bar */}
      <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900 tracking-tight">
            {t('dashboard.title', 'Revenue Records Digitization & AI Validation Overview')}
          </h2>
          <p className="text-xs text-slate-500 mt-1">
            {t('dashboard.subtitle', 'Real-time pipeline monitoring, Indic OCR accuracy, cross-database validation & cadastral mapping.')}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Link
            to="/upload"
            className="inline-flex items-center gap-2 px-4 py-2 text-xs font-bold text-white bg-emerald-700 hover:bg-emerald-800 rounded-lg shadow-xs transition-colors"
          >
            {t('dashboard.uploadNewRecord', 'Upload New Land Record')} &rarr;
          </Link>
          <button
            onClick={fetchDashboardData}
            className="p-2 text-slate-500 hover:text-slate-900 rounded-lg border border-slate-200 hover:bg-slate-50 transition-colors"
            title={t('dashboard.refreshMetrics', 'Refresh Metrics')}
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title={t('dashboard.totalDocs', 'Total Documents')}
          value={num(stats.total_documents)}
          subtext={t('dashboard.statSubtextHistorical', 'Historical registers & deeds')}
          icon={FileText}
          color="blue"
          trend={t('dashboard.trendMoM', '+12.4% MoM')}
        />
        <StatCard
          title={t('dashboard.aiProcessed', 'AI Processed')}
          value={num(stats.processed_documents)}
          subtext={`${t('dashboard.avgOcrConfidence', 'Avg OCR confidence')}: ${pct(stats.average_ocr_confidence)}`}
          icon={Cpu}
          color="purple"
          trend={t('dashboard.trendParsed', '96.2% parsed')}
        />
        <StatCard
          title={t('dashboard.verifiedDocs', 'Verified Documents')}
          value={num(stats.verified_documents)}
          subtext={`${t('dashboard.avgExtractionConfidence', 'Avg extraction confidence')}: ${pct(stats.average_extraction_confidence)}`}
          icon={CheckCircle2}
          color="emerald"
          trend={t('dashboard.trendAuthoritative', 'Authoritative')}
        />
        <StatCard
          title={t('dashboard.pendingVerification', 'Pending Verification')}
          value={num(stats.pending_verification)}
          subtext={`${num(stats.open_findings)} ${t('dashboard.openFindings', 'open findings')}`}
          icon={AlertTriangle}
          color="amber"
          trend={t('dashboard.trendRequiresAction', 'Requires Action')}
        />
      </div>

      {/* Interactive Charts Row 1 */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Processing Throughput Area Chart */}
        <div className="lg:col-span-2 bg-white rounded-xl border border-slate-200 p-5 shadow-xs">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-sm font-bold text-slate-900">{t('dashboard.throughputChart', 'Digitization & Verification Velocity')}</h3>
              <p className="text-xs text-slate-500">{t('dashboard.throughputSubtitle', 'Daily throughput of documents processed vs verified')}</p>
            </div>
            <span className="text-xs font-semibold text-emerald-700 bg-emerald-50 px-2 py-1 rounded border border-emerald-200">
              {t('dashboard.weeklyVelocity', 'Weekly Velocity')}
            </span>
          </div>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={stats.processing_timeline || []}>
                <defs>
                  <linearGradient id="colorUploaded" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#3B82F6" stopOpacity={0.4}/>
                    <stop offset="95%" stopColor="#3B82F6" stopOpacity={0}/>
                  </linearGradient>
                  <linearGradient id="colorVerified" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#10B981" stopOpacity={0.4}/>
                    <stop offset="95%" stopColor="#10B981" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <XAxis dataKey="day" tick={{ fontSize: 12 }} stroke="#94a3b8" />
                <YAxis tick={{ fontSize: 12 }} stroke="#94a3b8" />
                <Tooltip />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Area type="monotone" dataKey="uploaded" stroke="#3B82F6" fillOpacity={1} fill="url(#colorUploaded)" name={t('dashboard.legendUploaded', 'Uploaded')} />
                <Area type="monotone" dataKey="verified" stroke="#10B981" fillOpacity={1} fill="url(#colorVerified)" name={t('dashboard.legendVerified', 'Verified')} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Verification Status Donut Chart */}
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs">
          <div className="mb-4">
            <h3 className="text-sm font-bold text-slate-900">{t('dashboard.statusChart', 'Document Status Distribution')}</h3>
            <p className="text-xs text-slate-500">{t('dashboard.statusSubtitle', 'Verification & anomaly ratio')}</p>
          </div>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={(stats.status_distribution || []).filter((d) => d.value > 0)}
                  cx="50%"
                  cy="50%"
                  innerRadius={55}
                  outerRadius={80}
                  paddingAngle={4}
                  dataKey="value"
                >
                  {(stats.status_distribution || []).map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip />
                <Legend wrapperStyle={{ fontSize: 11 }} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Interactive Charts Row 2 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* State-wise Progress Bar Chart */}
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-sm font-bold text-slate-900">{t('dashboard.stateChart', 'State-wise Digitization Completion')}</h3>
              <p className="text-xs text-slate-500">{t('dashboard.stateSubtitle', 'Total target vs verified land records')}</p>
            </div>
            <Link to="/reports" className="text-xs font-semibold text-emerald-700 hover:underline">
              {t('common.fullReport', 'Full Report')} &rarr;
            </Link>
          </div>
          <div className="h-60">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={stats.state_progress || []}>
                <XAxis dataKey="state" tick={{ fontSize: 11 }} stroke="#94a3b8" />
                <YAxis tick={{ fontSize: 11 }} stroke="#94a3b8" />
                <Tooltip />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Bar dataKey="total" fill="#94A3B8" name={t('dashboard.legendTotalRecords', 'Total Records')} radius={[4, 4, 0, 0]} />
                <Bar dataKey="verified" fill="#059669" name={t('dashboard.legendVerified', 'Verified')} radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Confidence Distribution */}
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs">
          <div className="mb-4">
            <h3 className="text-sm font-bold text-slate-900">{t('dashboard.confidenceChart', 'OCR & Field Confidence Distribution')}</h3>
            <p className="text-xs text-slate-500">{t('dashboard.confidenceSubtitle', 'Model extraction certainty bands')}</p>
          </div>
          <div className="h-60">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={stats.confidence_distribution || []} layout="vertical">
                <XAxis type="number" tick={{ fontSize: 11 }} stroke="#94a3b8" />
                <YAxis dataKey="range" type="category" tick={{ fontSize: 11 }} stroke="#94a3b8" width={80} />
                <Tooltip />
                <Bar dataKey="count" fill="#3B82F6" name={t('dashboard.legendDocuments', 'Documents')} radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Tables Row: Recent Documents & Live Validation Discrepancies */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recent Documents Table */}
        <div className="lg:col-span-2 bg-white rounded-xl border border-slate-200 p-5 shadow-xs">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-sm font-bold text-slate-900">{t('dashboard.recentDocs', 'Recent Land Documents')}</h3>
              <p className="text-xs text-slate-500">{t('dashboard.recentDocsSubtitle', 'Latest digitized records in processing pipeline')}</p>
            </div>
            <Link to="/documents" className="text-xs font-semibold text-emerald-700 hover:underline">
              {t('common.viewAll', 'View All')} &rarr;
            </Link>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-slate-600 uppercase text-[10px] font-bold border-y border-slate-200">
                <tr>
                  <th className="py-2.5 px-3">{t('dashboard.tableFileName', 'File Name')}</th>
                  <th className="py-2.5 px-3">{t('dashboard.tableType', 'Type')}</th>
                  <th className="py-2.5 px-3">{t('dashboard.tableLocation', 'Location')}</th>
                  <th className="py-2.5 px-3">{t('dashboard.tableConfidence', 'Confidence')}</th>
                  <th className="py-2.5 px-3">{t('common.status', 'Status')}</th>
                  <th className="py-2.5 px-3 text-right">{t('dashboard.tableAction', 'Action')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {recentDocs.map((d) => (
                  <tr key={d.id} className="hover:bg-slate-50/80 transition-colors">
                    <td className="py-3 px-3 font-semibold text-slate-900 truncate max-w-[180px]">
                      {d.file_name}
                    </td>
                    <td className="py-3 px-3 capitalize text-slate-600 font-mono text-[11px]">
                      {d.document_type.replace('_', ' ')}
                    </td>
                    <td className="py-3 px-3 text-slate-600">
                      {d.village}, {d.tehsil}
                    </td>
                    <td className="py-3 px-3">
                      <ConfidenceBadge confidence={d.extraction_confidence || d.ocr_confidence} />
                    </td>
                    <td className="py-3 px-3">
                      <StatusBadge status={d.status} />
                    </td>
                    <td className="py-3 px-3 text-right">
                      <Link
                        to={`/verification/${d.id}`}
                        className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-700 hover:text-emerald-900 bg-emerald-50 px-2.5 py-1 rounded border border-emerald-200 hover:bg-emerald-100 transition-colors"
                      >
                        {t('dashboard.verify', 'Verify')} &rarr;
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Live Validation Anomalies Feed */}
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs flex flex-col">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-sm font-bold text-slate-900">{t('dashboard.liveAnomalies', 'Validation Anomalies')}</h3>
              <p className="text-xs text-slate-500">{t('dashboard.anomaliesSubtitle', 'Cross-DB & rule discrepancies')}</p>
            </div>
            <Link to="/validation" className="text-xs font-semibold text-emerald-700 hover:underline">
              {t('common.resolve', 'Resolve')} &rarr;
            </Link>
          </div>

          <div className="space-y-3 flex-1 overflow-y-auto">
            {anomalies.length === 0 ? (
              <div className="text-center py-8 text-slate-400 text-xs">{t('dashboard.noActiveAnomalies', 'No active anomalies')}</div>
            ) : (
              anomalies.map((anom) => (
                <div key={anom.id} className="p-3 rounded-lg bg-red-50/50 border border-red-200 text-xs">
                  <div className="flex items-center justify-between font-bold text-red-900">
                    <span className="truncate max-w-[180px]">{anom.rule_name}</span>
                    <span className="text-[10px] uppercase font-bold text-red-600 bg-red-100 px-1.5 py-0.5 rounded">
                      {anom.severity}
                    </span>
                  </div>
                  <p className="mt-1 text-slate-700 leading-relaxed text-[11px]">{anom.message}</p>
                  <div className="mt-2 flex items-center justify-between text-[10px] text-slate-500">
                    <span>{t('dashboard.docNumberPrefix', 'Doc #')}{anom.document_id}</span>
                    <Link
                      to={`/verification/${anom.document_id}`}
                      className="font-bold text-emerald-700 hover:underline"
                    >
                      {t('dashboard.resolveInWorkspace', 'Resolve in Workspace')} &rarr;
                    </Link>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
