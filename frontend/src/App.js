import React, { Suspense, lazy } from 'react';
import { Routes, Route, Navigate, Outlet } from 'react-router-dom';
import { QueryClientProvider } from '@tanstack/react-query';
import TopNav from './components/TopNav';
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
const SettingsPage   = lazy(() => import('./pages/SettingsPage'));
const UserPublicPage = lazy(() => import('./pages/UserPublicPage'));
const BalancePage    = lazy(() => import('./pages/BalancePage'));
const SupportPage    = lazy(() => import('./pages/SupportPage'));

function MainLayout() {
  return (
    <div className="app-bg">
      <TopNav />
      <Outlet />
    </div>
  );
}

export default function App() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <UserProvider>
          <Suspense fallback={<PageFallback />}>
            <Routes>
            <Route path="/login"    element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />

            <Route element={<MainLayout />}>
              <Route path="/" element={<Navigate to={isAuthenticated() ? '/profile' : '/login'} replace />} />
              <Route path="/news"   element={<NewsPage />} />
              <Route path="/search" element={<SearchPage />} />
              <Route
                path="/profile"
                element={isAuthenticated() ? <ProfilePage /> : <Navigate to="/login" replace />}
              />
              <Route
                path="/settings"
                element={isAuthenticated() ? <SettingsPage /> : <Navigate to="/login" replace />}
              />
              <Route path="/users/:username" element={<UserPublicPage />} />
              <Route
                path="/balance"
                element={isAuthenticated() ? <BalancePage /> : <Navigate to="/login" replace />}
              />
              <Route
                path="/support"
                element={isAuthenticated() ? <SupportPage /> : <Navigate to="/login" replace />}
              />
            </Route>
          </Routes>
          </Suspense>
        </UserProvider>
      </QueryClientProvider>
    </ErrorBoundary>
  );
}
