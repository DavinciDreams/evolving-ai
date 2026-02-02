import { Link } from 'react-router-dom';
import Card from '../components/common/Card';
import Button from '../components/common/Button';
import { ROUTES } from '../utils/constants';

const HomePage = () => {
  return (
    <div className="max-w-7xl mx-auto">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">Welcome to Evolving AI Agent</h1>
        <p className="mt-2 text-gray-600">
          A self-improving AI system with memory, knowledge management, and code evolution capabilities.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <Card title="Chat Interface">
          <p className="text-gray-600 mb-4">
            Interact with the AI agent and receive intelligent responses based on context and memory.
          </p>
          <Link to={ROUTES.CHAT}>
            <Button size="sm">Go to Chat</Button>
          </Link>
        </Card>

        <Card title="Memory Browser">
          <p className="text-gray-600 mb-4">
            Browse and search through stored memories and past interactions.
          </p>
          <Link to={ROUTES.MEMORY}>
            <Button size="sm" variant="secondary">Browse Memory</Button>
          </Link>
        </Card>

        <Card title="Knowledge Base">
          <p className="text-gray-600 mb-4">
            Explore the agent's knowledge base organized by categories and confidence levels.
          </p>
          <Link to={ROUTES.KNOWLEDGE}>
            <Button size="sm" variant="secondary">View Knowledge</Button>
          </Link>
        </Card>

        <Card title="GitHub Integration">
          <p className="text-gray-600 mb-4">
            Monitor pull requests, commits, and trigger code improvements.
          </p>
          <Link to={ROUTES.GITHUB}>
            <Button size="sm" variant="secondary">GitHub Dashboard</Button>
          </Link>
        </Card>

        <Card title="Analytics">
          <p className="text-gray-600 mb-4">
            View system metrics, performance trends, and interaction analytics.
          </p>
          <Link to={ROUTES.ANALYTICS}>
            <Button size="sm" variant="secondary">View Analytics</Button>
          </Link>
        </Card>

        <Card title="System Status">
          <p className="text-gray-600 mb-4">
            Monitor agent health, API status, and system resources.
          </p>
          <Button size="sm" variant="secondary">Coming Soon</Button>
        </Card>
      </div>
    </div>
  );
};

export default HomePage;
