import React, { Suspense, lazy } from 'react';
import { Routes, Route, Navigate, Outlet } from 'react-router-dom';
import { QueryClientProvider } from '@tanstack/react-query';
import TopNav from './components/TopNav';
import AccessibilityToggle from './components/AccessibilityToggle';
import OnboardingQuestWidget from './components/OnboardingQuestWidget';
import ErrorBoundary from './components/ErrorBoundary';
import { PageFallback } from './components/Skeleton';
import { isAuthenticated } from './api/client';
import { UserProvider } from './context/UserContext';
import { queryClient } from './utils/queryClient';

// Lazy-импорт страниц — каждая попадёт в свой chunk, уменьшит initial bundle.
const ProfilePage    = lazy(() => import('./pages/ProfilePage'));
const NewsPage       = lazy(() => import('./pages/NewsPage'));
const SearchPage     = lazy(() => import('./pages/SearchPage'));
const LoginPage      = lazy(() => import('./pages/LoginPage'));
const RegisterPage   = lazy(() => import('./pages/RegisterPage'));
const VerifyEmailPage = lazy(() => import('./pages/VerifyEmailPage'));
const SettingsPage   = lazy(() => import('./pages/SettingsPage'));
const UserPublicPage = lazy(() => import('./pages/UserPublicPage'));
const BalancePage    = lazy(() => import('./pages/BalancePage'));
const SupportPage    = lazy(() => import('./pages/SupportPage'));
const AdminTicketsPage = lazy(() => import('./pages/AdminTicketsPage'));
const HomePage       = lazy(() => import('./pages/HomePage'));
const OnboardingPage = lazy(() => import('./pages/OnboardingPage'));

function MainLayout() {
  return (
    <div className="app-bg">
      <TopNav />
      <Outlet />
      <OnboardingQuestWidget />
    </div>
  );
}

function ProtectedRoute({ children }) {
  return isAuthenticated() ? children : <Navigate to="/login" replace />;
}

export default function App() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <UserProvider>
          <Suspense fallback={<PageFallback />}>
            <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/login"    element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />
            <Route path="/verify-email/:token" element={<VerifyEmailPage />} />

            <Route element={<MainLayout />}>
              <Route path="/news"   element={<NewsPage />} />
              <Route path="/search" element={<SearchPage />} />
              <Route
                path="/profile"
                element={<ProtectedRoute><ProfilePage /></ProtectedRoute>}
              />
              <Route
                path="/settings"
                element={<ProtectedRoute><SettingsPage /></ProtectedRoute>}
              />
              <Route path="/users/:username" element={<UserPublicPage />} />
              <Route
                path="/balance"
                element={<ProtectedRoute><BalancePage /></ProtectedRoute>}
              />
              <Route
                path="/support"
                element={<ProtectedRoute><SupportPage /></ProtectedRoute>}
              />
              <Route
                path="/onboarding"
                element={<ProtectedRoute><OnboardingPage /></ProtectedRoute>}
              />
              <Route
                path="/admin/tickets"
                element={<ProtectedRoute><AdminTicketsPage /></ProtectedRoute>}
              />
            </Route>
          </Routes>
          </Suspense>
          <AccessibilityToggle />
        </UserProvider>
      </QueryClientProvider>
    </ErrorBoundary>
  );
}
