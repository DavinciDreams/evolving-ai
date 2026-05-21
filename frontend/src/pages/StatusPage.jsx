import { useQuery } from '@tanstack/react-query';
import Card from '../components/common/Card';
import Badge from '../components/common/Badge';
import Spinner from '../components/common/Spinner';
import { api } from '../services/api';
import { getGitHubStatus } from '../services/githubService';
import { getDiscordStatus } from '../services/discordService';

const StatusPage = () => {
  const { data: agentStatus, isLoading: loadingStatus, error: statusError } = useQuery({
    queryKey: ['status'],
    queryFn: () => api.get('/status').then(r => r.data),
    refetchInterval: 30000,
  });

  const { data: healthStatus, isLoading: loadingHealth } = useQuery({
    queryKey: ['health'],
    queryFn: () => api.get('/health').then(r => r.data),
    refetchInterval: 30000,
  });

  const { data: githubStatus, isLoading: loadingGithub } = useQuery({
    queryKey: ['github-status'],
    queryFn: getGitHubStatus,
    refetchInterval: 30000,
  });

  const { data: discordStatus, isLoading: loadingDiscord } = useQuery({
    queryKey: ['discord-status'],
    queryFn: getDiscordStatus,
    refetchInterval: 30000,
  });

  const isInitialLoading = loadingStatus && !agentStatus;

  const getStatusBadge = (isHealthy) => {
    if (isHealthy) {
      return <Badge variant="success">Healthy</Badge>;
    }
    return <Badge variant="danger">Unhealthy</Badge>;
  };

  const getConnectionBadge = (isConnected) => {
    if (isConnected) {
      return <Badge variant="success">Connected</Badge>;
    }
    return <Badge variant="danger">Disconnected</Badge>;
  };

  if (isInitialLoading) {
    return (
      <div className="flex justify-center items-center min-h-screen">
        <Spinner size="lg" />
      </div>
    );
  }

  if (statusError && !agentStatus) {
    return (
      <div className="max-w-7xl mx-auto">
        <Card title="Error Loading Status">
          <p className="text-red-600">{statusError.message}</p>
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
          {loadingStatus && !agentStatus ? (
            <Spinner size="sm" />
          ) : agentStatus?.error ? (
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
          {loadingHealth && !healthStatus ? (
            <Spinner size="sm" />
          ) : healthStatus?.error ? (
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
          {loadingGithub && !githubStatus ? (
            <Spinner size="sm" />
          ) : githubStatus?.error ? (
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
          {loadingDiscord && !discordStatus ? (
            <Spinner size="sm" />
          ) : discordStatus?.error ? (
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
    </div>
  );
};

export default StatusPage;
