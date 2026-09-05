import { Link } from 'react-router-dom';
import Card from '../components/common/Card';
import ChatContainer from '../components/chat/ChatContainer';
import { ROUTES } from '../utils/constants';

const HomePage = () => {
  return (
    <div className="max-w-7xl mx-auto">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">Welcome to Evolving AI Agent</h1>
        <p className="mt-2 text-gray-600">
          A private AI steward with shared memory, dream consolidation, and measured, reversible response adaptation.
        </p>
      </div>

      {/* Quick Chat Interface for Debugging */}
      <Card title="Quick Chat" className="mb-8">
        <div className="h-96">
          <ChatContainer />
        </div>
      </Card>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <Card title="Chat Interface">
          <p className="text-gray-600 mb-4">
            Interact with the AI agent and receive intelligent responses based on context and memory.
          </p>
          <Link to={ROUTES.CHAT} className="inline-flex rounded-md bg-indigo-50 px-3 py-2 text-sm font-medium text-indigo-800 hover:bg-indigo-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-indigo-600">Go to Chat</Link>
        </Card>

        <Card title="Memory Browser">
          <p className="text-gray-600 mb-4">
            Browse and search through stored memories and past interactions.
          </p>
          <Link to={ROUTES.MEMORY} className="inline-flex rounded-md bg-indigo-50 px-3 py-2 text-sm font-medium text-indigo-800 hover:bg-indigo-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-indigo-600">Browse Memory</Link>
        </Card>

        <Card title="Knowledge Base">
          <p className="text-gray-600 mb-4">
            Explore the agent's knowledge base organized by categories and confidence levels.
          </p>
          <Link to={ROUTES.KNOWLEDGE} className="inline-flex rounded-md bg-indigo-50 px-3 py-2 text-sm font-medium text-indigo-800 hover:bg-indigo-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-indigo-600">View Knowledge</Link>
        </Card>

        <Card title="GitHub Integration">
          <p className="text-gray-600 mb-4">
            Review repository activity. Code changes require a separately authorized development workflow.
          </p>
          <Link to={ROUTES.GITHUB} className="inline-flex rounded-md bg-indigo-50 px-3 py-2 text-sm font-medium text-indigo-800 hover:bg-indigo-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-indigo-600">GitHub Dashboard</Link>
        </Card>

        <Card title="Analytics">
          <p className="text-gray-600 mb-4">
            View system metrics, performance trends, and interaction analytics.
          </p>
          <Link to={ROUTES.ANALYTICS} className="inline-flex rounded-md bg-indigo-50 px-3 py-2 text-sm font-medium text-indigo-800 hover:bg-indigo-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-indigo-600">View Analytics</Link>
        </Card>

        <Card title="System Status">
          <p className="text-gray-600 mb-4">
            Monitor agent health, API status, and system resources.
          </p>
          <Link to={ROUTES.STATUS} className="inline-flex rounded-md bg-indigo-50 px-3 py-2 text-sm font-medium text-indigo-800 hover:bg-indigo-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-indigo-600">View Status</Link>
        </Card>

        <Card title="API Documentation">
          <p className="text-gray-600 mb-4">
            Explore the complete API reference and interactive documentation.
          </p>
          <Link to={ROUTES.DOCS} className="inline-flex rounded-md bg-indigo-50 px-3 py-2 text-sm font-medium text-indigo-800 hover:bg-indigo-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-indigo-600">View Docs</Link>
        </Card>
      </div>
    </div>
  );
};

export default HomePage;
