import Card from '../components/common/Card';
import Button from '../components/common/Button';
import { API_BASE_URL } from '../utils/constants';

const DocsPage = () => {
  const docsUrl = `${API_BASE_URL}/docs`;
  const reDocUrl = `${API_BASE_URL}/redoc`;

  const apiEndpoints = [
    {
      category: 'General',
      endpoints: [
        { method: 'GET', path: '/', description: 'Root endpoint with basic information' },
        { method: 'GET', path: '/status', description: 'Get current agent status' },
        { method: 'GET', path: '/health', description: 'Health check endpoint' },
      ],
    },
    {
      category: 'Interaction',
      endpoints: [
        { method: 'POST', path: '/chat', description: 'Send query to agent and receive response' },
      ],
    },
    {
      category: 'Memory',
      endpoints: [
        { method: 'GET', path: '/memories', description: 'Retrieve stored memories' },
      ],
    },
    {
      category: 'Knowledge',
      endpoints: [
        { method: 'GET', path: '/knowledge', description: 'Retrieve knowledge base items' },
      ],
    },
    {
      category: 'Measured Steward',
      endpoints: [
        { method: 'GET', path: '/steward/status', description: 'Inspect runtime, dream, and measured-adaptation telemetry' },
        { method: 'POST', path: '/steward/dream', description: 'Request one bounded consolidation job; returns a job receipt' },
        { method: 'POST', path: '/steward/improvement/evaluate', description: 'Evaluate a closed strategy against explicit development and holdout fixtures' },
        { method: 'POST', path: '/steward/improvement/promote', description: 'Promote a measured strategy after its evidence gate passes' },
        { method: 'POST', path: '/steward/improvement/rollback', description: 'Roll back a strategy using its expected revision' },
        { method: 'GET', path: '/analysis-history', description: 'Read bounded, redacted historical analysis records; never triggers analysis' },
      ],
    },
    {
      category: 'GitHub',
      endpoints: [
        { method: 'GET', path: '/github/status', description: 'Get GitHub integration status' },
        { method: 'GET', path: '/github/repository', description: 'Get repository information' },
        { method: 'GET', path: '/github/pull-requests', description: 'Get open pull requests' },
        { method: 'GET', path: '/github/commits', description: 'Get recent commits' },
        { method: 'GET', path: '/github/improvement-history', description: 'Get improvement history' },
      ],
    },
    {
      category: 'Optional Media and Connectors',
      endpoints: [
        { method: 'GET', path: '/media/status', description: 'Inspect enabled, configured, and ready media capabilities' },
        { method: 'POST', path: '/media/vision', description: 'Analyze a bounded image upload; disabled by default' },
        { method: 'POST', path: '/media/transcribe', description: 'Transcribe bounded audio; disabled by default' },
        { method: 'POST', path: '/media/speech', description: 'Generate disclosed AI speech; disabled by default' },
        { method: 'GET', path: '/connectors/status', description: 'Inspect reviewed connector manifests and readiness' },
        { method: 'POST', path: '/connectors/webhooks/app-webhook', description: 'Receive signed untrusted app events into a review-only inbox' },
        { method: 'GET', path: '/connectors/events', description: 'Read pending app events; no automatic tool execution' },
      ],
    },
    {
      category: 'Discord',
      endpoints: [
        { method: 'GET', path: '/discord/status', description: 'Get Discord bot status' },
      ],
    },
    {
      category: 'Web Search',
      endpoints: [
        { method: 'POST', path: '/web-search', description: 'Search the web for information' },
        { method: 'GET', path: '/web-search/status', description: 'Get web search status' },
      ],
    },
  ];

  const getMethodColor = (method) => {
    const colors = {
      GET: 'bg-blue-100 text-blue-800',
      POST: 'bg-green-100 text-green-800',
      PUT: 'bg-yellow-100 text-yellow-800',
      DELETE: 'bg-red-100 text-red-800',
    };
    return colors[method] || 'bg-gray-100 text-gray-800';
  };

  return (
    <div className="max-w-7xl mx-auto">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">API Documentation</h1>
        <p className="mt-2 text-gray-600">
          Complete API reference for the Evolving AI Agent system.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
        <Card title="Interactive API Documentation">
          <p className="text-gray-600 mb-4">
            Explore and test the API endpoints using the interactive Swagger UI interface.
          </p>
          <a href={docsUrl} target="_blank" rel="noopener noreferrer">
            <Button>Open Swagger UI</Button>
          </a>
        </Card>

        <Card title="Alternative Documentation">
          <p className="text-gray-600 mb-4">
            View the API documentation in ReDoc format for a different perspective.
          </p>
          <a href={reDocUrl} target="_blank" rel="noopener noreferrer">
            <Button variant="secondary">Open ReDoc</Button>
          </a>
        </Card>
      </div>

      <Card title="API Endpoints Overview">
        <p className="mb-4 text-sm text-gray-700">
          Private endpoints require project authentication. Legacy POST /analyze,
          /self-improve, /github/demo-pr, and /github/issue are retired (HTTP 410).
          Measured strategy adaptation does not modify repository code or publish externally.
        </p>
        <div className="space-y-6">
          {apiEndpoints.map((category) => (
            <div key={category.category}>
              <h3 className="text-lg font-semibold text-gray-900 mb-3">
                {category.category}
              </h3>
              <div className="space-y-2">
                {category.endpoints.map((endpoint, index) => (
                  <div
                    key={index}
                    className="flex items-start gap-3 p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors"
                  >
                    <span
                      className={`px-2 py-1 text-xs font-semibold rounded ${getMethodColor(
                        endpoint.method
                      )}`}
                    >
                      {endpoint.method}
                    </span>
                    <div className="flex-1">
                      <code className="text-sm font-mono text-gray-900">
                        {endpoint.path}
                      </code>
                      <p className="text-sm text-gray-600 mt-1">
                        {endpoint.description}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </Card>

      <div className="mt-8">
        <Card title="Getting Started">
          <div className="prose max-w-none">
            <h3 className="text-lg font-semibold text-gray-900 mb-3">
              Base URL
            </h3>
            <code className="block p-3 bg-gray-900 text-gray-100 rounded-lg mb-4">
              {API_BASE_URL}
            </code>

            <h3 className="text-lg font-semibold text-gray-900 mb-3">
              Quick Example
            </h3>
            <p className="text-gray-600 mb-2">
              Send a chat message to the agent. Supply the project credential through your
              secure client configuration; do not paste a real key into documentation or shell history:
            </p>
            <pre className="p-4 bg-gray-900 text-gray-100 rounded-lg overflow-x-auto">
              <code>{`curl -X POST "${API_BASE_URL}/chat" \\
  -H "Content-Type: application/json" \\
  -d '{
    "query": "What are the best practices for code optimization?",
    "context_hints": ["performance"]
  }'`}</code>
            </pre>

            <h3 className="text-lg font-semibold text-gray-900 mb-3 mt-6">
              Features
            </h3>
            <ul className="list-disc list-inside space-y-2 text-gray-600">
              <li>Interactive chat interface with intelligent responses</li>
              <li>Project-scoped HAM/PostgreSQL memory with explicit storage status</li>
              <li>Real-time web search with multiple provider support</li>
              <li>Bounded dreaming and measured, reversible response-strategy adaptation</li>
              <li>Automatic knowledge extraction and organization</li>
              <li>Multi-LLM support (OpenAI, Anthropic, OpenRouter)</li>
              <li>Read-only GitHub visibility; publication requires a separate authorized workflow</li>
              <li>Discord bot interface for real-time interactions</li>
            </ul>

            <h3 className="text-lg font-semibold text-gray-900 mb-3 mt-6">
              Need Help?
            </h3>
            <p className="text-gray-600">
              For detailed information about request/response formats, authentication,
              and error handling, visit the{' '}
              <a
                href={docsUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="text-indigo-600 hover:text-indigo-800 font-medium"
              >
                interactive documentation
              </a>
              .
            </p>
          </div>
        </Card>
      </div>
    </div>
  );
};

export default DocsPage;
