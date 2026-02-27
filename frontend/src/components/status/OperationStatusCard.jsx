import React, { useState } from 'react';
import Card from '../common/Card';
import Badge from '../common/Badge';
import Button from '../common/Button';
import { formatDuration, formatRelativeTime } from '../../utils/formatting';

const OperationStatusCard = ({ operationsStatus, className = '' }) => {
  const [showCompleted, setShowCompleted] = useState(false);
  
  if (!operationsStatus) {
    return (
      <Card title="Operations" className={className}>
        <div className="flex items-center justify-center py-8">
          <div className="text-gray-500">Loading operations status...</div>
        </div>
      </Card>
    );
  }

  const { active_operations, active_count, recent_completed, total_completed } = operationsStatus;

  const getOperationIcon = (type) => {
    switch (type) {
      case 'improvement': return '🔧';
      case 'analysis': return '🔍';
      case 'file_improvement': return '📝';
      case 'performance_optimization': return '⚡';
      case 'code_quality': return '✨';
      case 'full_improvement_cycle': return '🔄';
      case 'pr_creation': return '🔀';
      default: return '⚙️';
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'running': return 'blue';
      case 'completed': return 'green';
      case 'failed': return 'red';
      case 'cancelled': return 'gray';
      default: return 'gray';
    }
  };

  const renderProgressBar = (progress, status) => {
    const colorClass = status === 'failed' ? 'bg-red-500' : 
                     status === 'completed' ? 'bg-green-500' : 'bg-blue-500';
    
    return (
      <div className="w-full bg-gray-200 rounded-full h-2">
        <div
          className={`${colorClass} h-2 rounded-full transition-all duration-300`}
          style={{ width: `${Math.min(progress, 100)}%` }}
        />
      </div>
    );
  };

  const renderActiveOperation = (operation, index) => {
    const startTime = new Date(operation.start_time);
    const elapsed = Date.now() - startTime.getTime();
    const estimatedDuration = operation.estimated_duration;
    
    return (
      <div key={operation.id || index} className="border border-gray-200 rounded-lg p-4 mb-3">
        <div className="flex items-start justify-between mb-3">
          <div className="flex items-center space-x-2">
            <span className="text-lg">{getOperationIcon(operation.type)}</span>
            <div>
              <h4 className="font-medium text-gray-900">{operation.description}</h4>
              <div className="text-sm text-gray-500">
                {operation.type.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())}
              </div>
            </div>
          </div>
          <Badge variant={getStatusColor(operation.status)} size="sm">
            {operation.status}
          </Badge>
        </div>

        {/* Progress Bar */}
        <div className="mb-3">
          <div className="flex justify-between text-sm mb-1">
            <span className="text-gray-600">Progress</span>
            <span className="font-medium">{operation.progress}%</span>
          </div>
          {renderProgressBar(operation.progress, operation.status)}
        </div>

        {/* Current Step */}
        {operation.current_step && (
          <div className="text-sm text-gray-600 mb-2">
            <span className="font-medium">Current:</span> {operation.current_step}
          </div>
        )}

        {/* Time Information */}
        <div className="flex justify-between text-xs text-gray-500">
          <span>Started: {formatRelativeTime(startTime)}</span>
          {estimatedDuration && (
            <span>
              Est. remaining: {formatDuration(Math.max(0, estimatedDuration - elapsed / 1000))}
            </span>
          )}
        </div>

        {/* Step Progress */}
        {operation.total_steps && operation.current_step && (
          <div className="mt-2 text-xs text-gray-500">
            Step information available
          </div>
        )}
      </div>
    );
  };

  const renderCompletedOperation = (operation, index) => {
    const startTime = new Date(operation.start_time);
    const endTime = operation.end_time ? new Date(operation.end_time) : new Date();
    const duration = (endTime.getTime() - startTime.getTime()) / 1000;
    
    return (
      <div key={operation.id || index} className="border border-gray-100 rounded-lg p-3 mb-2 bg-gray-50">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <span>{getOperationIcon(operation.type)}</span>
            <div>
              <div className="font-medium text-sm text-gray-900">{operation.description}</div>
              <div className="text-xs text-gray-500">
                {formatDuration(duration)} • {formatRelativeTime(endTime)}
              </div>
            </div>
          </div>
          <div className="flex items-center space-x-2">
            <Badge variant={getStatusColor(operation.status)} size="sm">
              {operation.status}
            </Badge>
            {operation.error && (
              <div className="text-xs text-red-600 max-w-xs truncate" title={operation.error}>
                Error: {operation.error}
              </div>
            )}
          </div>
        </div>
      </div>
    );
  };

  return (
    <Card
      title="Operations"
      className={className}
      action={
        <div className="flex items-center space-x-2">
          <Badge variant={active_count > 0 ? 'primary' : 'secondary'}>
            {active_count} Active
          </Badge>
          {total_completed > 0 && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowCompleted(!showCompleted)}
            >
              {showCompleted ? 'Hide' : 'Show'} Completed
            </Button>
          )}
        </div>
      }
    >
      <div className="space-y-4">
        {/* Active Operations */}
        {active_count > 0 ? (
          <div>
            <h4 className="text-sm font-semibold text-gray-700 mb-3">Active Operations</h4>
            <div className="space-y-3">
              {active_operations.map(renderActiveOperation)}
            </div>
          </div>
        ) : (
          <div className="text-center py-8 text-gray-500 border-2 border-dashed border-gray-200 rounded-lg">
            <div className="text-lg mb-2">🎯</div>
            <div>No active operations</div>
            <div className="text-sm mt-1">System is idle</div>
          </div>
        )}

        {/* Completed Operations */}
        {showCompleted && recent_completed && recent_completed.length > 0 && (
          <div className="border-t border-gray-200 pt-4">
            <h4 className="text-sm font-semibold text-gray-700 mb-3">
              Recently Completed ({recent_completed.length})
            </h4>
            <div className="max-h-60 overflow-y-auto">
              {recent_completed.map(renderCompletedOperation)}
            </div>
          </div>
        )}

        {/* Statistics */}
        {total_completed > 0 && (
          <div className="border-t border-gray-200 pt-4">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
              <div>
                <div className="text-lg font-bold text-gray-900">{active_count}</div>
                <div className="text-xs text-gray-500">Active</div>
              </div>
              <div>
                <div className="text-lg font-bold text-green-600">
                  {recent_completed?.filter(op => op.status === 'completed').length || 0}
                </div>
                <div className="text-xs text-gray-500">Completed</div>
              </div>
              <div>
                <div className="text-lg font-bold text-red-600">
                  {recent_completed?.filter(op => op.status === 'failed').length || 0}
                </div>
                <div className="text-xs text-gray-500">Failed</div>
              </div>
              <div>
                <div className="text-lg font-bold text-gray-900">{total_completed}</div>
                <div className="text-xs text-gray-500">Total</div>
              </div>
            </div>
          </div>
        )}
      </div>
    </Card>
  );
};

export default OperationStatusCard;