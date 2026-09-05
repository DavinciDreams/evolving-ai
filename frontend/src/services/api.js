import axios from 'axios';
import toast from 'react-hot-toast';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api';

// Connectivity is telemetry only. Every explicit request can test recovery;
// no request bodies or credentials are retained in an offline replay queue.
let isOnline = true;
const MAX_RETRY_ATTEMPTS = 3;
const RETRY_DELAY_BASE = 1000; // 1 second
let projectApiKey = '';
let credentialEpoch = 0;

export const setProjectApiKey = (credential) => {
  projectApiKey = credential;
  credentialEpoch += 1;
};

export const clearProjectApiKey = () => {
  projectApiKey = '';
  credentialEpoch += 1;
};

const scrubAuthFromError = (error) => {
  // Axios errors retain request.data, credentials, XHR, response.config, and
  // occasionally a cause containing the same values. Return a fresh small error
  // rather than trying to recursively redact an arbitrary transport object.
  const status = Number.isInteger(error.response?.status) ? error.response.status : undefined;
  const safe = new Error(formatErrorMessage(error.message, status));
  safe.name = 'ApiError';
  const safeCodes = ['ERR_NETWORK', 'ECONNABORTED', 'ETIMEDOUT', 'ERR_CANCELED', 'ERR_BAD_REQUEST', 'ERR_BAD_RESPONSE'];
  if (safeCodes.includes(error.code)) safe.code = error.code;
  if (error.code === 'ERR_CANCELED') safe.__CANCEL__ = true;
  if (status !== undefined) safe.response = { status, data: { detail: safe.message } };
  safe.isAxiosError = axios.isAxiosError(error);
  return safe;
};

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  // Increased timeout to 90s to accommodate LLM response times (especially with improvement evaluation)
  timeout: 90000,
});

// Retry bookkeeping only: failures never prevent a later explicit request.
api.interceptors.request.use(
  (config) => {
    const hasExplicitCredential = config.headers?.has?.('X-API-Key')
      || Boolean(config.headers?.['X-API-Key']);
    if (projectApiKey && !hasExplicitCredential) {
      config.headers['X-API-Key'] = projectApiKey;
    }
    
    // Add request ID for tracking
    config.metadata = {
      requestId: crypto.randomUUID?.() || Math.random().toString(36),
      timestamp: Date.now(),
      retryAttempt: config.retryAttempt || 0
    };
    config.credentialEpoch ??= credentialEpoch;
    
    return config;
  },
  (error) => {
    return Promise.reject(scrubAuthFromError(error));
  }
);

// Response interceptor with enhanced error handling
api.interceptors.response.use(
  (response) => {
    // Reset online state on success
    isOnline = true;
    
    return response;
  },
  async (error) => {
    const config = error.config;
    const status = error.response?.status;

    if (axios.isCancel(error) || error.code === 'ERR_CANCELED') {
      return Promise.reject(scrubAuthFromError(error));
    }

    if (status === 401 && typeof window !== 'undefined') {
      window.dispatchEvent(new Event('evolving-ai:auth-required'));
    }
    
    // Handle different error types
    if (error.code === 'ECONNABORTED') {
      if (!config || config.noRetry || !['get', 'head'].includes((config.method || 'get').toLowerCase())) {
        return Promise.reject(scrubAuthFromError(error));
      }
      // Request timeout - retry with backoff
      return handleRetry(config, 'Request timeout');
    }

    if (!error.response && error.request) {
      // Request was made but no response received - network error
      isOnline = false;
      toast.error('Network error - server may be unavailable', { icon: '🔌' });
      return Promise.reject(scrubAuthFromError(error));
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
      return Promise.reject(scrubAuthFromError(error));
    }
    
    if (status === 429) {
      // Rate limited
      const retryValue = Number(error.response?.headers?.['retry-after']);
      const retryAfter = Number.isFinite(retryValue) && retryValue > 0 && retryValue <= 3600 ? retryValue : 5;
      toast.error(`Rate limited. Please wait ${retryAfter} seconds before trying again.`, {
        icon: '⏳',
        duration: 4000
      });
      return Promise.reject(scrubAuthFromError(error));
    }
    
    if (status >= 500 && status < 600) {
      if (!config || config.noRetry || !['get', 'head'].includes((config.method || 'get').toLowerCase())) {
        return Promise.reject(scrubAuthFromError(error));
      }
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
    
    return Promise.reject(scrubAuthFromError(error));
  }
);

export const validateProjectApiKey = async (credential) => {
  const response = await api.get('/status', {
    headers: { 'X-API-Key': credential },
  });
  return response.data;
};

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

  if (config.credentialEpoch !== credentialEpoch || config.signal?.aborted) {
    // A read retry must not resurrect credentials after logout or key rotation.
    return Promise.reject(new Error('Request cancelled before retry; retry explicitly if needed.'));
  }
  
  // Retry the request
  return api({
    ...config,
    retryAttempt
  });
}

// Format error messages to be more user-friendly
function formatErrorMessage(message, status) {
  if (status === 410) {
    return 'This legacy action is retired. Use measured steward controls or a separately authorized publishing workflow.';
  }
  if (typeof message !== 'string') message = status === 422 ? 'Please check your input and try again.' : 'Request failed';
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
  if (status === 409) {
    return 'Another operation is active or this event was already handled. Check status before retrying.';
  }
  if (status === 413) {
    return 'The request exceeds the size limit.';
  }
  if (status === 415) {
    return 'This file or request format is not supported.';
  }
  return 'Request failed. Check service status and retry explicitly.';
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
    queueLength: 0,
    isProcessing: false,
    isOnline
  };
};

// Manual retry of queued requests
export const retryQueuedRequests = () => {
  toast('Requests are not queued. Retry the action explicitly.', { icon: 'ℹ️' });
};

export default api;
