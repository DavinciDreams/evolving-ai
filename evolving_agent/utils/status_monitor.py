"""
Status Monitoring Module

This module provides comprehensive system status monitoring including:
- System health metrics (CPU, memory, disk usage)
- LLM provider availability and response times
- Active operations and their progress
- Historical status data for trend analysis
"""

import psutil
import time
import threading
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from collections import defaultdict, deque
import logging

logger = logging.getLogger(__name__)

class StatusMonitor:
    """Comprehensive status monitoring system for the evolving AI agent."""
    
    def __init__(self, max_history_hours: int = 24):
        """Initialize the status monitor.
        
        Args:
            max_history_hours: Maximum hours of historical data to keep
        """
        self.max_history_hours = max_history_hours
        self.max_history_points = max_history_hours * 60  # One point per minute
        
        # System metrics history
        self.system_history = deque(maxlen=self.max_history_points)
        
        # Provider status tracking
        self.provider_status = {}
        self.provider_history = defaultdict(lambda: deque(maxlen=1000))
        
        # Active operations tracking
        self.active_operations = {}
        self.operation_history = deque(maxlen=1000)
        
        # System alerts
        self.active_alerts = []
        self.alert_history = deque(maxlen=500)
        
        # Monitoring thread
        self._monitoring_active = False
        self._monitor_thread = None
        
        # Lock for thread safety
        self._lock = threading.Lock()
        
        # Initialize system metrics
        self._last_system_update = 0
        self._update_interval = 30  # seconds
        
    def start_monitoring(self):
        """Start the background monitoring thread."""
        if self._monitoring_active:
            return
            
        self._monitoring_active = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        logger.info("Status monitoring started")
        
    def stop_monitoring(self):
        """Stop the background monitoring thread."""
        self._monitoring_active = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
        logger.info("Status monitoring stopped")
        
    def _monitor_loop(self):
        """Main monitoring loop running in background thread."""
        while self._monitoring_active:
            try:
                current_time = time.time()
                
                # Update system metrics every 30 seconds
                if current_time - self._last_system_update >= self._update_interval:
                    self._update_system_metrics()
                    self._last_system_update = current_time
                
                # Check for alerts
                self._check_alerts()
                
                # Clean up old data
                self._cleanup_old_data()
                
                time.sleep(5)  # Check every 5 seconds
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(10)  # Wait longer on error
                
    def _update_system_metrics(self):
        """Update system health metrics."""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Memory usage
            memory = psutil.virtual_memory()
            
            # Disk usage
            disk = psutil.disk_usage('/')
            
            # Network I/O
            network = psutil.net_io_counters()
            
            # Process count
            process_count = len(psutil.pids())
            
            metrics = {
                'timestamp': datetime.now().isoformat(),
                'cpu': {
                    'percent': cpu_percent,
                    'count': psutil.cpu_count(),
                    'freq': psutil.cpu_freq()._asdict() if psutil.cpu_freq() else None
                },
                'memory': {
                    'total': memory.total,
                    'available': memory.available,
                    'percent': memory.percent,
                    'used': memory.used,
                    'free': memory.free
                },
                'disk': {
                    'total': disk.total,
                    'used': disk.used,
                    'free': disk.free,
                    'percent': (disk.used / disk.total) * 100
                },
                'network': {
                    'bytes_sent': network.bytes_sent,
                    'bytes_recv': network.bytes_recv,
                    'packets_sent': network.packets_sent,
                    'packets_recv': network.packets_recv
                },
                'processes': process_count
            }
            
            with self._lock:
                self.system_history.append(metrics)
                
        except Exception as e:
            logger.error(f"Error updating system metrics: {e}")
            
    def update_provider_status(self, provider_name: str, status: Dict[str, Any]):
        """Update LLM provider status.
        
        Args:
            provider_name: Name of the LLM provider
            status: Status information including availability, response time, etc.
        """
        try:
            timestamp = datetime.now().isoformat()
            
            provider_data = {
                'timestamp': timestamp,
                'provider': provider_name,
                **status
            }
            
            with self._lock:
                self.provider_status[provider_name] = provider_data
                self.provider_history[provider_name].append(provider_data)
                
        except Exception as e:
            logger.error(f"Error updating provider status: {e}")
            
    def start_operation(self, operation_id: str, operation_type: str, 
                       description: str, estimated_duration: Optional[int] = None):
        """Start tracking a new operation.
        
        Args:
            operation_id: Unique identifier for the operation
            operation_type: Type of operation (e.g., 'improvement', 'analysis')
            description: Human-readable description
            estimated_duration: Estimated duration in seconds
        """
        try:
            operation = {
                'id': operation_id,
                'type': operation_type,
                'description': description,
                'status': 'running',
                'progress': 0,
                'start_time': datetime.now().isoformat(),
                'estimated_duration': estimated_duration,
                'current_step': None,
                'total_steps': None,
                'error': None
            }
            
            with self._lock:
                self.active_operations[operation_id] = operation
                
            logger.info(f"Started tracking operation: {operation_id}")
            
        except Exception as e:
            logger.error(f"Error starting operation tracking: {e}")
            
    def update_operation_progress(self, operation_id: str, progress: int,
                                 current_step: Optional[str] = None,
                                 total_steps: Optional[int] = None):
        """Update operation progress.
        
        Args:
            operation_id: Operation identifier
            progress: Progress percentage (0-100)
            current_step: Current step description
            total_steps: Total number of steps
        """
        try:
            with self._lock:
                if operation_id in self.active_operations:
                    self.active_operations[operation_id]['progress'] = progress
                    if current_step:
                        self.active_operations[operation_id]['current_step'] = current_step
                    if total_steps:
                        self.active_operations[operation_id]['total_steps'] = total_steps
                        
        except Exception as e:
            logger.error(f"Error updating operation progress: {e}")
            
    def complete_operation(self, operation_id: str, success: bool = True, 
                          error: Optional[str] = None):
        """Mark an operation as completed.
        
        Args:
            operation_id: Operation identifier
            success: Whether the operation completed successfully
            error: Error message if operation failed
        """
        try:
            with self._lock:
                if operation_id in self.active_operations:
                    operation = self.active_operations[operation_id]
                    operation['status'] = 'completed' if success else 'failed'
                    operation['progress'] = 100 if success else operation['progress']
                    operation['end_time'] = datetime.now().isoformat()
                    operation['error'] = error
                    
                    # Move to history
                    self.operation_history.append(operation.copy())
                    del self.active_operations[operation_id]
                    
            logger.info(f"Completed operation: {operation_id}, success: {success}")
            
        except Exception as e:
            logger.error(f"Error completing operation: {e}")
            
    def add_alert(self, alert_type: str, severity: str, message: str, 
                 details: Optional[Dict[str, Any]] = None):
        """Add a system alert.
        
        Args:
            alert_type: Type of alert (e.g., 'system', 'provider', 'operation')
            severity: Severity level (info, warning, error, critical)
            message: Alert message
            details: Additional alert details
        """
        try:
            alert = {
                'id': f"{alert_type}_{int(time.time())}",
                'type': alert_type,
                'severity': severity,
                'message': message,
                'details': details or {},
                'timestamp': datetime.now().isoformat(),
                'acknowledged': False
            }
            
            with self._lock:
                self.active_alerts.append(alert)
                self.alert_history.append(alert.copy())
                
            logger.warning(f"Alert added: {alert_type} - {message}")
            
        except Exception as e:
            logger.error(f"Error adding alert: {e}")
            
    def acknowledge_alert(self, alert_id: str):
        """Acknowledge an alert.
        
        Args:
            alert_id: Alert identifier
        """
        try:
            with self._lock:
                for alert in self.active_alerts:
                    if alert['id'] == alert_id:
                        alert['acknowledged'] = True
                        break
                        
        except Exception as e:
            logger.error(f"Error acknowledging alert: {e}")
            
    def _check_alerts(self):
        """Check for system conditions that should trigger alerts."""
        try:
            if not self.system_history:
                return
                
            latest_metrics = self.system_history[-1]
            
            # Check CPU usage
            if latest_metrics['cpu']['percent'] > 90:
                self.add_alert(
                    'system', 'warning',
                    f"High CPU usage: {latest_metrics['cpu']['percent']:.1f}%",
                    {'metric': 'cpu', 'value': latest_metrics['cpu']['percent']}
                )
                
            # Check memory usage
            if latest_metrics['memory']['percent'] > 90:
                self.add_alert(
                    'system', 'warning',
                    f"High memory usage: {latest_metrics['memory']['percent']:.1f}%",
                    {'metric': 'memory', 'value': latest_metrics['memory']['percent']}
                )
                
            # Check disk usage
            if latest_metrics['disk']['percent'] > 90:
                self.add_alert(
                    'system', 'critical',
                    f"Low disk space: {latest_metrics['disk']['percent']:.1f}% used",
                    {'metric': 'disk', 'value': latest_metrics['disk']['percent']}
                )
                
        except Exception as e:
            logger.error(f"Error checking alerts: {e}")
            
    def _cleanup_old_data(self):
        """Clean up old data based on retention policies."""
        try:
            cutoff_time = datetime.now() - timedelta(hours=self.max_history_hours)
            cutoff_iso = cutoff_time.isoformat()
            
            with self._lock:
                # Clean system history (handled by deque maxlen)
                
                # Clean provider history
                for provider in self.provider_history:
                    while (self.provider_history[provider] and 
                           self.provider_history[provider][0]['timestamp'] < cutoff_iso):
                        self.provider_history[provider].popleft()
                        
                # Clean operation history
                while (self.operation_history and 
                       self.operation_history[0]['start_time'] < cutoff_iso):
                    self.operation_history.popleft()
                    
                # Clean alert history
                while (self.alert_history and 
                       self.alert_history[0]['timestamp'] < cutoff_iso):
                    self.alert_history.popleft()
                    
        except Exception as e:
            logger.error(f"Error cleaning up old data: {e}")
            
    def get_system_status(self) -> Dict[str, Any]:
        """Get current system status.
        
        Returns:
            Dictionary containing system status information
        """
        try:
            with self._lock:
                latest_metrics = self.system_history[-1] if self.system_history else None
                
                return {
                    'timestamp': datetime.now().isoformat(),
                    'monitoring_active': self._monitoring_active,
                    'metrics': latest_metrics,
                    'alerts': [a for a in self.active_alerts if not a['acknowledged']],
                    'alert_count': len([a for a in self.active_alerts if not a['acknowledged']]),
                    'history_points': len(self.system_history)
                }
                
        except Exception as e:
            logger.error(f"Error getting system status: {e}")
            return {'error': str(e)}
            
    def get_operations_status(self) -> Dict[str, Any]:
        """Get current operations status.
        
        Returns:
            Dictionary containing operations status information
        """
        try:
            with self._lock:
                return {
                    'timestamp': datetime.now().isoformat(),
                    'active_operations': list(self.active_operations.values()),
                    'active_count': len(self.active_operations),
                    'recent_completed': list(self.operation_history)[-10:],  # Last 10 completed
                    'total_completed': len(self.operation_history)
                }
                
        except Exception as e:
            logger.error(f"Error getting operations status: {e}")
            return {'error': str(e)}
            
    def get_providers_status(self) -> Dict[str, Any]:
        """Get LLM providers status.
        
        Returns:
            Dictionary containing provider status information
        """
        try:
            with self._lock:
                return {
                    'timestamp': datetime.now().isoformat(),
                    'providers': self.provider_status,
                    'provider_count': len(self.provider_status),
                    'history_points': {p: len(h) for p, h in self.provider_history.items()}
                }
                
        except Exception as e:
            logger.error(f"Error getting providers status: {e}")
            return {'error': str(e)}
            
    def get_history_status(self, hours: int = 24) -> Dict[str, Any]:
        """Get historical status data.
        
        Args:
            hours: Number of hours of history to return
            
        Returns:
            Dictionary containing historical status data
        """
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            cutoff_iso = cutoff_time.isoformat()
            
            with self._lock:
                # Filter system history
                system_history = [
                    m for m in self.system_history 
                    if m['timestamp'] >= cutoff_iso
                ]
                
                # Filter operation history
                operation_history = [
                    o for o in self.operation_history 
                    if o['start_time'] >= cutoff_iso
                ]
                
                # Filter alert history
                alert_history = [
                    a for a in self.alert_history 
                    if a['timestamp'] >= cutoff_iso
                ]
                
                # Aggregate provider history
                provider_history = {}
                for provider, history in self.provider_history.items():
                    provider_history[provider] = [
                        h for h in history 
                        if h['timestamp'] >= cutoff_iso
                    ]
                
                return {
                    'timestamp': datetime.now().isoformat(),
                    'hours': hours,
                    'system_metrics': system_history,
                    'operations': operation_history,
                    'alerts': alert_history,
                    'providers': provider_history,
                    'summary': {
                        'system_points': len(system_history),
                        'operations_completed': len(operation_history),
                        'alerts_generated': len(alert_history),
                        'providers_active': len(provider_history)
                    }
                }
                
        except Exception as e:
            logger.error(f"Error getting history status: {e}")
            return {'error': str(e)}

# Global status monitor instance
_status_monitor = None

def get_status_monitor() -> StatusMonitor:
    """Get the global status monitor instance."""
    global _status_monitor
    if _status_monitor is None:
        _status_monitor = StatusMonitor()
        _status_monitor.start_monitoring()
    return _status_monitor

def initialize_status_monitor(max_history_hours: int = 24) -> StatusMonitor:
    """Initialize the global status monitor.
    
    Args:
        max_history_hours: Maximum hours of historical data to keep
        
    Returns:
        The initialized status monitor instance
    """
    global _status_monitor
    _status_monitor = StatusMonitor(max_history_hours)
    _status_monitor.start_monitoring()
    return _status_monitor