import { useState, useEffect } from 'react';
import Card from '../components/common/Card';
import Badge from '../components/common/Badge';
import Spinner from '../components/common/Spinner';
import { getAgentStatus, getHealthStatus } from '../services/api';
import { getGitHubStatus } from '../services/githubService';
import { getDiscordStatus } from '../services/discordService';

const StatusPage = () => {
  const [loading, setLoading] = useState(true);
  const [agentStatus, setAgentStatus] = useState(null);
  const [healthStatus, setHealthStatus] = useState(null);
  const [githubStatus, setGitHubStatus] = useState(null);
  const [discordStatus, setDiscordStatus] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchAllStatus();
    // Refresh status every 30 seconds
    const interval = setInterval(fetchAllStatus, 30000);
    return () => clearInterval(interval);
  }, []);

  const fetchAllStatus = async () => {
    try {
      setLoading(true);
      setError(null);

      const [agent, health, github, discord] = await Promise.all([
        getAgentStatus().catch(err => ({ error: err.message })),
        getHealthStatus().catch(err => ({ error: err.message })),
        getGitHubStatus().catch(err => ({ error: err.message })),
        getDiscordStatus().catch(err => ({ error: err.message })),
      ]);

      setAgentStatus(agent);
      setHealthStatus(health);
      setGitHubStatus(github);
      setDiscordStatus(discord);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const getStatusBadge = (isHealthy) => {
    if (isHealthy) {
      return <Badge color="success">Healthy</Badge>;
    }
    return <Badge color="danger">Unhealthy</Badge>;
  };

  const getConnectionBadge = (isConnected) => {
    if (isConnected) {
      return <Badge color="success">Connected</Badge>;
    }
    return <Badge color="danger">Disconnected</Badge>;
  };

  if (loading && !agentStatus) {
    return (
      <div className="flex justify-center items-center min-h-screen">
        <Spinner size="lg" />
      </div>
    );
  }

  if (error && !agentStatus) {
    return (
      <div className="max-w-7xl mx-auto">
        <Card title="Error Loading Status">
          <p className="text-red-600">{error}</p>
        </Card>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">System Status</h1>
        <p className="mt-2 text-gray-600">
          Monitor the health and status of all system components.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Agent Status */}
        <Card title="Agent Status">
          {agentStatus?.error ? (
            <div className="text-red-600">
              <p className="font-semibold">Error:</p>
              <p>{agentStatus.error}</p>
            </div>
          ) : (
            <div className="space-y-3">
              <div className="flex justify-between items-center">
                <span className="text-gray-600">Initialized</span>
                {getStatusBadge(agentStatus?.is_initialized)}
              </div>
              <div className="flex justify-between items-center">
                <span className="text-gray-600">Session ID</span>
                <span className="text-sm font-mono text-gray-800">
                  {agentStatus?.session_id || 'N/A'}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-gray-600">Total Interactions</span>
                <span className="text-gray-800 font-semibold">
                  {agentStatus?.total_interactions || 0}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-gray-600">Memory Count</span>
                <span className="text-gray-800 font-semibold">
                  {agentStatus?.memory_count || 0}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-gray-600">Knowledge Count</span>
                <span className="text-gray-800 font-semibold">
                  {agentStatus?.knowledge_count || 0}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-gray-600">Uptime</span>
                <span className="text-gray-800">{agentStatus?.uptime || 'Active'}</span>
              </div>
            </div>
          )}
        </Card>

        {/* API Health */}
        <Card title="API Health">
          {healthStatus?.error ? (
            <div className="text-red-600">
              <p className="font-semibold">Error:</p>
              <p>{healthStatus.error}</p>
            </div>
          ) : (
            <div className="space-y-3">
              <div className="flex justify-between items-center">
                <span className="text-gray-600">Status</span>
                {getStatusBadge(healthStatus?.status === 'healthy')}
              </div>
              <div className="flex justify-between items-center">
                <span className="text-gray-600">Agent Initialized</span>
                {getStatusBadge(healthStatus?.agent_initialized)}
              </div>
              <div className="flex justify-between items-center">
                <span className="text-gray-600">GitHub Available</span>
                {getStatusBadge(healthStatus?.github_available)}
              </div>
              <div className="flex justify-between items-center">
                <span className="text-gray-600">Last Check</span>
                <span className="text-sm text-gray-800">
                  {healthStatus?.timestamp
                    ? new Date(healthStatus.timestamp).toLocaleTimeString()
                    : 'N/A'}
                </span>
              </div>
            </div>
          )}
        </Card>

        {/* GitHub Integration */}
        <Card title="GitHub Integration">
          {githubStatus?.error ? (
            <div className="text-red-600">
              <p className="font-semibold">Error:</p>
              <p>{githubStatus.error}</p>
            </div>
          ) : (
            <div className="space-y-3">
              <div className="flex justify-between items-center">
                <span className="text-gray-600">Connection</span>
                {getConnectionBadge(githubStatus?.github_connected)}
              </div>
              {githubStatus?.github_connected && (
                <>
                  <div className="flex justify-between items-center">
                    <span className="text-gray-600">Repository</span>
                    <span className="text-sm font-mono text-gray-800">
                      {githubStatus?.repository_name || 'N/A'}
                    </span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-gray-600">Local Repo</span>
                    {getStatusBadge(githubStatus?.local_repo_available)}
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-gray-600">Auto PR</span>
                    {getStatusBadge(githubStatus?.auto_pr_enabled)}
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-gray-600">Open PRs</span>
                    <span className="text-gray-800 font-semibold">
                      {githubStatus?.open_prs_count || 0}
                    </span>
                  </div>
                </>
              )}
            </div>
          )}
        </Card>

        {/* Discord Integration */}
        <Card title="Discord Integration">
          {discordStatus?.error ? (
            <div className="text-red-600">
              <p className="font-semibold">Error:</p>
              <p>{discordStatus.error}</p>
            </div>
          ) : (
            <div className="space-y-3">
              <div className="flex justify-between items-center">
                <span className="text-gray-600">Enabled</span>
                {getStatusBadge(discordStatus?.enabled)}
              </div>
              {discordStatus?.enabled && (
                <>
                  <div className="flex justify-between items-center">
                    <span className="text-gray-600">Connection</span>
                    {getConnectionBadge(discordStatus?.connected)}
                  </div>
                  {discordStatus?.connected && (
                    <>
                      <div className="flex justify-between items-center">
                        <span className="text-gray-600">Bot Name</span>
                        <span className="text-gray-800">
                          {discordStatus?.bot_name || 'N/A'}
                        </span>
                      </div>
                      <div className="flex justify-between items-center">
                        <span className="text-gray-600">Guild Count</span>
                        <span className="text-gray-800 font-semibold">
                          {discordStatus?.guild_count || 0}
                        </span>
                      </div>
                      <div className="flex justify-between items-center">
                        <span className="text-gray-600">Allowed Channels</span>
                        <span className="text-gray-800 font-semibold">
                          {discordStatus?.allowed_channels || 0}
                        </span>
                      </div>
                      <div className="flex justify-between items-center">
                        <span className="text-gray-600">Mention Required</span>
                        {getStatusBadge(!discordStatus?.mention_required)}
                      </div>
                    </>
                  )}
                </>
              )}
            </div>
          )}
        </Card>
      </div>

      <div className="mt-4 text-center">
        <button
          onClick={fetchAllStatus}
          disabled={loading}
          className="text-indigo-600 hover:text-indigo-800 font-medium"
        >
          {loading ? 'Refreshing...' : 'Refresh Status'}
        </button>
      </div>
    </div>
  );
};

export default StatusPage;
