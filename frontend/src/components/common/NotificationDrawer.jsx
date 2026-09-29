import React, { useState, useEffect } from 'react';
import { Bell, CheckCircle2, AlertTriangle, AlertCircle, Info, X } from 'lucide-react';
import { Link } from 'react-router-dom';
import api from '../../services/api';
import { useLanguage } from '../../context/LanguageContext';

export const NotificationDrawer = ({ isOpen, onClose }) => {
  const { t } = useLanguage();
  const [notifications, setNotifications] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (isOpen) {
      fetchNotifications();
    }
  }, [isOpen]);

  const fetchNotifications = async () => {
    setLoading(true);
    try {
      const res = await api.get('/notifications/');
      setNotifications(res.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const markAllRead = async () => {
    try {
      await api.put('/notifications/read-all');
      setNotifications(prev => prev.map(n => ({ ...n, is_read: true })));
    } catch (err) {
      console.error(err);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-hidden">
      <div className="absolute inset-0 bg-slate-900/40 backdrop-blur-xs" onClick={onClose} />
      <div className="fixed inset-y-0 right-0 max-w-full flex pl-10">
        <div className="w-screen max-w-md bg-white shadow-2xl border-l border-slate-200 flex flex-col">
          <div className="p-4 border-b border-slate-200 flex items-center justify-between bg-slate-50">
            <div className="flex items-center gap-2">
              <Bell className="w-5 h-5 text-emerald-700" />
              <h2 className="text-base font-bold text-slate-900">{t('notifications.title', 'System Notifications')}</h2>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={markAllRead}
                className="text-xs font-semibold text-emerald-700 hover:text-emerald-800 hover:underline"
              >
                {t('notifications.markAllRead', 'Mark all read')}
              </button>
              <button onClick={onClose} className="p-1 text-slate-400 hover:text-slate-600 rounded">
                <X className="w-5 h-5" />
              </button>
            </div>
          </div>

          <div className="flex-1 overflow-y-auto p-4 space-y-3">
            {notifications.length === 0 ? (
              <div className="text-center py-12 text-slate-400 text-sm">
                {t('notifications.noNew', 'No new notifications')}
              </div>
            ) : (
              notifications.map((n) => (
                <div
                  key={n.id}
                  className={`p-3.5 rounded-lg border text-sm transition-all ${
                    n.is_read ? 'bg-slate-50/60 border-slate-200 text-slate-600' : 'bg-white border-emerald-200 shadow-xs'
                  }`}
                >
                  <div className="flex items-start gap-2.5">
                    {n.type === 'alert' && <AlertCircle className="w-4 h-4 text-red-600 shrink-0 mt-0.5" />}
                    {n.type === 'warning' && <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />}
                    {n.type === 'success' && <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />}
                    {n.type === 'info' && <Info className="w-4 h-4 text-blue-600 shrink-0 mt-0.5" />}
                    <div className="flex-1">
                      <h4 className="font-semibold text-slate-900 text-xs">{n.title}</h4>
                      <p className="mt-1 text-xs text-slate-600 leading-relaxed">{n.message}</p>
                      {n.link && (
                        <Link
                          to={n.link}
                          onClick={onClose}
                          className="mt-2 inline-block text-xs font-medium text-emerald-700 hover:underline"
                        >
                          {t('notifications.viewDetails', 'View Details')} &rarr;
                        </Link>
                      )}
                    </div>
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
