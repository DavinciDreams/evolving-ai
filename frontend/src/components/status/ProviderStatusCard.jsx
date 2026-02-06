import React, { useState } from 'react';
import Card from '../common/Card';
import Badge from '../common/Badge';
import { formatDuration, formatRelativeTime } from '../../utils/formatting';

const ProviderStatusCard = ({ providersStatus, className = '' }) => {
  const [expanded, setExpanded] = useState(false);
  
  if (!providersStatus) {
    return (
      <Card title="LLM Providers" className={className}>
        <div className="flex items-center justify-center py-8">
          <div className="text-gray-500">Loading provider status...</div>
        </div>
      </Card>
    );
  }

  const { providers, provider_count, history_points } = providersStatus;

  const getProviderIcon = (providerName) => {
    const name = providerName.toLowerCase();
    if (name.includes('openai')) return '🤖';
    if (name.includes('anthropic') || name.includes('claude')) return '🧠';
    if (name.includes('openrouter')) return '🌐';
    if (name.includes('minimax')) return '⚡';
    return '🔮';
  };

  const getAvailabilityColor = (available) => {
    return available ? 'green' : 'red';
  };

  const getResponseTimeColor = (responseTime) => {
    if (!responseTime) return 'gray';
    if (responseTime < 1000) return 'green'; // < 1s
    if (responseTime < 3000) return 'yellow'; // < 3s
    return 'red'; // >= 3s
  };

  const renderProviderStatus = (providerName, providerData) => {
    const isAvailable = providerData.available !== false;
    const responseTime = providerData.response_time;
    const lastUsed = providerData.last_used ? new Date(providerData.last_used) : null;
    const errorRate = providerData.error_rate || 0;
    const requestCount = providerData.request_count || 0;
    const successRate = ((1 - errorRate) * 100).toFixed(1);

    return (
      <div key={providerName} className="border border-gray-200 rounded-lg p-4 mb-3">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center space-x-3">
            <span className="text-xl">{getProviderIcon(providerName)}</span>
            <div>
              <h4 className="font-medium text-gray-900">{providerName}</h4>
              {providerData.model && (
                <div className="text-sm text-gray-500">Model: {providerData.model}</div>
              )}
            </div>
          </div>
          <div className="flex items-center space-x-2">
            <Badge variant={getAvailabilityColor(isAvailable)} size="sm">
              {isAvailable ? 'Online' : 'Offline'}
            </Badge>
            {providerData.healthy !== undefined && (
              <Badge variant={providerData.healthy ? 'success' : 'danger'} size="sm">
                {providerData.healthy ? 'Healthy' : 'Unhealthy'}
              </Badge>
            )}
          </div>
        </div>

        {/* Performance Metrics */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-3">
          <div>
            <div className="text-xs text-gray-500">Response Time</div>
            <div className={`font-medium text-${getResponseTimeColor(responseTime)}-600`}>
              {responseTime ? `${responseTime}ms` : 'N/A'}
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-500">Success Rate</div>
            <div className={`font-medium ${successRate >= 95 ? 'text-green-600' : successRate >= 80 ? 'text-yellow-600' : 'text-red-600'}`}>
              {successRate}%
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-500">Requests</div>
            <div className="font-medium">{requestCount}</div>
          </div>
          <div>
            <div className="text-xs text-gray-500">Last Used</div>
            <div className="font-medium">
              {lastUsed ? formatRelativeTime(lastUsed) : 'Never'}
            </div>
          </div>
        </div>

        {/* Expanded Details */}
        {expanded && (
          <div className="border-t border-gray-200 pt-3 mt-3">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
              {providerData.endpoint && (
                <div>
                  <div className="text-gray-500">Endpoint</div>
                  <div className="font-mono text-xs break-all">{providerData.endpoint}</div>
                </div>
              )}
              {providerData.version && (
                <div>
                  <div className="text-gray-500">Version</div>
                  <div className="font-medium">{providerData.version}</div>
                </div>
              )}
              {providerData.rate_limit && (
                <div>
                  <div className="text-gray-500">Rate Limit</div>
                  <div className="font-medium">{providerData.rate_limit}</div>
                </div>
              )}
              {providerData.cost_per_token && (
                <div>
                  <div className="text-gray-500">Cost/Token</div>
                  <div className="font-medium">${providerData.cost_per_token}</div>
                </div>
              )}
              {providerData.last_error && (
                <div className="md:col-span-2">
                  <div className="text-gray-500">Last Error</div>
                  <div className="font-medium text-red-600">{providerData.last_error}</div>
                </div>
              )}
              {providerData.features && (
                <div className="md:col-span-2">
                  <div className="text-gray-500">Features</div>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {providerData.features.map(feature => (
                      <Badge key={feature} variant="secondary" size="sm">
                        {feature}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Status Bar */}
        <div className="mt-3">
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div
              className={`h-2 rounded-full transition-all duration-300 ${
                isAvailable ? 'bg-green-500' : 'bg-red-500'
              }`}
              style={{ width: `${isAvailable ? successRate : 0}%` }}
            />
          </div>
        </div>
      </div>
    );
  };

  const getOverallStatus = () => {
    const availableProviders = Object.values(providers).filter(p => p.available !== false).length;
    const totalProviders = provider_count;
    
    if (totalProviders === 0) return { status: 'unknown', color: 'gray', text: 'No Providers' };
    if (availableProviders === totalProviders) return { status: 'healthy', color: 'green', text: 'All Online' };
    if (availableProviders > 0) return { status: 'warning', color: 'yellow', text: `${availableProviders}/${totalProviders} Online` };
    return { status: 'critical', color: 'red', text: 'All Offline' };
  };

  const overallStatus = getOverallStatus();

  return (
    <Card
      title="LLM Providers"
      className={className}
      action={
        <div className="flex items-center space-x-2">
          <Badge variant={overallStatus.status === 'healthy' ? 'success' : 
                         overallStatus.status === 'warning' ? 'warning' : 
                         overallStatus.status === 'critical' ? 'danger' : 'secondary'}>
            {overallStatus.text}
          </Badge>
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-gray-500 hover:text-gray-700 transition-colors"
          >
            {expanded ? 'Collapse' : 'Expand'}
          </button>
        </div>
      }
    >
      <div className="space-y-4">
        {/* Overview */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="text-center">
            <div className={`text-2xl font-bold text-${overallStatus.color}-600`}>
              {provider_count}
            </div>
            <div className="text-sm text-gray-500">Total Providers</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-green-600">
              {Object.values(providers).filter(p => p.available !== false).length}
            </div>
            <div className="text-sm text-gray-500">Available</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-gray-900">
              {Object.values(providers).reduce((sum, p) => sum + (p.request_count || 0), 0)}
            </div>
            <div className="text-sm text-gray-500">Total Requests</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-gray-900">
              {Object.keys(history_points).reduce((sum, key) => sum + history_points[key], 0)}
            </div>
            <div className="text-sm text-gray-500">Data Points</div>
          </div>
        </div>

        {/* Provider List */}
        {Object.keys(providers).length > 0 ? (
          <div>
            <h4 className="text-sm font-semibold text-gray-700 mb-3">Provider Status</h4>
            <div className="space-y-3">
              {Object.entries(providers).map(([name, data]) => renderProviderStatus(name, data))}
            </div>
          </div>
        ) : (
          <div className="text-center py-8 text-gray-500 border-2 border-dashed border-gray-200 rounded-lg">
            <div className="text-lg mb-2">🤖</div>
            <div>No LLM providers configured</div>
            <div className="text-sm mt-1">Configure providers to enable AI features</div>
          </div>
        )}

        {/* Performance Summary */}
        {Object.keys(providers).length > 0 && (
          <div className="border-t border-gray-200 pt-4">
            <h4 className="text-sm font-semibold text-gray-700 mb-3">Performance Summary</h4>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {Object.entries(providers).map(([name, data]) => {
                const avgResponseTime = data.response_time || 0;
                const successRate = ((1 - (data.error_rate || 0)) * 100).toFixed(1);
                
                return (
                  <div key={name} className="text-center p-3 bg-gray-50 rounded-lg">
                    <div className="font-medium text-sm text-gray-900 mb-1">{name}</div>
                    <div className="text-xs text-gray-500">
                      <div>Response: {avgResponseTime}ms</div>
                      <div>Success: {successRate}%</div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </Card>
  );
};

export default ProviderStatusCard;