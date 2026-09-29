import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { LanguageProvider } from './context/LanguageContext';
import { MainLayout } from './layouts/MainLayout';
import { Login } from './pages/Login';
import { LandStory } from './pages/LandStory';
import { Dashboard } from './pages/Dashboard';
import { DocumentUpload } from './pages/DocumentUpload';
import { DocumentsRepository } from './pages/DocumentsRepository';
import { VerificationQueue } from './pages/VerificationQueue';
import { VerificationWorkspace } from './pages/VerificationWorkspace';
import { LandRecordsRegistry } from './pages/LandRecordsRegistry';
import { ParcelSearch } from './pages/ParcelSearch';
import { ParcelIntelligence } from './pages/ParcelIntelligence';
import { InvestigationCenter } from './pages/InvestigationCenter';
import { GISMap } from './pages/GISMap';
import { CadastralVectorizer } from './pages/CadastralVectorizer';
import { ValidationCenter } from './pages/ValidationCenter';
import { Reports } from './pages/Reports';
import { AuditLogs } from './pages/AuditLogs';
import { ActiveLearning } from './pages/ActiveLearning';
import { AdminManagement } from './pages/AdminManagement';
import { Settings } from './pages/Settings';
import { AccessRestricted } from './pages/AccessRestricted';

// Mirrors backend/app/auth/rbac.py's STAFF_ROLES - every role except the
// public/citizen viewer. Parcel Intelligence, the Investigation Center and
// every other internal-operations page are all gated STAFF_ROLES-equivalent
// capabilities server-side (CAN_READ_DOCUMENTS/CAN_READ_FINDINGS/etc.), so a
// viewer would only hit a wall of 403s; this keeps that consistent
// client-side rather than showing broken or blank pages.
const STAFF_ROLES = ['super_admin', 'admin', 'district_officer', 'tehsil_officer', 'verification_officer'];

const ProtectedRoute = ({ children, allowedRoles }) => {
  const { isAuthenticated, user } = useAuth();
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  if (allowedRoles && !allowedRoles.includes(user?.role)) {
    // The viewer role gets an explicit, friendly "Access Restricted" page
    // rather than a silent bounce - it's how a citizen user finds out a
    // typed/bookmarked URL isn't theirs to see. Every other role keeps the
    // exact redirect behavior this already had, unchanged.
    if (user?.role === 'viewer') {
      return <AccessRestricted />;
    }
    return <Navigate to="/" replace />;
  }
  return children;
};

export default function App() {
  return (
    <LanguageProvider>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<Login />} />

            {/*
              Public, unauthenticated narrative page. Deliberately outside
              ProtectedRoute: it is what a judge, a visiting officer or a citizen
              sees before they have an account, and it calls no API (every
              backend endpoint requires a bearer token, and api.js bounces a 401
              back to /login - which would make a public page unusable).
            */}
            <Route path="/story" element={<LandStory />} />

            <Route
              path="/"
              element={
                <ProtectedRoute>
                  <MainLayout />
                </ProtectedRoute>
              }
            >
              <Route index element={<Dashboard />} />
              <Route
                path="upload"
                element={
                  <ProtectedRoute allowedRoles={STAFF_ROLES}>
                    <DocumentUpload />
                  </ProtectedRoute>
                }
              />
              <Route
                path="documents"
                element={
                  <ProtectedRoute allowedRoles={STAFF_ROLES}>
                    <DocumentsRepository />
                  </ProtectedRoute>
                }
              />
              <Route
                path="verification"
                element={
                  <ProtectedRoute allowedRoles={STAFF_ROLES}>
                    <VerificationQueue />
                  </ProtectedRoute>
                }
              />
              <Route
                path="verification/:id"
                element={
                  <ProtectedRoute allowedRoles={STAFF_ROLES}>
                    <VerificationWorkspace />
                  </ProtectedRoute>
                }
              />
              <Route path="records" element={<LandRecordsRegistry />} />
              <Route
                path="parcels"
                element={
                  <ProtectedRoute allowedRoles={STAFF_ROLES}>
                    <ParcelSearch />
                  </ProtectedRoute>
                }
              />
              <Route
                path="parcels/:id"
                element={
                  <ProtectedRoute allowedRoles={STAFF_ROLES}>
                    <ParcelIntelligence />
                  </ProtectedRoute>
                }
              />
              <Route
                path="investigations"
                element={
                  <ProtectedRoute allowedRoles={STAFF_ROLES}>
                    <InvestigationCenter />
                  </ProtectedRoute>
                }
              />
              <Route path="gis" element={<GISMap />} />
              <Route
                path="vectorizer"
                element={
                  <ProtectedRoute allowedRoles={STAFF_ROLES}>
                    <CadastralVectorizer />
                  </ProtectedRoute>
                }
              />
              <Route
                path="validation"
                element={
                  <ProtectedRoute allowedRoles={STAFF_ROLES}>
                    <ValidationCenter />
                  </ProtectedRoute>
                }
              />
              <Route
                path="reports"
                element={
                  <ProtectedRoute allowedRoles={STAFF_ROLES}>
                    <Reports />
                  </ProtectedRoute>
                }
              />
              <Route
                path="audit"
                element={
                  <ProtectedRoute allowedRoles={STAFF_ROLES}>
                    <AuditLogs />
                  </ProtectedRoute>
                }
              />
              <Route
                path="learning"
                element={
                  <ProtectedRoute allowedRoles={STAFF_ROLES}>
                    <ActiveLearning />
                  </ProtectedRoute>
                }
              />
              <Route
                path="admin/users"
                element={
                  <ProtectedRoute allowedRoles={['super_admin', 'admin']}>
                    <AdminManagement />
                  </ProtectedRoute>
                }
              />
              <Route path="settings" element={<Settings />} />
            </Route>

            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </LanguageProvider>
  );
}
