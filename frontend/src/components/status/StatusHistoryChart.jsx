import React, { useState, useMemo } from 'react';
import Card from '../common/Card';
import Badge from '../common/Badge';
import { formatDuration, formatRelativeTime } from '../../utils/formatting';

// Simple chart components since we don't have a chart library
const SimpleLineChart = ({ data, color = 'blue', height = 200 }) => {
  if (!data || data.length === 0) {
    return (
      <div className="flex items-center justify-center h-48 text-gray-500 border-2 border-dashed border-gray-200 rounded-lg">
        No data available
      </div>
    );
  }

  const maxValue = Math.max(...data.map(d => d.value));
  const minValue = Math.min(...data.map(d => d.value));
  const range = maxValue - minValue || 1;

  const points = data.map((point, index) => {
    const x = (index / (data.length - 1)) * 100;
    const y = 100 - ((point.value - minValue) / range) * 100;
    return `${x},${y}`;
  }).join(' ');

  return (
    <div className="relative">
      <svg
        width="100%"
        height={height}
        className="border border-gray-200 rounded-lg"
        viewBox="0 0 100 100"
        preserveAspectRatio="none"
      >
        {/* Grid lines */}
        <line x1="0" y1="25" x2="100" y2="25" stroke="#e5e7eb" strokeWidth="0.5" />
        <line x1="0" y1="50" x2="100" y2="50" stroke="#e5e7eb" strokeWidth="0.5" />
        <line x1="0" y1="75" x2="100" y2="75" stroke="#e5e7eb" strokeWidth="0.5" />
        
        {/* Data line */}
        <polyline
          points={points}
          fill="none"
          stroke={`rgb(${color === 'blue' ? '59, 130, 246' : color === 'green' ? '34, 197, 94' : color === 'red' ? '239, 68, 68' : '156, 163, 175'})`}
          strokeWidth="2"
        />
        
        {/* Data points */}
        {data.map((point, index) => {
          const x = (index / (data.length - 1)) * 100;
          const y = 100 - ((point.value - minValue) / range) * 100;
          return (
            <circle
              key={index}
              cx={x}
              cy={y}
              r="1"
              fill={`rgb(${color === 'blue' ? '59, 130, 246' : color === 'green' ? '34, 197, 94' : color === 'red' ? '239, 68, 68' : '156, 163, 175'})`}
            />
          );
        })}
      </svg>
      
      {/* Y-axis labels */}
      <div className="absolute left-0 top-0 h-full flex flex-col justify-between text-xs text-gray-500 -ml-8">
        <span>{maxValue.toFixed(1)}</span>
        <span>{((maxValue + minValue) / 2).toFixed(1)}</span>
        <span>{minValue.toFixed(1)}</span>
      </div>
    </div>
  );
};

const StatusHistoryChart = ({ historyData, className = '' }) => {
  const [timeRange, setTimeRange] = useState(6); // hours
  const [metricType, setMetricType] = useState('cpu'); // cpu, memory, disk, operations, alerts

  if (!historyData) {
    return (
      <Card title="Status History" className={className}>
        <div className="flex items-center justify-center py-8">
          <div className="text-gray-500">Loading history data...</div>
        </div>
      </Card>
    );
  }

  const { system_metrics, operations, alerts, providers, summary, hours } = historyData;

  // Process data for charts
  const chartData = useMemo(() => {
    switch (metricType) {
      case 'cpu':
        return system_metrics.map(metric => ({
          timestamp: metric.timestamp,
          value: metric.cpu.percent,
          label: 'CPU %'
        }));
      case 'memory':
        return system_metrics.map(metric => ({
          timestamp: metric.timestamp,
          value: metric.memory.percent,
          label: 'Memory %'
        }));
      case 'disk':
        return system_metrics.map(metric => ({
          timestamp: metric.timestamp,
          value: metric.disk.percent,
          label: 'Disk %'
        }));
      case 'operations':
        // Count operations per hour
        const operationCounts = {};
        operations.forEach(op => {
          const hour = new Date(op.start_time).toISOString().slice(0, 13);
          operationCounts[hour] = (operationCounts[hour] || 0) + 1;
        });
        return Object.entries(operationCounts).map(([hour, count]) => ({
          timestamp: hour + ':00:00Z',
          value: count,
          label: 'Operations'
        }));
      case 'alerts':
        // Count alerts per hour
        const alertCounts = {};
        alerts.forEach(alert => {
          const hour = new Date(alert.timestamp).toISOString().slice(0, 13);
          alertCounts[hour] = (alertCounts[hour] || 0) + 1;
        });
        return Object.entries(alertCounts).map(([hour, count]) => ({
          timestamp: hour + ':00:00Z',
          value: count,
          label: 'Alerts'
        }));
      default:
        return [];
    }
  }, [system_metrics, operations, alerts, metricType]);

  // Filter data by time range
  const filteredData = useMemo(() => {
    if (!chartData.length) return [];
    
    const cutoffTime = new Date(Date.now() - timeRange * 60 * 60 * 1000);
    return chartData.filter(point => new Date(point.timestamp) >= cutoffTime);
  }, [chartData, timeRange]);

  const getMetricColor = (type) => {
    switch (type) {
      case 'cpu': return 'blue';
      case 'memory': return 'green';
      case 'disk': return 'purple';
      case 'operations': return 'blue';
      case 'alerts': return 'red';
      default: return 'gray';
    }
  };

  const getMetricLabel = (type) => {
    switch (type) {
      case 'cpu': return 'CPU Usage';
      case 'memory': return 'Memory Usage';
      case 'disk': return 'Disk Usage';
      case 'operations': return 'Operations Count';
      case 'alerts': return 'Alerts Count';
      default: return 'Unknown';
    }
  };

  const renderMetricSelector = () => (
    <div className="flex flex-wrap gap-2">
      {[
        { value: 'cpu', label: 'CPU' },
        { value: 'memory', label: 'Memory' },
        { value: 'disk', label: 'Disk' },
        { value: 'operations', label: 'Operations' },
        { value: 'alerts', label: 'Alerts' }
      ].map(metric => (
        <button
          key={metric.value}
          onClick={() => setMetricType(metric.value)}
          className={`px-3 py-1 rounded-lg text-sm font-medium transition-colors ${
            metricType === metric.value
              ? 'bg-blue-500 text-white'
              : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
          }`}
        >
          {metric.label}
        </button>
      ))}
    </div>
  );

  const renderTimeRangeSelector = () => (
    <div className="flex items-center space-x-2">
      <span className="text-sm text-gray-600">Time Range:</span>
      <select
        value={timeRange}
        onChange={(e) => setTimeRange(Number(e.target.value))}
        className="border border-gray-300 rounded px-2 py-1 text-sm"
      >
        <option value={1}>Last Hour</option>
        <option value={6}>Last 6 Hours</option>
        <option value={12}>Last 12 Hours</option>
        <option value={24}>Last 24 Hours</option>
        <option value={48}>Last 48 Hours</option>
      </select>
    </div>
  );

  const renderSummaryStats = () => {
    const latestMetric = system_metrics[system_metrics.length - 1];
    const recentAlerts = alerts.filter(alert => 
      new Date(alert.timestamp) >= new Date(Date.now() - 24 * 60 * 60 * 1000)
    );
    const recentOperations = operations.filter(op => 
      new Date(op.start_time) >= new Date(Date.now() - 24 * 60 * 60 * 1000)
    );

    return (
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <div className="text-center">
          <div className="text-lg font-bold text-gray-900">
            {summary?.system_points || system_metrics.length}
          </div>
          <div className="text-xs text-gray-500">System Data Points</div>
        </div>
        <div className="text-center">
          <div className="text-lg font-bold text-gray-900">
            {summary?.operations_completed || recentOperations.length}
          </div>
          <div className="text-xs text-gray-500">Operations (24h)</div>
        </div>
        <div className="text-center">
          <div className="text-lg font-bold text-gray-900">
            {summary?.alerts_generated || recentAlerts.length}
          </div>
          <div className="text-xs text-gray-500">Alerts (24h)</div>
        </div>
        <div className="text-center">
          <div className="text-lg font-bold text-gray-900">
            {summary?.providers_active || Object.keys(providers).length}
          </div>
          <div className="text-xs text-gray-500">Active Providers</div>
        </div>
      </div>
    );
  };

  return (
    <Card
      title="Status History"
      className={className}
      action={
        <div className="flex items-center space-x-2">
          <Badge variant="secondary">
            {hours}h available
          </Badge>
        </div>
      }
    >
      <div className="space-y-6">
        {/* Summary Stats */}
        {renderSummaryStats()}

        {/* Controls */}
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          {renderMetricSelector()}
          {renderTimeRangeSelector()}
        </div>

        {/* Chart */}
        <div>
          <div className="flex items-center justify-between mb-3">
            <h4 className="text-sm font-semibold text-gray-700">
              {getMetricLabel(metricType)}
            </h4>
            <div className="text-sm text-gray-500">
              {filteredData.length} data points
            </div>
          </div>
          <SimpleLineChart
            data={filteredData}
            color={getMetricColor(metricType)}
            height={200}
          />
        </div>

        {/* Recent Events */}
        <div className="border-t border-gray-200 pt-4">
          <h4 className="text-sm font-semibold text-gray-700 mb-3">Recent Events</h4>
          <div className="space-y-2 max-h-40 overflow-y-auto">
            {alerts.slice(-5).reverse().map((alert, index) => (
              <div key={alert.id || index} className="flex items-center justify-between text-sm">
                <div className="flex items-center space-x-2">
                  <Badge
                    variant={alert.severity === 'critical' ? 'danger' : 
                           alert.severity === 'warning' ? 'warning' : 'info'}
                    size="sm"
                  >
                    {alert.severity}
                  </Badge>
                  <span className="text-gray-700">{alert.message}</span>
                </div>
                <span className="text-gray-500 text-xs">
                  {formatRelativeTime(new Date(alert.timestamp))}
                </span>
              </div>
            ))}
            {alerts.length === 0 && (
              <div className="text-center text-gray-500 text-sm py-2">
                No recent alerts
              </div>
            )}
          </div>
        </div>

        {/* Data Quality Info */}
        <div className="text-xs text-gray-500 border-t border-gray-200 pt-3">
          <div className="flex justify-between">
            <span>Data freshness: {system_metrics.length > 0 ? formatRelativeTime(new Date(system_metrics[system_metrics.length - 1].timestamp)) : 'No data'}</span>
            <span>Update interval: ~30 seconds</span>
          </div>
        </div>
      </div>
    </Card>
  );
};

export default StatusHistoryChart;