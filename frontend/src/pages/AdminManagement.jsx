import React, { useState, useEffect } from 'react';
import {
  Users,
  UserPlus,
  Shield,
  ShieldCheck,
  ShieldAlert,
  Search,
  Filter,
  RefreshCw,
  Edit2,
  KeyRound,
  UserX,
  UserCheck,
  Trash2,
  CheckCircle2,
  AlertCircle,
  Clock,
  MapPin
} from 'lucide-react';
import api from '../services/api';
import { useAuth } from '../context/AuthContext';
import { useLanguage } from '../context/LanguageContext';
import { StatusBadge } from '../components/common/Badge';
import { Modal } from '../components/common/Modal';
import { CascadingLocationPicker } from '../components/common/CascadingLocationPicker';

export const AdminManagement = () => {
  const { user: currentUser } = useAuth();
  const { t } = useLanguage();

  const [users, setUsers] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [roleFilter, setRoleFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');

  // Modals state
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [passwordModalOpen, setPasswordModalOpen] = useState(false);
  const [selectedUser, setSelectedUser] = useState(null);

  // Form states
  const [formData, setFormData] = useState({
    full_name: '',
    email: '',
    username: '',
    password: '',
    role: 'verification_officer',
    department: 'Revenue Department',
    state: 'Uttar Pradesh',
    district: 'Kanpur Nagar',
    tehsil: 'Bilhaur',
    is_active: true
  });

  const [newPassword, setNewPassword] = useState('');
  const [actionSuccess, setActionSuccess] = useState('');
  const [actionError, setActionError] = useState('');

  useEffect(() => {
    fetchUsersAndStats();
  }, [roleFilter, statusFilter]);

  const fetchUsersAndStats = async () => {
    setLoading(true);
    try {
      let url = '/admin/users?';
      if (roleFilter) url += `role=${roleFilter}&`;
      if (statusFilter !== '') url += `is_active=${statusFilter === 'true'}&`;
      
      const [usersRes, statsRes] = await Promise.all([
        api.get(url),
        api.get('/admin/stats')
      ]);
      setUsers(usersRes.data);
      setStats(statsRes.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const showNotification = (msg, isError = false) => {
    if (isError) {
      setActionError(msg);
      setTimeout(() => setActionError(''), 4000);
    } else {
      setActionSuccess(msg);
      setTimeout(() => setActionSuccess(''), 4000);
    }
  };

  const handleCreateSubmit = async (e) => {
    e.preventDefault();
    try {
      await api.post('/admin/users', formData);
      showNotification(`Officer '${formData.username}' registered successfully!`);
      setCreateModalOpen(false);
      setFormData({
        full_name: '',
        email: '',
        username: '',
        password: '',
        role: 'verification_officer',
        department: 'Revenue Department',
        state: 'Uttar Pradesh',
        district: 'Kanpur Nagar',
        tehsil: 'Bilhaur',
        is_active: true
      });
      fetchUsersAndStats();
    } catch (err) {
      showNotification(err.response?.data?.detail || 'Failed to create account.', true);
    }
  };

  const handleEditSubmit = async (e) => {
    e.preventDefault();
    if (!selectedUser) return;
    try {
      await api.put(`/admin/users/${selectedUser.id}`, {
        full_name: formData.full_name,
        email: formData.email,
        role: formData.role,
        department: formData.department,
        state: formData.state,
        district: formData.district,
        tehsil: formData.tehsil,
        is_active: formData.is_active
      });
      showNotification(`Account '${formData.username}' updated successfully!`);
      setEditModalOpen(false);
      fetchUsersAndStats();
    } catch (err) {
      showNotification(err.response?.data?.detail || 'Failed to update account.', true);
    }
  };

  const handleToggleStatus = async (user) => {
    const newStatus = !user.is_active;
    const actionLabel = newStatus ? 'activate' : 'deactivate';
    if (!window.confirm(`Are you sure you want to ${actionLabel} account '${user.username}'?`)) return;

    try {
      await api.put(`/admin/users/${user.id}/status`, { is_active: newStatus });
      showNotification(`Account '${user.username}' ${actionLabel}d successfully!`);
      fetchUsersAndStats();
    } catch (err) {
      showNotification(err.response?.data?.detail || `Failed to ${actionLabel} account.`, true);
    }
  };

  const handleResetPasswordSubmit = async (e) => {
    e.preventDefault();
    if (!selectedUser) return;
    if (newPassword.length < 6) {
      showNotification('Password must be at least 6 characters long.', true);
      return;
    }

    try {
      await api.post(`/admin/users/${selectedUser.id}/reset-password`, { new_password: newPassword });
      showNotification(`Password for '${selectedUser.username}' reset successfully!`);
      setPasswordModalOpen(false);
      setNewPassword('');
    } catch (err) {
      showNotification(err.response?.data?.detail || 'Failed to reset password.', true);
    }
  };

  const handleDeleteUser = async (user) => {
    if (!window.confirm(`Are you sure you want to permanently delete user '${user.username}'?`)) return;

    try {
      await api.delete(`/admin/users/${user.id}`);
      showNotification(`User '${user.username}' removed successfully!`);
      fetchUsersAndStats();
    } catch (err) {
      showNotification(err.response?.data?.detail || 'Failed to delete user.', true);
    }
  };

  const openEditModal = (user) => {
    setSelectedUser(user);
    setFormData({
      full_name: user.full_name,
      email: user.email,
      username: user.username,
      role: user.role,
      department: user.department,
      state: user.state,
      district: user.district,
      tehsil: user.tehsil,
      is_active: user.is_active
    });
    setEditModalOpen(true);
  };

  const openPasswordModal = (user) => {
    setSelectedUser(user);
    setNewPassword('');
    setPasswordModalOpen(true);
  };

  const filteredUsers = users.filter(u => {
    if (!search) return true;
    const q = search.toLowerCase();
    return (
      u.full_name.toLowerCase().includes(q) ||
      u.username.toLowerCase().includes(q) ||
      u.email.toLowerCase().includes(q) ||
      u.district?.toLowerCase().includes(q)
    );
  });

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
            <ShieldCheck className="w-5 h-5 text-emerald-700" />
            {t('admin.title', 'Administrative User & Officer Management')}
          </h2>
          <p className="text-xs text-slate-500 mt-1">
            {t('admin.subtitle', 'Create, configure, activate/deactivate, and audit revenue officers with strict role-based access control.')}
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <button
            onClick={() => setCreateModalOpen(true)}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-bold text-white bg-emerald-700 hover:bg-emerald-800 rounded-lg shadow-xs transition-colors"
          >
            <UserPlus className="w-4 h-4" />
            {t('admin.createBtn', 'Create New Officer / Admin')}
          </button>
          <button
            onClick={fetchUsersAndStats}
            className="p-2 text-slate-500 hover:text-slate-900 border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Notifications Alert Banner */}
      {actionSuccess && (
        <div className="p-3 bg-emerald-50 border border-emerald-200 text-emerald-900 rounded-lg text-xs font-bold flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-700" />
          {actionSuccess}
        </div>
      )}
      {actionError && (
        <div className="p-3 bg-rose-50 border border-rose-200 text-rose-900 rounded-lg text-xs font-bold flex items-center gap-2">
          <AlertCircle className="w-4 h-4 text-rose-700" />
          {actionError}
        </div>
      )}

      {/* KPI Stats Summary */}
      {stats && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs flex items-center gap-3">
            <div className="p-2.5 bg-blue-50 text-blue-700 rounded-lg">
              <Users className="w-5 h-5" />
            </div>
            <div>
              <span className="text-[10px] text-slate-400 font-bold uppercase">{t('admin.totalAdmins', 'Total Registered Users')}</span>
              <div className="text-xl font-bold text-slate-900">{stats.total_admins}</div>
            </div>
          </div>

          <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs flex items-center gap-3">
            <div className="p-2.5 bg-emerald-50 text-emerald-700 rounded-lg">
              <UserCheck className="w-5 h-5" />
            </div>
            <div>
              <span className="text-[10px] text-slate-400 font-bold uppercase">{t('admin.activeAdmins', 'Active Accounts')}</span>
              <div className="text-xl font-bold text-emerald-700">{stats.active_admins}</div>
            </div>
          </div>

          <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs flex items-center gap-3">
            <div className="p-2.5 bg-amber-50 text-amber-700 rounded-lg">
              <UserX className="w-5 h-5" />
            </div>
            <div>
              <span className="text-[10px] text-slate-400 font-bold uppercase">{t('admin.inactiveAdmins', 'Deactivated Accounts')}</span>
              <div className="text-xl font-bold text-amber-700">{stats.inactive_admins}</div>
            </div>
          </div>
        </div>
      )}

      {/* Filter and Search Bar */}
      <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-xs flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="relative w-full sm:w-80">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
          <input
            type="text"
            placeholder={t('common.search', 'Search by name, email, or district...')}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-emerald-500 focus:border-emerald-500"
          />
        </div>

        <div className="flex items-center gap-3 flex-wrap">
          <div className="flex items-center gap-1.5 text-xs">
            <Filter className="w-3.5 h-3.5 text-slate-400" />
            <span className="font-semibold text-slate-600">{t('admin.role', 'Role')}:</span>
            <select
              value={roleFilter}
              onChange={(e) => setRoleFilter(e.target.value)}
              className="text-xs border border-slate-300 rounded-lg p-1.5 focus:ring-emerald-500 focus:border-emerald-500"
            >
              <option value="">{t('adminManagement.allRoles', 'All Roles')}</option>
              <option value="super_admin">{t('header.roleSuperAdmin', 'Super Admin')}</option>
              <option value="admin">{t('adminManagement.roleStateAdmin', 'State Admin')}</option>
              <option value="district_officer">{t('header.roleDistrictOfficer', 'District Officer')}</option>
              <option value="tehsil_officer">{t('header.roleTehsilOfficer', 'Tehsil Officer')}</option>
              <option value="verification_officer">{t('header.roleVerificationOfficer', 'Verification Officer')}</option>
              <option value="viewer">{t('adminManagement.rolePublicViewer', 'Public Viewer')}</option>
            </select>
          </div>

          <div className="flex items-center gap-1.5 text-xs">
            <span className="font-semibold text-slate-600">{t('admin.status', 'Status')}:</span>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="text-xs border border-slate-300 rounded-lg p-1.5 focus:ring-emerald-500 focus:border-emerald-500"
            >
              <option value="">{t('adminManagement.allStatuses', 'All Statuses')}</option>
              <option value="true">{t('adminManagement.activeOnly', 'Active Only')}</option>
              <option value="false">{t('adminManagement.deactivatedOnly', 'Deactivated Only')}</option>
            </select>
          </div>
        </div>
      </div>

      {/* Users Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
        {loading ? (
          <div className="py-16 text-center text-slate-500 text-xs">
            <RefreshCw className="w-6 h-6 animate-spin mx-auto text-emerald-700 mb-2" />
            {t('common.loading', 'Loading registered officers...')}
          </div>
        ) : filteredUsers.length === 0 ? (
          <div className="py-16 text-center text-slate-400 text-xs">
            No accounts found matching filter.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-slate-600 uppercase text-[10px] font-bold border-b border-slate-200">
                <tr>
                  <th className="py-3 px-4">{t('admin.name', 'Name')} & {t('admin.username', 'Username')}</th>
                  <th className="py-3 px-4">{t('admin.email', 'Email')}</th>
                  <th className="py-3 px-4">{t('admin.role', 'Role')}</th>
                  <th className="py-3 px-4">{t('admin.jurisdiction', 'Jurisdiction')}</th>
                  <th className="py-3 px-4">{t('admin.status', 'Status')}</th>
                  <th className="py-3 px-4">{t('admin.createdAt', 'Created At')}</th>
                  <th className="py-3 px-4 text-right">{t('admin.actions', 'Actions')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filteredUsers.map((u) => (
                  <tr key={u.id} className="hover:bg-slate-50/80 transition-colors">
                    <td className="py-3.5 px-4">
                      <div className="font-bold text-slate-900">{u.full_name}</div>
                      <div className="text-[10px] text-slate-400 font-mono">@{u.username}</div>
                    </td>
                    <td className="py-3.5 px-4 font-mono text-slate-700">
                      {u.email}
                    </td>
                    <td className="py-3.5 px-4">
                      <span className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-bold ${
                        u.role === 'super_admin' ? 'bg-purple-50 text-purple-700 border border-purple-200' :
                        u.role === 'admin' ? 'bg-indigo-50 text-indigo-700 border border-indigo-200' :
                        u.role === 'district_officer' ? 'bg-blue-50 text-blue-700 border border-blue-200' :
                        u.role === 'tehsil_officer' ? 'bg-teal-50 text-teal-700 border border-teal-200' :
                        u.role === 'verification_officer' ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' :
                        'bg-slate-100 text-slate-700 border border-slate-200'
                      }`}>
                        {u.role.replace('_', ' ').toUpperCase()}
                      </span>
                    </td>
                    <td className="py-3.5 px-4 text-slate-700">
                      <div>{u.district || t('adminManagement.allDistricts', 'All Districts')}</div>
                      <div className="text-[10px] text-slate-400">{u.state}</div>
                    </td>
                    <td className="py-3.5 px-4">
                      <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold ${
                        u.is_active ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' : 'bg-rose-50 text-rose-700 border border-rose-200'
                      }`}>
                        {u.is_active ? t('adminManagement.active', 'Active') : t('adminManagement.deactivated', 'Deactivated')}
                      </span>
                    </td>
                    <td className="py-3.5 px-4 text-slate-500 font-mono text-[11px]">
                      {new Date(u.created_at).toLocaleDateString()}
                    </td>
                    <td className="py-3.5 px-4 text-right">
                      <div className="flex items-center justify-end gap-1">
                        <button
                          onClick={() => openEditModal(u)}
                          className="p-1.5 rounded-lg text-slate-600 hover:text-emerald-700 hover:bg-emerald-50 transition-colors"
                          title={t('admin.edit', 'Edit User')}
                        >
                          <Edit2 className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => handleToggleStatus(u)}
                          className={`p-1.5 rounded-lg transition-colors ${
                            u.is_active ? 'text-amber-600 hover:bg-amber-50' : 'text-emerald-600 hover:bg-emerald-50'
                          }`}
                          title={u.is_active ? t('admin.deactivate', 'Deactivate') : t('admin.activate', 'Activate')}
                        >
                          {u.is_active ? <UserX className="w-3.5 h-3.5" /> : <UserCheck className="w-3.5 h-3.5" />}
                        </button>
                        <button
                          onClick={() => openPasswordModal(u)}
                          className="p-1.5 rounded-lg text-slate-600 hover:text-blue-700 hover:bg-blue-50 transition-colors"
                          title={t('admin.resetPass', 'Reset Password')}
                        >
                          <KeyRound className="w-3.5 h-3.5" />
                        </button>
                        {currentUser?.role === 'super_admin' && u.role !== 'super_admin' && (
                          <button
                            onClick={() => handleDeleteUser(u)}
                            className="p-1.5 rounded-lg text-slate-400 hover:text-rose-700 hover:bg-rose-50 transition-colors"
                            title="Delete User"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* CREATE NEW ADMIN MODAL */}
      <Modal
        isOpen={createModalOpen}
        onClose={() => setCreateModalOpen(false)}
        title={t('admin.createBtn', 'Create New Officer / Admin Account')}
      >
        <form onSubmit={handleCreateSubmit} className="space-y-4 text-xs">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block font-bold text-slate-700 mb-1">{t('admin.name', 'Full Name')} *</label>
              <input
                type="text"
                required
                value={formData.full_name}
                onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
                placeholder="e.g. Dr. Ramesh Gupta"
                className="w-full p-2 border border-slate-300 rounded-lg focus:ring-emerald-500 focus:border-emerald-500"
              />
            </div>
            <div>
              <label className="block font-bold text-slate-700 mb-1">{t('admin.username', 'Username')} *</label>
              <input
                type="text"
                required
                value={formData.username}
                onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                placeholder="e.g. ramesh_gupta"
                className="w-full p-2 border border-slate-300 rounded-lg focus:ring-emerald-500 focus:border-emerald-500"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block font-bold text-slate-700 mb-1">{t('admin.email', 'Official Email')} *</label>
              <input
                type="email"
                required
                value={formData.email}
                onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                placeholder="officer@revenue.gov.in"
                className="w-full p-2 border border-slate-300 rounded-lg focus:ring-emerald-500 focus:border-emerald-500"
              />
            </div>
            <div>
              <label className="block font-bold text-slate-700 mb-1">{t('admin.password', 'Initial Password')} *</label>
              <input
                type="password"
                required
                minLength={6}
                value={formData.password}
                onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                placeholder="Min 6 characters"
                className="w-full p-2 border border-slate-300 rounded-lg focus:ring-emerald-500 focus:border-emerald-500"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block font-bold text-slate-700 mb-1">{t('admin.role', 'Role')} *</label>
              <select
                value={formData.role}
                onChange={(e) => setFormData({ ...formData, role: e.target.value })}
                className="w-full p-2 border border-slate-300 rounded-lg focus:ring-emerald-500 focus:border-emerald-500 bg-white"
              >
                {currentUser?.role === 'super_admin' && (
                  <option value="super_admin">{t('adminManagement.roleSuperAdminFull', 'Super Admin (Director General)')}</option>
                )}
                <option value="admin">{t('adminManagement.roleStateAdministrator', 'State Administrator')}</option>
                <option value="district_officer">{t('adminManagement.roleDistrictMagistrate', 'District Magistrate / Collector')}</option>
                <option value="tehsil_officer">{t('adminManagement.roleTehsildar', 'Tehsildar / SDM')}</option>
                <option value="verification_officer">{t('adminManagement.roleVerificationKanoongo', 'Verification Officer / Kanoongo')}</option>
                <option value="viewer">{t('adminManagement.rolePublicViewer', 'Public Viewer')}</option>
              </select>
            </div>
            <div>
              <label className="block font-bold text-slate-700 mb-1">{t('adminManagement.department', 'Department')}</label>
              <input
                type="text"
                value={formData.department}
                onChange={(e) => setFormData({ ...formData, department: e.target.value })}
                className="w-full p-2 border border-slate-300 rounded-lg focus:ring-emerald-500 focus:border-emerald-500"
              />
            </div>
          </div>

          {/* Cascading Location Jurisdiction Picker */}
          <div className="pt-2 border-t border-slate-100">
            <span className="block font-bold text-slate-800 mb-2 uppercase text-[10px] tracking-wider">
              {t('admin.jurisdiction', 'Jurisdiction Assignment')} (Location Hierarchy)
            </span>
            <CascadingLocationPicker
              selectedState={formData.state}
              selectedDistrict={formData.district}
              selectedTehsil={formData.tehsil}
              selectedVillage=""
              onChange={(loc) => setFormData(prev => ({
                ...prev,
                state: loc.state,
                district: loc.district,
                tehsil: loc.tehsil
              }))}
            />
          </div>

          <div className="pt-3 border-t border-slate-100 flex items-center justify-end gap-2">
            <button
              type="button"
              onClick={() => setCreateModalOpen(false)}
              className="px-4 py-2 border border-slate-300 rounded-lg text-slate-600 hover:bg-slate-50 font-semibold"
            >
              {t('admin.cancel', 'Cancel')}
            </button>
            <button
              type="submit"
              className="px-4 py-2 bg-emerald-700 hover:bg-emerald-800 text-white rounded-lg font-bold shadow-xs transition-colors"
            >
              {t('admin.save', 'Create Account')}
            </button>
          </div>
        </form>
      </Modal>

      {/* EDIT ADMIN MODAL */}
      <Modal
        isOpen={editModalOpen}
        onClose={() => setEditModalOpen(false)}
        title={`Edit Officer: ${selectedUser?.username}`}
      >
        <form onSubmit={handleEditSubmit} className="space-y-4 text-xs">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block font-bold text-slate-700 mb-1">{t('admin.name', 'Full Name')}</label>
              <input
                type="text"
                required
                value={formData.full_name}
                onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
                className="w-full p-2 border border-slate-300 rounded-lg focus:ring-emerald-500 focus:border-emerald-500"
              />
            </div>
            <div>
              <label className="block font-bold text-slate-700 mb-1">{t('admin.email', 'Official Email')}</label>
              <input
                type="email"
                required
                value={formData.email}
                onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                className="w-full p-2 border border-slate-300 rounded-lg focus:ring-emerald-500 focus:border-emerald-500"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block font-bold text-slate-700 mb-1">{t('admin.role', 'Role')}</label>
              <select
                value={formData.role}
                onChange={(e) => setFormData({ ...formData, role: e.target.value })}
                className="w-full p-2 border border-slate-300 rounded-lg focus:ring-emerald-500 focus:border-emerald-500 bg-white"
              >
                {currentUser?.role === 'super_admin' && (
                  <option value="super_admin">{t('header.roleSuperAdmin', 'Super Admin')}</option>
                )}
                <option value="admin">{t('adminManagement.roleStateAdmin', 'State Admin')}</option>
                <option value="district_officer">{t('header.roleDistrictOfficer', 'District Officer')}</option>
                <option value="tehsil_officer">{t('header.roleTehsilOfficer', 'Tehsil Officer')}</option>
                <option value="verification_officer">{t('header.roleVerificationOfficer', 'Verification Officer')}</option>
                <option value="viewer">{t('adminManagement.rolePublicViewer', 'Public Viewer')}</option>
              </select>
            </div>
            <div>
              <label className="block font-bold text-slate-700 mb-1">{t('admin.status', 'Status')}</label>
              <select
                value={formData.is_active ? 'true' : 'false'}
                onChange={(e) => setFormData({ ...formData, is_active: e.target.value === 'true' })}
                className="w-full p-2 border border-slate-300 rounded-lg focus:ring-emerald-500 focus:border-emerald-500 bg-white"
              >
                <option value="true">{t('adminManagement.active', 'Active')}</option>
                <option value="false">{t('adminManagement.deactivated', 'Deactivated')}</option>
              </select>
            </div>
          </div>

          <div className="pt-2 border-t border-slate-100">
            <span className="block font-bold text-slate-800 mb-2 uppercase text-[10px] tracking-wider">
              {t('admin.jurisdiction', 'Jurisdiction Assignment')}
            </span>
            <CascadingLocationPicker
              selectedState={formData.state}
              selectedDistrict={formData.district}
              selectedTehsil={formData.tehsil}
              selectedVillage=""
              onChange={(loc) => setFormData(prev => ({
                ...prev,
                state: loc.state,
                district: loc.district,
                tehsil: loc.tehsil
              }))}
            />
          </div>

          <div className="pt-3 border-t border-slate-100 flex items-center justify-end gap-2">
            <button
              type="button"
              onClick={() => setEditModalOpen(false)}
              className="px-4 py-2 border border-slate-300 rounded-lg text-slate-600 hover:bg-slate-50 font-semibold"
            >
              {t('admin.cancel', 'Cancel')}
            </button>
            <button
              type="submit"
              className="px-4 py-2 bg-emerald-700 hover:bg-emerald-800 text-white rounded-lg font-bold shadow-xs transition-colors"
            >
              {t('admin.save', 'Save Changes')}
            </button>
          </div>
        </form>
      </Modal>

      {/* RESET PASSWORD MODAL */}
      <Modal
        isOpen={passwordModalOpen}
        onClose={() => setPasswordModalOpen(false)}
        title={`Reset Password: ${selectedUser?.username}`}
      >
        <form onSubmit={handleResetPasswordSubmit} className="space-y-4 text-xs">
          <div>
            <label className="block font-bold text-slate-700 mb-1">New Password *</label>
            <input
              type="password"
              required
              minLength={6}
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              placeholder="Enter new password (min 6 characters)"
              className="w-full p-2.5 border border-slate-300 rounded-lg focus:ring-emerald-500 focus:border-emerald-500"
            />
          </div>

          <div className="pt-3 border-t border-slate-100 flex items-center justify-end gap-2">
            <button
              type="button"
              onClick={() => setPasswordModalOpen(false)}
              className="px-4 py-2 border border-slate-300 rounded-lg text-slate-600 hover:bg-slate-50 font-semibold"
            >
              {t('admin.cancel', 'Cancel')}
            </button>
            <button
              type="submit"
              className="px-4 py-2 bg-blue-700 hover:bg-blue-800 text-white rounded-lg font-bold shadow-xs transition-colors"
            >
              Update Password
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
