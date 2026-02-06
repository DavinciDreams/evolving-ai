import toast from 'react-hot-toast';

/**
 * Status notification system for providing users with real-time feedback
 * about system status changes, alerts, and important events.
 */

class StatusNotificationManager {
  constructor() {
    this.notificationHistory = [];
    this.maxHistorySize = 100;
    this.notificationSettings = {
      systemAlerts: true,
      operationUpdates: true,
      providerStatus: true,
      connectionStatus: true,
      errorNotifications: true,
      successNotifications: false // Only show important successes
    };
    
    // Track last notification times to prevent spam
    this.lastNotifications = {};
    this.cooldownPeriod = 5000; // 5 seconds
    
    this.loadSettings();
  }

  /**
   * Load notification settings from localStorage
   */
  loadSettings() {
    try {
      const saved = localStorage.getItem('statusNotificationSettings');
      if (saved) {
        this.notificationSettings = { ...this.notificationSettings, ...JSON.parse(saved) };
      }
    } catch (error) {
      console.warn('Failed to load notification settings:', error);
    }
  }

  /**
   * Save notification settings to localStorage
   */
  saveSettings() {
    try {
      localStorage.setItem('statusNotificationSettings', JSON.stringify(this.notificationSettings));
    } catch (error) {
      console.warn('Failed to save notification settings:', error);
    }
  }

  /**
   * Update notification settings
   */
  updateSettings(newSettings) {
    this.notificationSettings = { ...this.notificationSettings, ...newSettings };
    this.saveSettings();
  }

  /**
   * Check if a notification should be shown (cooldown check)
   */
  shouldShowNotification(type, key) {
    const notificationKey = `${type}_${key}`;
    const lastTime = this.lastNotifications[notificationKey];
    const now = Date.now();
    
    if (lastTime && (now - lastTime) < this.cooldownPeriod) {
      return false;
    }
    
    this.lastNotifications[notificationKey] = now;
    return true;
  }

  /**
   * Add notification to history
   */
  addToHistory(notification) {
    this.notificationHistory.unshift({
      ...notification,
      id: Date.now() + Math.random(),
      timestamp: new Date().toISOString()
    });
    
    // Keep history size manageable
    if (this.notificationHistory.length > this.maxHistorySize) {
      this.notificationHistory = this.notificationHistory.slice(0, this.maxHistorySize);
    }
  }

  /**
   * Show a system alert notification
   */
  showSystemAlert(alert, options = {}) {
    if (!this.notificationSettings.systemAlerts) return;
    
    if (!this.shouldShowNotification('system_alert', alert.id || alert.message)) return;

    const severity = alert.severity || 'info';
    const toastOptions = {
      duration: severity === 'critical' ? 10000 : 5000,
      icon: this.getSeverityIcon(severity),
      ...options
    };

    const message = (
      <div>
        <div className="font-semibold">{alert.message}</div>
        {alert.details && (
          <div className="text-sm opacity-75 mt-1">
            {Object.entries(alert.details).map(([key, value]) => (
              <span key={key} className="mr-3">
                {key}: {typeof value === 'number' ? value.toFixed(1) : value}
              </span>
            ))}
          </div>
        )}
      </div>
    );

    this.addToHistory({
      type: 'system_alert',
      severity,
      title: 'System Alert',
      message: alert.message,
      details: alert.details
    });

    switch (severity) {
      case 'critical':
        toast.error(message, toastOptions);
        break;
      case 'warning':
        toast(message, { ...toastOptions, icon: '⚠️' });
        break;
      case 'info':
      default:
        toast(message, toastOptions);
        break;
    }
  }

  /**
   * Show operation status update
   */
  showOperationUpdate(operation, previousStatus = null) {
    if (!this.notificationSettings.operationUpdates) return;
    
    const key = `${operation.id}_${operation.status}`;
    if (!this.shouldShowNotification('operation', key)) return;

    const statusMessages = {
      'running': 'Operation started',
      'completed': 'Operation completed successfully',
      'failed': 'Operation failed',
      'cancelled': 'Operation cancelled'
    };

    const message = statusMessages[operation.status] || `Operation ${operation.status}`;
    const fullMessage = `${message}: ${operation.description}`;

    const toastOptions = {
      duration: operation.status === 'failed' ? 8000 : 4000,
      icon: this.getOperationIcon(operation.type)
    };

    this.addToHistory({
      type: 'operation_update',
      operation,
      previousStatus,
      title: 'Operation Update',
      message: fullMessage
    });

    switch (operation.status) {
      case 'completed':
        if (this.notificationSettings.successNotifications) {
          toast.success(fullMessage, toastOptions);
        }
        break;
      case 'failed':
        toast.error(fullMessage, toastOptions);
        break;
      case 'running':
        toast(fullMessage, toastOptions);
        break;
      default:
        toast(fullMessage, toastOptions);
        break;
    }
  }

  /**
   * Show provider status change
   */
  showProviderStatusChange(providerName, status, previousStatus = null) {
    if (!this.notificationSettings.providerStatus) return;
    
    const key = `provider_${providerName}`;
    if (!this.shouldShowNotification('provider', key)) return;

    const isAvailable = status.available !== false;
    const wasAvailable = previousStatus?.available !== false;
    
    // Only notify on status change
    if (isAvailable === wasAvailable) return;

    const message = isAvailable 
      ? `${providerName} is now online`
      : `${providerName} is now offline`;

    const toastOptions = {
      duration: 6000,
      icon: isAvailable ? '🟢' : '🔴'
    };

    this.addToHistory({
      type: 'provider_status',
      provider: providerName,
      status,
      previousStatus,
      title: 'Provider Status',
      message
    });

    if (isAvailable) {
      toast.success(message, toastOptions);
    } else {
      toast.error(message, toastOptions);
    }
  }

  /**
   * Show connection status change
   */
  showConnectionStatusChange(status, details = {}) {
    if (!this.notificationSettings.connectionStatus) return;
    
    const key = 'connection_status';
    if (!this.shouldShowNotification('connection', key)) return;

    const messages = {
      'connected': 'Real-time updates connected',
      'disconnected': 'Real-time updates disconnected',
      'error': 'Connection error occurred'
    };

    const message = messages[status] || `Connection status: ${status}`;
    const toastOptions = {
      duration: status === 'error' ? 8000 : 4000,
      icon: status === 'connected' ? '🟢' : status === 'error' ? '🔴' : '🟡'
    };

    this.addToHistory({
      type: 'connection_status',
      status,
      details,
      title: 'Connection Status',
      message
    });

    switch (status) {
      case 'connected':
        if (this.notificationSettings.successNotifications) {
          toast.success(message, toastOptions);
        }
        break;
      case 'error':
        toast.error(message, toastOptions);
        break;
      default:
        toast(message, toastOptions);
        break;
    }
  }

  /**
   * Show error notification
   */
  showError(title, message, details = null) {
    if (!this.notificationSettings.errorNotifications) return;
    
    const key = `error_${title}`;
    if (!this.shouldShowNotification('error', key)) return;

    const toastMessage = (
      <div>
        <div className="font-semibold">{title}</div>
        <div className="text-sm mt-1">{message}</div>
        {details && (
          <div className="text-xs opacity-75 mt-1">
            {typeof details === 'string' ? details : JSON.stringify(details)}
          </div>
        )}
      </div>
    );

    this.addToHistory({
      type: 'error',
      title,
      message,
      details,
      severity: 'error'
    });

    toast.error(toastMessage, { duration: 8000, icon: '❌' });
  }

  /**
   * Show success notification
   */
  showSuccess(title, message) {
    if (!this.notificationSettings.successNotifications) return;
    
    const key = `success_${title}`;
    if (!this.shouldShowNotification('success', key)) return;

    const toastMessage = (
      <div>
        <div className="font-semibold">{title}</div>
        <div className="text-sm mt-1">{message}</div>
      </div>
    );

    this.addToHistory({
      type: 'success',
      title,
      message,
      severity: 'success'
    });

    toast.success(toastMessage, { duration: 4000, icon: '✅' });
  }

  /**
   * Get severity icon
   */
  getSeverityIcon(severity) {
    switch (severity) {
      case 'critical': return '🚨';
      case 'warning': return '⚠️';
      case 'info': return 'ℹ️';
      default: return '📢';
    }
  }

  /**
   * Get operation icon
   */
  getOperationIcon(operationType) {
    switch (operationType) {
      case 'improvement': return '🔧';
      case 'analysis': return '🔍';
      case 'file_improvement': return '📝';
      case 'performance_optimization': return '⚡';
      case 'code_quality': return '✨';
      case 'full_improvement_cycle': return '🔄';
      case 'pr_creation': return '🔀';
      default: return '⚙️';
    }
  }

  /**
   * Get notification history
   */
  getHistory(limit = 50) {
    return this.notificationHistory.slice(0, limit);
  }

  /**
   * Clear notification history
   */
  clearHistory() {
    this.notificationHistory = [];
  }

  /**
   * Get notification settings
   */
  getSettings() {
    return { ...this.notificationSettings };
  }

  /**
   * Process real-time status update and show appropriate notifications
   */
  processStatusUpdate(statusData, previousStatusData = {}) {
    // Process system alerts
    if (statusData.system?.alerts) {
      const currentAlerts = statusData.system.alerts;
      const previousAlerts = previousStatusData.system?.alerts || [];
      
      // Find new alerts
      currentAlerts.forEach(alert => {
        const wasPresent = previousAlerts.some(prev => prev.id === alert.id);
        if (!wasPresent) {
          this.showSystemAlert(alert);
        }
      });
    }

    // Process operation updates
    if (statusData.operations?.active_operations) {
      const currentOps = statusData.operations.active_operations;
      const previousOps = previousStatusData.operations?.active_operations || [];
      
      currentOps.forEach(operation => {
        const previousOp = previousOps.find(prev => prev.id === operation.id);
        if (previousOp && previousOp.status !== operation.status) {
          this.showOperationUpdate(operation, previousOp.status);
        } else if (!previousOp) {
          this.showOperationUpdate(operation);
        }
      });
    }

    // Process provider status changes
    if (statusData.providers?.providers) {
      const currentProviders = statusData.providers.providers;
      const previousProviders = previousStatusData.providers?.providers || {};
      
      Object.entries(currentProviders).forEach(([name, status]) => {
        const previousStatus = previousProviders[name];
        if (previousStatus && previousStatus.available !== status.available) {
          this.showProviderStatusChange(name, status, previousStatus);
        }
      });
    }
  }
}

// Create singleton instance
const statusNotificationManager = new StatusNotificationManager();

// Export the manager and convenience functions
export default statusNotificationManager;

export const {
  showSystemAlert,
  showOperationUpdate,
  showProviderStatusChange,
  showConnectionStatusChange,
  showError,
  showSuccess,
  getHistory,
  clearHistory,
  getSettings,
  updateSettings,
  processStatusUpdate
} = statusNotificationManager;