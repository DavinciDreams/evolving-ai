import { useQuery } from '@tanstack/react-query';
import Card from '../components/common/Card';
import Badge from '../components/common/Badge';
import Spinner from '../components/common/Spinner';
import { analyticsService } from '../services/analyticsService';
import { formatNumber } from '../utils/formatting';
import { useDiscordStatus } from '../hooks/useDiscord';

const AnalyticsPage = () => {
  const { data: status, isLoading, error } = useQuery({
    queryKey: ['agent-status'],
    queryFn: analyticsService.getStatus,
    refetchInterval: 30000, // Refresh every 30 seconds
  });

  const { data: discordStatus, isLoading: discordLoading } = useDiscordStatus();

  return (
    <div className="max-w-7xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Analytics Dashboard</h1>
        <p className="text-gray-600 mt-1">View system metrics and performance trends</p>
      </div>

      {isLoading ? (
        <Card>
          <Spinner className="h-64" />
        </Card>
      ) : error ? (
        <Card>
          <div className="text-center text-red-600 py-8">
            Error loading analytics: {error.message}
          </div>
        </Card>
      ) : status ? (
        <>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
            <Card>
              <div className="text-center">
                <p className="text-sm text-gray-600 mb-2">Total Interactions</p>
                <p className="text-3xl font-bold text-indigo-600">
                  {formatNumber(status.interaction_count || 0)}
                </p>
              </div>
            </Card>

            <Card>
              <div className="text-center">
                <p className="text-sm text-gray-600 mb-2">Memories Stored</p>
                <p className="text-3xl font-bold text-green-600">
                  {formatNumber(status.memory_count || 0)}
                </p>
              </div>
            </Card>

            <Card>
              <div className="text-center">
                <p className="text-sm text-gray-600 mb-2">Knowledge Items</p>
                <p className="text-3xl font-bold text-blue-600">
                  {formatNumber(status.knowledge_count || 0)}
                </p>
              </div>
            </Card>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <Card title="Agent Status">
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-gray-600">Status</span>
                  <Badge variant="success">Active</Badge>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-gray-600">Version</span>
                  <span className="text-gray-900 font-medium">{status.version || 'v1.0.0'}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-gray-600">Uptime</span>
                  <span className="text-gray-900 font-medium">{status.uptime || 'N/A'}</span>
                </div>
              </div>
            </Card>

            <Card title="Discord Integration">
              {discordLoading ? (
                <Spinner size="sm" />
              ) : discordStatus ? (
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-gray-600">Status</span>
                    <Badge variant={discordStatus.connected ? 'success' : discordStatus.enabled ? 'warning' : 'secondary'}>
                      {discordStatus.connected ? 'Connected' : discordStatus.enabled ? 'Disconnected' : 'Disabled'}
                    </Badge>
                  </div>
                  {discordStatus.connected && (
                    <>
                      <div className="flex items-center justify-between">
                        <span className="text-gray-600">Bot Name</span>
                        <span className="text-gray-900 font-medium">{discordStatus.bot_name}</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-gray-600">Servers</span>
                        <span className="text-gray-900 font-medium">{discordStatus.guild_count}</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-gray-600">Channels</span>
                        <span className="text-gray-900 font-medium">{discordStatus.allowed_channels}</span>
                      </div>
                    </>
                  )}
                </div>
              ) : (
                <p className="text-gray-500">Discord status unavailable</p>
              )}
            </Card>
          </div>
        </>
      ) : (
        <Card>
          <div className="text-center text-gray-500 py-8">
            No analytics data available
          </div>
        </Card>
      )}
    </div>
  );
};

export default AnalyticsPage;
