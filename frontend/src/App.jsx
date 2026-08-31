import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { lazy, Suspense } from 'react';
import Layout from './components/common/Layout';
import { ROUTES } from './utils/constants';
import AuthGate from './components/common/AuthGate';
import PageBoundary from './components/common/PageBoundary';

const HomePage = lazy(() => import('./pages/HomePage'));
const ChatPage = lazy(() => import('./pages/ChatPage'));
const MemoryPage = lazy(() => import('./pages/MemoryPage'));
const KnowledgePage = lazy(() => import('./pages/KnowledgePage'));
const GitHubPage = lazy(() => import('./pages/GitHubPage'));
const AnalyticsPage = lazy(() => import('./pages/AnalyticsPage'));
const StatusPage = lazy(() => import('./pages/StatusPage'));
const DocsPage = lazy(() => import('./pages/DocsPage'));

function App() {
  return (
    <BrowserRouter>
      <AuthGate>
        <Layout>
          {import.meta.env.DEV && import.meta.env.VITE_PREVIEW_FIXTURES === 'true' && (
            <p role="status" className="mb-4 rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-950">
              Synthetic UI preview — no HAM, provider calls, or external actions. Evidence below is test data.
            </p>
          )}
          <PageBoundary>
          <Suspense fallback={<p role="status" className="p-6 text-gray-700">Loading page…</p>}>
          <Routes>
            <Route path={ROUTES.HOME} element={<HomePage />} />
            <Route path={ROUTES.CHAT} element={<ChatPage />} />
            <Route path={ROUTES.MEMORY} element={<MemoryPage />} />
            <Route path={ROUTES.KNOWLEDGE} element={<KnowledgePage />} />
            <Route path={ROUTES.GITHUB} element={<GitHubPage />} />
            <Route path={ROUTES.ANALYTICS} element={<AnalyticsPage />} />
            <Route path={ROUTES.STATUS} element={<StatusPage />} />
            <Route path={ROUTES.DOCS} element={<DocsPage />} />
            <Route path="*" element={<Navigate to={ROUTES.HOME} replace />} />
          </Routes>
          </Suspense>
          </PageBoundary>
        </Layout>
      </AuthGate>
    </BrowserRouter>
  );
}

export default App;
