import React, { useState, useEffect, useRef, useCallback } from 'react';
import Badge from '../common/Badge';
import { formatRelativeTime } from '../../utils/formatting';

const RealTimeStatus = ({ onStatusUpdate, onConnectionChange, className = '' }) => {
  const [connectionStatus, setConnectionStatus] = useState('disconnected'); // disconnected, connecting, connected, error
  const [lastUpdate, setLastUpdate] = useState(null);
  const [reconnectAttempts, setReconnectAttempts] = useState(0);
  const [error, setError] = useState(null);
  
  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const heartbeatIntervalRef = useRef(null);
  
  const maxReconnectAttempts = 5;
  const reconnectDelay = 3000; // 3 seconds
  const heartbeatInterval = 30000; // 30 seconds

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return;
    }

    setConnectionStatus('connecting');
    setError(null);

    try {
      // Determine WebSocket URL based on current location
      const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsHost = window.location.host || 'localhost:8000';
      const wsUrl = `${wsProtocol}//${wsHost}/ws/status`;
      
      wsRef.current = new WebSocket(wsUrl);

      wsRef.current.onopen = () => {
        setConnectionStatus('connected');
        setReconnectAttempts(0);
        setError(null);
        setLastUpdate(new Date());
        
        if (onConnectionChange) {
          onConnectionChange({ status: 'connected', timestamp: new Date() });
        }

        // Start heartbeat
        heartbeatIntervalRef.current = setInterval(() => {
          if (wsRef.current?.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify({ type: 'heartbeat' }));
          }
        }, heartbeatInterval);

        console.log('WebSocket connected for real-time status updates');
      };

      wsRef.current.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          
          if (data.type === 'status_update') {
            setLastUpdate(new Date());
            
            if (onStatusUpdate) {
              onStatusUpdate(data);
            }
          } else if (data.type === 'heartbeat_response') {
            // Heartbeat received, connection is alive
            setLastUpdate(new Date());
          }
        } catch (err) {
          console.error('Error parsing WebSocket message:', err);
        }
      };

      wsRef.current.onclose = (event) => {
        setConnectionStatus('disconnected');
        
        if (onConnectionChange) {
          onConnectionChange({ 
            status: 'disconnected', 
            timestamp: new Date(),
            code: event.code,
            reason: event.reason
          });
        }

        // Clear heartbeat
        if (heartbeatIntervalRef.current) {
          clearInterval(heartbeatIntervalRef.current);
          heartbeatIntervalRef.current = null;
        }

        // Attempt to reconnect if not explicitly closed
        if (event.code !== 1000 && reconnectAttempts < maxReconnectAttempts) {
          const nextAttempt = reconnectAttempts + 1;
          setReconnectAttempts(nextAttempt);
          
          reconnectTimeoutRef.current = setTimeout(() => {
            console.log(`WebSocket reconnection attempt ${nextAttempt}/${maxReconnectAttempts}`);
            connect();
          }, reconnectDelay * nextAttempt); // Exponential backoff
        } else if (reconnectAttempts >= maxReconnectAttempts) {
          setError('Maximum reconnection attempts reached');
          setConnectionStatus('error');
        }

        console.log('WebSocket disconnected:', event.code, event.reason);
      };

      wsRef.current.onerror = (event) => {
        console.error('WebSocket error:', event);
        setError('Connection error');
        setConnectionStatus('error');
        
        if (onConnectionChange) {
          onConnectionChange({ 
            status: 'error', 
            timestamp: new Date(),
            error: 'Connection error'
          });
        }
      };

    } catch (err) {
      console.error('Error creating WebSocket connection:', err);
      setError(`Failed to connect: ${err.message}`);
      setConnectionStatus('error');
    }
  }, [onStatusUpdate, onConnectionChange, reconnectAttempts]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    if (heartbeatIntervalRef.current) {
      clearInterval(heartbeatIntervalRef.current);
      heartbeatIntervalRef.current = null;
    }

    if (wsRef.current) {
      wsRef.current.close(1000, 'User disconnected');
      wsRef.current = null;
    }

    setConnectionStatus('disconnected');
    setReconnectAttempts(0);
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
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (heartbeatIntervalRef.current) {
        clearInterval(heartbeatIntervalRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close(1000, 'Component unmounting');
      }
    };
  }, []);

  const getStatusColor = (status) => {
    switch (status) {
      case 'connected': return 'green';
      case 'connecting': return 'blue';
      case 'disconnected': return 'gray';
      case 'error': return 'red';
      default: return 'gray';
    }
  };

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
          <span>WebSocket Endpoint:</span>
          <span className="font-mono">/ws/status</span>
        </div>
        <div className="flex justify-between mt-1">
          <span>Update Frequency:</span>
          <span>~5 seconds</span>
        </div>
        <div className="flex justify-between mt-1">
          <span>Heartbeat:</span>
          <span>30 seconds</span>
        </div>
      </div>
    </div>
  );
};

export default RealTimeStatus;