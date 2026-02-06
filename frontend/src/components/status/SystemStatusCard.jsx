import React, { useState, useEffect } from 'react';
import Card from '../common/Card';
import Badge from '../common/Badge';
import { formatBytes, formatPercentage } from '../../utils/formatting';

const SystemStatusCard = ({ systemStatus, className = '' }) => {
  const [expanded, setExpanded] = useState(false);
  
  if (!systemStatus) {
    return (
      <Card title="System Health" className={className}>
        <div className="flex items-center justify-center py-8">
          <div className="text-gray-500">Loading system status...</div>
        </div>
      </Card>
    );
  }

  const { metrics, alerts, alert_count, monitoring_active, history_points } = systemStatus;

  // Determine overall health status
  const getHealthStatus = () => {
    if (!monitoring_active) return { status: 'unknown', color: 'gray', text: 'Monitoring Inactive' };
    if (alert_count > 0) {
      const criticalAlerts = alerts.filter(a => a.severity === 'critical').length;
      if (criticalAlerts > 0) return { status: 'critical', color: 'red', text: 'Critical Issues' };
      return { status: 'warning', color: 'yellow', text: 'Warning' };
    }
    if (!metrics) return { status: 'unknown', color: 'gray', text: 'No Data' };
    return { status: 'healthy', color: 'green', text: 'Healthy' };
  };

  const healthStatus = getHealthStatus();

  const renderMetricBar = (label, value, maxValue, unit = '', color = 'blue') => {
    const percentage = (value / maxValue) * 100;
    const getColorClass = () => {
      if (percentage > 90) return 'bg-red-500';
      if (percentage > 75) return 'bg-yellow-500';
      return `bg-${color}-500`;
    };

    return (
      <div className="mb-4">
        <div className="flex justify-between text-sm mb-1">
          <span className="text-gray-600">{label}</span>
          <span className="font-medium">
            {unit === '%' ? formatPercentage(value) : `${value}${unit}`}
          </span>
        </div>
        <div className="w-full bg-gray-200 rounded-full h-2">
          <div
            className={`${getColorClass()} h-2 rounded-full transition-all duration-300`}
            style={{ width: `${Math.min(percentage, 100)}%` }}
          />
        </div>
      </div>
    );
  };

  const renderAlertItem = (alert, index) => {
    const getSeverityColor = (severity) => {
      switch (severity) {
        case 'critical': return 'bg-red-100 text-red-800 border-red-200';
        case 'warning': return 'bg-yellow-100 text-yellow-800 border-yellow-200';
        case 'info': return 'bg-blue-100 text-blue-800 border-blue-200';
        default: return 'bg-gray-100 text-gray-800 border-gray-200';
      }
    };

    return (
      <div
        key={alert.id || index}
        className={`p-3 rounded-lg border ${getSeverityColor(alert.severity)} mb-2`}
      >
        <div className="flex justify-between items-start">
          <div className="flex-1">
            <div className="font-medium text-sm">{alert.message}</div>
            {alert.details && (
              <div className="text-xs mt-1 opacity-75">
                {Object.entries(alert.details).map(([key, value]) => (
                  <span key={key} className="mr-3">
                    {key}: {typeof value === 'number' ? formatPercentage(value) : value}
                  </span>
                ))}
              </div>
            )}
          </div>
          <Badge variant={alert.severity} size="sm">
            {alert.severity}
          </Badge>
        </div>
        <div className="text-xs mt-2 opacity-60">
          {new Date(alert.timestamp).toLocaleString()}
        </div>
      </div>
    );
  };

  return (
    <Card
      title="System Health"
      className={className}
      action={
        <div className="flex items-center space-x-2">
          <Badge
            variant={healthStatus.status === 'healthy' ? 'success' : 
                   healthStatus.status === 'warning' ? 'warning' : 
                   healthStatus.status === 'critical' ? 'danger' : 'secondary'}
          >
            {healthStatus.text}
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
        {/* Status Overview */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="text-center">
            <div className={`text-2xl font-bold text-${healthStatus.color}-600`}>
              {healthStatus.text}
            </div>
            <div className="text-sm text-gray-500">Status</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-gray-900">
              {alert_count}
            </div>
            <div className="text-sm text-gray-500">Active Alerts</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-gray-900">
              {history_points}
            </div>
            <div className="text-sm text-gray-500">Data Points</div>
          </div>
          <div className="text-center">
            <div className={`text-2xl font-bold ${monitoring_active ? 'text-green-600' : 'text-gray-400'}`}>
              {monitoring_active ? 'Active' : 'Inactive'}
            </div>
            <div className="text-sm text-gray-500">Monitoring</div>
          </div>
        </div>

        {/* System Metrics */}
        {metrics && (
          <div>
            <h4 className="text-sm font-semibold text-gray-700 mb-3">Resource Usage</h4>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {renderMetricBar('CPU', metrics.cpu.percent, 100, '%', 'blue')}
              {renderMetricBar('Memory', metrics.memory.percent, 100, '%', 'green')}
              {renderMetricBar('Disk', metrics.disk.percent, 100, '%', 'purple')}
            </div>
            
            {expanded && (
              <div className="mt-4 pt-4 border-t border-gray-200">
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                  <div>
                    <div className="text-gray-500">CPU Cores</div>
                    <div className="font-medium">{metrics.cpu.count}</div>
                  </div>
                  <div>
                    <div className="text-gray-500">Memory Total</div>
                    <div className="font-medium">{formatBytes(metrics.memory.total)}</div>
                  </div>
                  <div>
                    <div className="text-gray-500">Disk Total</div>
                    <div className="font-medium">{formatBytes(metrics.disk.total)}</div>
                  </div>
                  <div>
                    <div className="text-gray-500">Processes</div>
                    <div className="font-medium">{metrics.processes}</div>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Alerts */}
        {alerts && alerts.length > 0 && (
          <div>
            <h4 className="text-sm font-semibold text-gray-700 mb-3">Active Alerts</h4>
            <div className="max-h-60 overflow-y-auto">
              {alerts.slice(0, expanded ? alerts.length : 3).map(renderAlertItem)}
              {!expanded && alerts.length > 3 && (
                <div className="text-center text-sm text-gray-500 mt-2">
                  +{alerts.length - 3} more alerts
                </div>
              )}
            </div>
          </div>
        )}

        {/* No Data State */}
        {!metrics && !alerts && (
          <div className="text-center py-8 text-gray-500">
            No system metrics available
          </div>
        )}
      </div>
    </Card>
  );
};

export default SystemStatusCard;