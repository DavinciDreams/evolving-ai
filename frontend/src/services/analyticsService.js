import { api } from './api';

export const analyticsService = {
  /**
   * Get overall agent status
   * @returns {Promise} Agent status with counts and metrics
   */
  getStatus: async () => {
    const response = await api.get('/status');
    return response.data;
  },

  /**
   * Get health check status
   * @returns {Promise} Health status
   */
  getHealth: async () => {
    const response = await api.get('/health');
    return response.data;
  },

  /**
   * Get code analysis history
   * @returns {Promise} Array of analysis results
   */
  getAnalysisHistory: async () => {
    const response = await api.get('/analysis-history');
    return response.data;
  },

  /**
   * Trigger code analysis
   * @param {Object} data - Analysis parameters
   * @returns {Promise} Analysis results
   */
  analyzeCode: async (data = {}) => {
    const response = await api.post('/analyze', data);
    return response.data;
  },
};

export default analyticsService;
