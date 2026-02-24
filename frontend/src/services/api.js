import axios from 'axios';
import toast from 'react-hot-toast';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

// Request queue for offline mode
const requestQueue = [];
let isProcessingQueue = false;
let isOnline = true;
const MAX_RETRY_ATTEMPTS = 3;
const RETRY_DELAY_BASE = 1000; // 1 second

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  // Increased timeout to 90s to accommodate LLM response times (especially with improvement evaluation)
  timeout: 90000,
});

// Request interceptor with retry logic and offline mode
api.interceptors.request.use(
  (config) => {
    // Add auth token if available (future enhancement)
    // const token = localStorage.getItem('token');
    // if (token) {
    //   config.headers.Authorization = `Bearer ${token}`;
    // }
    
    // Add request ID for tracking
    config.metadata = {
      requestId: crypto.randomUUID?.() || Math.random().toString(36),
      timestamp: Date.now(),
      retryAttempt: config.retryAttempt || 0
    };
    
    // Check if we're in offline mode
    if (!isOnline) {
      // Queue the request and keep the Promise pending until the queue is processed
      return new Promise((resolve, reject) => {
        requestQueue.push({
          config,
          resolve,
          reject,
          timestamp: Date.now()
        });
        toast('Request queued - offline mode', { icon: '📡' });
      });
    }
    
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor with enhanced error handling
api.interceptors.response.use(
  (response) => {
    // Reset online state on success
    isOnline = true;
    
    // Process any queued requests
    if (!isProcessingQueue && requestQueue.length > 0) {
      processRequestQueue();
    }
    
    return response;
  },
  async (error) => {
    const config = error.config;
    const status = error.response?.status;
    
    // Handle different error types
    if (error.code === 'ECONNABORTED') {
      // Request timeout - retry with backoff
      return handleRetry(config, 'Request timeout');
    }

    if (!error.response && error.request) {
      // Request was made but no response received - network error
      isOnline = false;
      toast.error('Network error - server may be unavailable', { icon: '🔌' });
      return Promise.reject(error);
    }
    
    if (status === 503) {
      // Service unavailable / degraded mode
      const degradedMode = error.response?.data?.degraded_mode;
      if (degradedMode) {
        toast.error('System operating in degraded mode. Some features may be limited.', {
          icon: '⚠️',
          duration: 5000
        });
      } else {
        toast.error('Service temporarily unavailable. Please try again later.', {
          icon: '⚠️',
          duration: 5000
        });
      }
      return Promise.reject(error);
    }
    
    if (status === 429) {
      // Rate limited
      const retryAfter = error.response?.headers?.['retry-after'] || 5;
      toast.error(`Rate limited. Please wait ${retryAfter} seconds before trying again.`, {
        icon: '⏳',
        duration: 4000
      });
      return Promise.reject(error);
    }
    
    if (status >= 500 && status < 600) {
      // Server error - retry with exponential backoff
      return handleRetry(config, 'Server error');
    }
    
    // For other errors, show user-friendly message
    let message = error.response?.data?.detail ||
                    error.response?.data?.message ||
                    error.response?.data?.error ||
                    error.message ||
                    'An error occurred';
    
    // Make message more user-friendly
    message = formatErrorMessage(message, status);
    
    // Show toast notification
    toast.error(message);
    
    return Promise.reject(error);
  }
);

// Retry logic with exponential backoff
async function handleRetry(config, errorType) {
  const retryAttempt = (config.metadata?.retryAttempt || 0) + 1;
  
  if (retryAttempt > MAX_RETRY_ATTEMPTS) {
    // Max retries reached
    toast.error(`Request failed after ${MAX_RETRY_ATTEMPTS} attempts. Please try again later.`, {
      icon: '❌',
      duration: 5000
    });
    return Promise.reject(new Error(errorType));
  }

  // Calculate delay with exponential backoff and jitter
  const delay = RETRY_DELAY_BASE * Math.pow(2, retryAttempt - 1) + Math.random() * 500;

  toast(`Retrying... (${retryAttempt}/${MAX_RETRY_ATTEMPTS})`, {
    icon: '🔄',
    duration: 2000
  });
  
  // Wait before retrying
  await new Promise(resolve => setTimeout(resolve, delay));
  
  // Retry the request
  return api({
    ...config,
    retryAttempt
  });
}

// Process queued requests when connection is restored
async function processRequestQueue() {
  if (isProcessingQueue || requestQueue.length === 0) {
    return;
  }
  
  isProcessingQueue = true;
  toast(`Processing ${requestQueue.length} queued requests...`, { icon: '📤' });
  
  const failedRequests = [];
  
  for (const queued of requestQueue) {
    try {
      const response = await api(queued.config);
      queued.resolve(response);
    } catch (error) {
      queued.reject(error);
      failedRequests.push(queued);
    }
  }
  
  // Clear processed requests
  requestQueue.length = 0;
  isProcessingQueue = false;
  
  // Notify about results
  if (failedRequests.length > 0) {
    toast.error(`${failedRequests.length} requests failed after retry`, { icon: '⚠️' });
  }
}

// Format error messages to be more user-friendly
function formatErrorMessage(message, status) {
  // Common error patterns and their user-friendly versions
  const errorMap = {
    'timeout': 'The request took too long to complete. Please try again.',
    'network error': 'Unable to connect to the server. Please check your internet connection.',
    'connection refused': 'The server is not responding. Please try again later.',
    'service unavailable': 'The service is temporarily unavailable. Please try again in a few minutes.',
    'rate limit': 'You have made too many requests. Please wait a moment before trying again.',
    'unauthorized': 'You are not authorized to perform this action.',
    'not found': 'The requested resource was not found.',
    'validation error': 'Please check your input and try again.',
    'internal server error': 'Something went wrong on our end. Please try again later.'
  };
  
  // Check if message matches any pattern
  const lowerMessage = message.toLowerCase();
  for (const [pattern, friendlyMessage] of Object.entries(errorMap)) {
    if (lowerMessage.includes(pattern)) {
      return friendlyMessage;
    }
  }
  
  // Add status-specific context
  if (status === 401) {
    return 'Please log in to continue.';
  }
  if (status === 403) {
    return 'You do not have permission to perform this action.';
  }
  if (status === 404) {
    return 'The requested resource was not found.';
  }
  if (status === 422) {
    return 'Please check your input and try again.';
  }
  
  return message;
}

// Agent Status API
export const getAgentStatus = async () => {
  try {
    const response = await api.get('/status');
    return response.data;
  } catch (error) {
    console.error('Error getting agent status:', error);
    throw error;
  }
};

export const getHealthStatus = async () => {
  try {
    const response = await api.get('/health');
    return response.data;
  } catch (error) {
    console.error('Error getting health status:', error);
    throw error;
  }
};

// Recovery status API
export const getRecoveryStatus = async () => {
  try {
    const response = await api.get('/health/recovery');
    return response.data;
  } catch (error) {
    console.error('Error getting recovery status:', error);
    throw error;
  }
};

// Trigger recovery
export const triggerRecovery = async () => {
  try {
    const response = await api.post('/system/trigger-recovery');
    toast.success('Recovery triggered successfully', { icon: '✅' });
    return response.data;
  } catch (error) {
    console.error('Error triggering recovery:', error);
    throw error;
  }
};

// Enable degraded mode
export const enableDegradedMode = async () => {
  try {
    const response = await api.post('/system/enable-degraded-mode');
    toast.success('Degraded mode enabled', { icon: '✅' });
    return response.data;
  } catch (error) {
    console.error('Error enabling degraded mode:', error);
    throw error;
  }
};

// Disable degraded mode
export const disableDegradedMode = async () => {
  try {
    const response = await api.post('/system/disable-degraded-mode');
    toast.success('Degraded mode disabled', { icon: '✅' });
    return response.data;
  } catch (error) {
    console.error('Error disabling degraded mode:', error);
    throw error;
  }
};

// Get request queue status
export const getRequestQueueStatus = () => {
  return {
    queueLength: requestQueue.length,
    isProcessing: isProcessingQueue,
    isOnline
  };
};

// Manual retry of queued requests
export const retryQueuedRequests = () => {
  if (requestQueue.length > 0) {
    processRequestQueue();
  } else {
    toast('No queued requests to retry', { icon: 'ℹ️' });
  }
};

export default api;
