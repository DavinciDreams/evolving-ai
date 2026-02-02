import axios from 'axios';
import toast from 'react-hot-toast';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  // Increased timeout to 90s to accommodate LLM response times (especially with improvement evaluation)
  timeout: 90000,
});

// Request interceptor
api.interceptors.request.use(
  (config) => {
    // Add auth token if available (future enhancement)
    // const token = localStorage.getItem('token');
    // if (token) {
    //   config.headers.Authorization = `Bearer ${token}`;
    // }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor
api.interceptors.response.use(
  (response) => response,
  (error) => {
    // Global error handling
    const message = error.response?.data?.detail ||
                    error.response?.data?.message ||
                    error.message ||
                    'An error occurred';

    // Show toast notification for errors
    toast.error(message);

    return Promise.reject(error);
  }
);

// Agent Status API
export const getAgentStatus = async () => {
  const response = await api.get('/status');
  return response.data;
};

export const getHealthStatus = async () => {
  const response = await api.get('/health');
  return response.data;
};

export default api;
