import React, { useState, useEffect, useRef, useCallback } from 'react';
import Badge from '../common/Badge';
import { formatRelativeTime } from '../../utils/formatting';
import { API_BASE_URL } from '../../utils/apiConfig';

const RealTimeStatus = ({ onStatusUpdate, onConnectionChange, className = '' }) => {
  const [connectionStatus, setConnectionStatus] = useState('disconnected'); // disconnected, connecting, connected, error
  const [lastUpdate, setLastUpdate] = useState(null);
  const [reconnectAttempts, setReconnectAttempts] = useState(0);
  const [error, setError] = useState(null);
  
  const pollIntervalRef = useRef(null);
  const reconnectAttemptsRef = useRef(0);
  
  const maxReconnectAttempts = 5;
  const pollInterval = 5000; // 5 seconds

  const pollStatus = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/status`);

      if (!response.ok) {
        throw new Error(`Status request failed (${response.status})`);
      }

      const data = await response.json();
      const timestamp = new Date();

      setConnectionStatus('connected');
      setReconnectAttempts(0);
      reconnectAttemptsRef.current = 0;
      setError(null);
      setLastUpdate(timestamp);

      if (onStatusUpdate) {
        onStatusUpdate({ type: 'status_update', data, timestamp });
      }

      if (onConnectionChange) {
        onConnectionChange({ status: 'connected', timestamp });
      }
    } catch (err) {
      const nextAttempt = reconnectAttemptsRef.current + 1;
      const connectionState = nextAttempt >= maxReconnectAttempts ? 'error' : 'connecting';

      reconnectAttemptsRef.current = nextAttempt;
      setReconnectAttempts(nextAttempt);
      setConnectionStatus(connectionState);
      setError(err.message);

      if (onConnectionChange) {
        onConnectionChange({
          status: connectionState,
          timestamp: new Date(),
          error: err.message
        });
      }
    }
  }, [onStatusUpdate, onConnectionChange]);

  const connect = useCallback(() => {
    if (pollIntervalRef.current) {
      return;
    }

    setConnectionStatus('connecting');
    setError(null);
    pollStatus();
    pollIntervalRef.current = setInterval(pollStatus, pollInterval);
  }, [pollStatus]);

  const disconnect = useCallback(() => {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }

    setConnectionStatus('disconnected');
    setReconnectAttempts(0);
    reconnectAttemptsRef.current = 0;
    setError(null);
  }, []);

  const manualReconnect = useCallback(() => {
    disconnect();
    setReconnectAttempts(0);
    setTimeout(connect, 100);
  }, [disconnect, connect]);

  // Auto-connect on mount
  useEffect(() => {
    connect();
    
    return () => {
      disconnect();
    };
  }, [connect, disconnect]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
    };
  }, []);

  const getStatusText = (status) => {
    switch (status) {
      case 'connected': return 'Connected';
      case 'connecting': return 'Connecting...';
      case 'disconnected': return 'Disconnected';
      case 'error': return 'Error';
      default: return 'Unknown';
    }
  };

  const renderConnectionStatus = () => (
    <div className={`inline-flex items-center space-x-2 px-3 py-1 rounded-full text-sm ${
      connectionStatus === 'connected' ? 'bg-green-100 text-green-800' :
      connectionStatus === 'connecting' ? 'bg-blue-100 text-blue-800' :
      connectionStatus === 'error' ? 'bg-red-100 text-red-800' :
      'bg-gray-100 text-gray-800'
    }`}>
      <div className={`w-2 h-2 rounded-full ${
        connectionStatus === 'connected' ? 'bg-green-500' :
        connectionStatus === 'connecting' ? 'bg-blue-500 animate-pulse' :
        connectionStatus === 'error' ? 'bg-red-500' :
        'bg-gray-400'
      }`} />
      <span>{getStatusText(connectionStatus)}</span>
      {connectionStatus === 'connecting' && reconnectAttempts > 0 && (
        <span className="text-xs">({reconnectAttempts}/{maxReconnectAttempts})</span>
      )}
    </div>
  );

  return (
    <div className={`bg-white rounded-lg shadow-sm border border-gray-200 p-4 ${className}`}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center space-x-3">
          <h3 className="text-sm font-semibold text-gray-900">Real-time Status</h3>
          {renderConnectionStatus()}
        </div>
        <div className="flex items-center space-x-2">
          {connectionStatus !== 'connected' && (
            <button
              onClick={manualReconnect}
              className="px-3 py-1 text-xs bg-blue-500 text-white rounded hover:bg-blue-600 transition-colors"
            >
              Reconnect
            </button>
          )}
          {connectionStatus === 'connected' && (
            <button
              onClick={disconnect}
              className="px-3 py-1 text-xs bg-gray-500 text-white rounded hover:bg-gray-600 transition-colors"
            >
              Disconnect
            </button>
          )}
        </div>
      </div>

      {/* Status Details */}
      <div className="space-y-2 text-sm">
        {lastUpdate && (
          <div className="flex justify-between">
            <span className="text-gray-600">Last Update:</span>
            <span className="text-gray-900">{formatRelativeTime(lastUpdate)}</span>
          </div>
        )}
        
        {error && (
          <div className="flex justify-between">
            <span className="text-gray-600">Error:</span>
            <span className="text-red-600">{error}</span>
          </div>
        )}

        {connectionStatus === 'disconnected' && reconnectAttempts > 0 && (
          <div className="flex justify-between">
            <span className="text-gray-600">Reconnect:</span>
            <span className="text-gray-900">
              Attempting... ({reconnectAttempts}/{maxReconnectAttempts})
            </span>
          </div>
        )}

        {connectionStatus === 'connected' && (
          <div className="flex justify-between">
            <span className="text-gray-600">Status:</span>
            <Badge variant="success" size="sm">
              Live Updates Active
            </Badge>
          </div>
        )}
      </div>

      {/* Connection Info */}
      <div className="mt-3 pt-3 border-t border-gray-200 text-xs text-gray-500">
        <div className="flex justify-between">
          <span>Status Endpoint:</span>
          <span className="font-mono">/status</span>
        </div>
        <div className="flex justify-between mt-1">
          <span>Update Frequency:</span>
          <span>~5 seconds</span>
        </div>
        <div className="flex justify-between mt-1">
          <span>Mode:</span>
          <span>HTTP polling</span>
        </div>
      </div>
    </div>
  );
};

export default RealTimeStatus;
