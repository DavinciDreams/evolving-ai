import React, { useState, useEffect } from 'react';
import Spinner from '../common/Spinner';
import Badge from '../common/Badge';
import Button from '../common/Button';
import { formatDuration, formatRelativeTime } from '../../utils/formatting';
import { 
  CheckCircleIcon, 
  XCircleIcon, 
  ClockIcon, 
  DocumentTextIcon,
  SparklesIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  ArrowPathIcon,
  ChevronDownIcon,
  ChevronUpIcon
} from '@heroicons/react/24/outline';

/**
 * Enhanced component to display detailed improvement progress in chat
 */
export const ImprovementStatus = ({ 
  improvementType, 
  progressUpdates = [], 
  isComplete = false,
  hasError = false,
  errorMessage = '',
  errorDetails = null,
  prCreated = false,
  prNumber = null,
  prUrl = null,
  estimatedDuration = null,
  startTime = null,
  onApprove = null,
  onReject = null,
  onRetry = null,
  onCancel = null
}) => {
  const [expanded, setExpanded] = useState(false);
  const [currentTime, setCurrentTime] = useState(Date.now());
  const [retryCount, setRetryCount] = useState(0);

  // Update current time for elapsed time calculations
  useEffect(() => {
    if (!isComplete && !hasError) {
      const interval = setInterval(() => setCurrentTime(Date.now()), 1000);
      return () => clearInterval(interval);
    }
  }, [isComplete, hasError]);

  const getStageIcon = (stage) => {
    switch (stage) {
      case 'analysis':
      case 'analyzing':
        return <DocumentTextIcon className="h-5 w-5 text-blue-500" />;
      case 'evaluation_insights':
        return <SparklesIcon className="h-5 w-5 text-purple-500" />;
      case 'knowledge_suggestions':
        return <SparklesIcon className="h-5 w-5 text-green-500" />;
      case 'generating':
      case 'pr_creation':
        return <ClockIcon className="h-5 w-5 text-yellow-500" />;
      case 'validation':
        return <CheckCircleIcon className="h-5 w-5 text-indigo-500" />;
      case 'complete':
        return <CheckCircleIcon className="h-5 w-5 text-green-500" />;
      case 'error':
        return <XCircleIcon className="h-5 w-5 text-red-500" />;
      default:
        return <ClockIcon className="h-5 w-5 text-gray-500" />;
    }
  };

  const getStageLabel = (stage) => {
    const labels = {
      'analysis': 'Analyzing codebase structure',
      'analyzing': 'Analyzing code patterns',
      'evaluation_insights': 'Gathering evaluation insights',
      'knowledge_suggestions': 'Processing knowledge suggestions',
      'generating': 'Generating improvements',
      'validation': 'Validating improvements',
      'pr_creation': 'Creating pull request',
      'running_cycle': 'Running improvement cycle',
      'file_improvement': 'Improving file',
      'performance_optimization': 'Optimizing performance',
      'code_quality': 'Analyzing code quality',
      'complete': 'Complete',
      'error': 'Error occurred'
    };
    return labels[stage] || stage;
  };

  const getImprovementTypeLabel = (type) => {
    const labels = {
      'code_analysis': 'Code Analysis',
      'pr_creation': 'Pull Request Creation',
      'file_improvement': 'File Improvement',
      'performance_optimization': 'Performance Optimization',
      'code_quality': 'Code Quality Improvement',
      'full_improvement_cycle': 'Full Improvement Cycle'
    };
    return labels[type] || 'Improvement';
  };

  const getErrorRecoverySuggestions = (errorType, errorMessage) => {
    const suggestions = {
      'timeout': [
        'The operation is taking longer than expected. Try again with a smaller scope.',
        'Consider breaking down the improvement into smaller chunks.',
        'Check if the system is under heavy load and try again later.'
      ],
      'rate_limit': [
        'Rate limit exceeded. Please wait a few minutes before trying again.',
        'Consider upgrading your API plan for higher rate limits.',
        'Try the operation during off-peak hours.'
      ],
      'permission': [
        'Check if you have the necessary permissions for this operation.',
        'Ensure GitHub token has the required scopes.',
        'Verify repository access permissions.'
      ],
      'validation': [
        'The generated improvements failed validation.',
        'Review the error details and adjust the improvement criteria.',
        'Try running with more conservative settings.'
      ],
      'network': [
        'Network connection issue. Check your internet connection.',
        'The server may be temporarily unavailable. Try again in a moment.',
        'Consider using a different network or VPN.'
      ]
    };

    // Determine error type from message
    let detectedType = 'general';
    if (errorMessage) {
      const lowerMessage = errorMessage.toLowerCase();
      if (lowerMessage.includes('timeout')) detectedType = 'timeout';
      else if (lowerMessage.includes('rate limit')) detectedType = 'rate_limit';
      else if (lowerMessage.includes('permission') || lowerMessage.includes('unauthorized')) detectedType = 'permission';
      else if (lowerMessage.includes('validation')) detectedType = 'validation';
      else if (lowerMessage.includes('network') || lowerMessage.includes('connection')) detectedType = 'network';
    }

    return suggestions[detectedType] || [
      'An unexpected error occurred. Please try again.',
      'Check the error details for more information.',
      'Contact support if the issue persists.'
    ];
  };

  const latestUpdate = progressUpdates.length > 0 
    ? progressUpdates[progressUpdates.length - 1] 
    : null;

  // Calculate progress metrics
  const startTimeMs = startTime ? new Date(startTime).getTime() : null;
  const elapsedMs = startTimeMs ? currentTime - startTimeMs : 0;
  const elapsedSeconds = Math.floor(elapsedMs / 1000);
  const progressPercentage = latestUpdate?.data?.progress || 0;

  // Estimate remaining time
  let estimatedRemaining = null;
  if (estimatedDuration && progressPercentage > 0) {
    estimatedRemaining = Math.max(0, estimatedDuration - elapsedSeconds);
  }

  const handleRetry = () => {
    setRetryCount(prev => prev + 1);
    if (onRetry) {
      onRetry();
    }
  };

  return (
    <div className="bg-gradient-to-r from-indigo-50 to-purple-50 border border-indigo-200 rounded-lg p-4 my-2">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <SparklesIcon className="h-5 w-5 text-indigo-600" />
          <h3 className="text-lg font-semibold text-gray-900">
            {getImprovementTypeLabel(improvementType)}
          </h3>
          {retryCount > 0 && (
            <Badge variant="warning" className="text-xs">
              Retry #{retryCount}
            </Badge>
          )}
        </div>
        <div className="flex items-center gap-2">
          {isComplete && !hasError && (
            <Badge variant="success" className="text-xs">
              Complete
            </Badge>
          )}
          {hasError && (
            <Badge variant="danger" className="text-xs">
              Failed
            </Badge>
          )}
          {!isComplete && !hasError && (
            <Badge variant="primary" className="text-xs">
              In Progress
            </Badge>
          )}
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-gray-500 hover:text-gray-700 transition-colors"
          >
            {expanded ? <ChevronUpIcon className="h-4 w-4" /> : <ChevronDownIcon className="h-4 w-4" />}
          </button>
        </div>
      </div>

      {/* Progress Bar */}
      {!isComplete && !hasError && (
        <div className="mb-4">
          <div className="flex justify-between text-sm mb-1">
            <span className="text-gray-600">Progress</span>
            <span className="font-medium">{progressPercentage}%</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div
              className="bg-gradient-to-r from-blue-500 to-indigo-500 h-2 rounded-full transition-all duration-300"
              style={{ width: `${progressPercentage}%` }}
            />
          </div>
          <div className="flex justify-between text-xs text-gray-500 mt-1">
            <span>Elapsed: {formatDuration(elapsedSeconds)}</span>
            {estimatedRemaining !== null && (
              <span>Est. remaining: {formatDuration(estimatedRemaining)}</span>
            )}
          </div>
        </div>
      )}

      {/* Progress Steps */}
      {progressUpdates.length > 0 && (
        <div className="space-y-2 mb-4">
          {progressUpdates.slice(expanded ? undefined : -3).map((update, index) => {
            const { event_type, data, timestamp } = update;
            const isLast = index === progressUpdates.length - 1;
            
            return (
              <div 
                key={index} 
                className={`flex items-start gap-3 p-2 rounded-md ${
                  isLast ? 'bg-white shadow-sm' : 'bg-gray-100/50'
                }`}
              >
                <div className="flex-shrink-0 mt-0.5">
                  {getStageIcon(data?.stage || event_type)}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-900">
                    {data?.message || getStageLabel(data?.stage || event_type)}
                  </p>
                  {data?.stage && (
                    <p className="text-xs text-gray-500 mt-1">
                      Stage: {getStageLabel(data.stage)}
                    </p>
                  )}
                  {data?.details && expanded && (
                    <div className="mt-2 p-2 bg-gray-50 rounded text-xs text-gray-600">
                      {Object.entries(data.details).map(([key, value]) => (
                        <div key={key} className="flex justify-between">
                          <span className="font-medium">{key}:</span>
                          <span>{typeof value === 'number' ? value.toFixed(2) : value}</span>
                        </div>
                      ))}
                    </div>
                  )}
                  {timestamp && (
                    <p className="text-xs text-gray-400 mt-1">
                      {formatRelativeTime(new Date(timestamp))}
                    </p>
                  )}
                </div>
                {isLast && !isComplete && !hasError && (
                  <div className="flex-shrink-0">
                    <Spinner size="sm" />
                  </div>
                )}
              </div>
            );
          })}
          {!expanded && progressUpdates.length > 3 && (
            <div className="text-center text-xs text-gray-500">
              +{progressUpdates.length - 3} more steps
            </div>
          )}
        </div>
      )}

      {/* Error Message with Recovery Suggestions */}
      {hasError && (
        <div className="bg-red-50 border border-red-200 rounded-md p-3 mb-4">
          <div className="flex items-start gap-2">
            <ExclamationTriangleIcon className="h-5 w-5 text-red-600 flex-shrink-0" />
            <div className="flex-1">
              <p className="text-sm font-medium text-red-900">
                {errorMessage || 'An error occurred during the improvement process'}
              </p>
              
              {/* Error Details */}
              {errorDetails && expanded && (
                <div className="mt-2 p-2 bg-red-100 rounded text-xs text-red-800">
                  <pre className="whitespace-pre-wrap">{errorDetails}</pre>
                </div>
              )}

              {/* Recovery Suggestions */}
              <div className="mt-3">
                <p className="text-sm font-medium text-red-800 mb-2">Recovery Suggestions:</p>
                <ul className="text-xs text-red-700 space-y-1">
                  {getErrorRecoverySuggestions(null, errorMessage).map((suggestion, index) => (
                    <li key={index} className="flex items-start gap-1">
                      <span>•</span>
                      <span>{suggestion}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Pull Request Info */}
      {prCreated && prNumber && (
        <div className="bg-green-50 border border-green-200 rounded-md p-3 mb-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <CheckCircleIcon className="h-5 w-5 text-green-600" />
              <div>
                <p className="text-sm font-medium text-green-900">
                  Pull Request Created Successfully
                </p>
                <p className="text-xs text-green-700">
                  PR #{prNumber} • {formatDuration(elapsedSeconds)} total time
                </p>
              </div>
            </div>
            {prUrl && (
              <a
                href={prUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm text-green-700 hover:text-green-900 underline flex items-center gap-1"
              >
                View on GitHub
                <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                </svg>
              </a>
            )}
          </div>
        </div>
      )}

      {/* Action Buttons */}
      <div className="flex gap-2 justify-end">
        {hasError && onRetry && (
          <Button
            variant="outline"
            size="sm"
            onClick={handleRetry}
            className="border-orange-300 text-orange-700 hover:bg-orange-50 flex items-center gap-1"
          >
            <ArrowPathIcon className="h-3 w-3" />
            Retry
          </Button>
        )}
        {!isComplete && !hasError && onCancel && (
          <Button
            variant="outline"
            size="sm"
            onClick={onCancel}
            className="border-gray-300 text-gray-700 hover:bg-gray-50"
          >
            Cancel
          </Button>
        )}
        {isComplete && !hasError && onApprove && onReject && (
          <>
            <Button
              variant="outline"
              size="sm"
              onClick={onReject}
              className="border-red-300 text-red-700 hover:bg-red-50"
            >
              Reject Changes
            </Button>
            <Button
              variant="primary"
              size="sm"
              onClick={onApprove}
              className="bg-green-600 hover:bg-green-700"
            >
              Approve Changes
            </Button>
          </>
        )}
      </div>

      {/* Additional Information (when expanded) */}
      {expanded && (
        <div className="mt-4 pt-4 border-t border-indigo-200">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs">
            <div>
              <span className="text-gray-500">Type:</span>
              <div className="font-medium">{getImprovementTypeLabel(improvementType)}</div>
            </div>
            <div>
              <span className="text-gray-500">Started:</span>
              <div className="font-medium">
                {startTime ? formatRelativeTime(new Date(startTime)) : 'Unknown'}
              </div>
            </div>
            <div>
              <span className="text-gray-500">Duration:</span>
              <div className="font-medium">{formatDuration(elapsedSeconds)}</div>
            </div>
            <div>
              <span className="text-gray-500">Steps:</span>
              <div className="font-medium">{progressUpdates.length}</div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

/**
 * Enhanced component to display improvement summary with detailed before/after comparison
 */
export const ImprovementSummary = ({ 
  improvementId,
  improvementType,
  filesAffected = [],
  changesCount = 0,
  beforeContent = '',
  afterContent = '',
  metrics = {},
  onApprove = null,
  onReject = null
}) => {
  const [showDiff, setShowDiff] = React.useState(false);
  const [showMetrics, setShowMetrics] = React.useState(false);

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4 my-2">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <DocumentTextIcon className="h-5 w-5 text-indigo-600" />
          <h3 className="text-lg font-semibold text-gray-900">
            Improvement Summary
          </h3>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="info" className="text-xs">
            {changesCount} {changesCount === 1 ? 'change' : 'changes'}
          </Badge>
          {Object.keys(metrics).length > 0 && (
            <button
              onClick={() => setShowMetrics(!showMetrics)}
              className="text-xs text-indigo-600 hover:text-indigo-800"
            >
              {showMetrics ? 'Hide' : 'Show'} Metrics
            </button>
          )}
        </div>
      </div>

      {/* Files Affected */}
      {filesAffected.length > 0 && (
        <div className="mb-3">
          <p className="text-sm font-medium text-gray-700 mb-1">
            Files affected:
          </p>
          <div className="flex flex-wrap gap-1">
            {filesAffected.map((file, index) => (
              <Badge key={index} variant="secondary" className="text-xs">
                {file}
              </Badge>
            ))}
          </div>
        </div>
      )}

      {/* Metrics */}
      {showMetrics && Object.keys(metrics).length > 0 && (
        <div className="mb-3 p-3 bg-gray-50 rounded-md">
          <p className="text-sm font-medium text-gray-700 mb-2">Improvement Metrics:</p>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
            {Object.entries(metrics).map(([key, value]) => (
              <div key={key}>
                <span className="text-gray-500 capitalize">{key.replace(/_/g, ' ')}:</span>
                <div className="font-medium">
                  {typeof value === 'number' ? value.toFixed(2) : value}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Before/After Toggle */}
      <div className="mb-3">
        <button
          onClick={() => setShowDiff(!showDiff)}
          className="text-sm text-indigo-600 hover:text-indigo-800 font-medium"
        >
          {showDiff ? 'Hide' : 'Show'} Before/After Comparison
        </button>
      </div>

      {/* Before/After Content */}
      {showDiff && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Before */}
          <div className="bg-red-50 border border-red-200 rounded-md p-3">
            <p className="text-xs font-medium text-red-900 mb-2">
              Before
            </p>
            <pre className="text-xs text-red-800 overflow-x-auto whitespace-pre-wrap">
              {beforeContent || 'No content available'}
            </pre>
          </div>

          {/* After */}
          <div className="bg-green-50 border border-green-200 rounded-md p-3">
            <p className="text-xs font-medium text-green-900 mb-2">
              After
            </p>
            <pre className="text-xs text-green-800 overflow-x-auto whitespace-pre-wrap">
              {afterContent || 'No content available'}
            </pre>
          </div>
        </div>
      )}

      {/* Action Buttons */}
      {onApprove && onReject && (
        <div className="flex gap-2 justify-end mt-4">
          <Button
            variant="outline"
            size="sm"
            onClick={onReject}
            className="border-red-300 text-red-700 hover:bg-red-50"
          >
            Reject Changes
          </Button>
          <Button
            variant="primary"
            size="sm"
            onClick={onApprove}
            className="bg-green-600 hover:bg-green-700"
          >
            Approve Changes
          </Button>
        </div>
      )}
    </div>
  );
};

export default ImprovementStatus;
