import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/common/Layout';
import HomePage from './pages/HomePage';
import ChatPage from './pages/ChatPage';
import MemoryPage from './pages/MemoryPage';
import KnowledgePage from './pages/KnowledgePage';
import GitHubPage from './pages/GitHubPage';
import AnalyticsPage from './pages/AnalyticsPage';
import { ROUTES } from './utils/constants';

function App() {
  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path={ROUTES.HOME} element={<HomePage />} />
          <Route path={ROUTES.CHAT} element={<ChatPage />} />
          <Route path={ROUTES.MEMORY} element={<MemoryPage />} />
          <Route path={ROUTES.KNOWLEDGE} element={<KnowledgePage />} />
          <Route path={ROUTES.GITHUB} element={<GitHubPage />} />
          <Route path={ROUTES.ANALYTICS} element={<AnalyticsPage />} />
          <Route path="*" element={<Navigate to={ROUTES.HOME} replace />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  );
}

export default App;
