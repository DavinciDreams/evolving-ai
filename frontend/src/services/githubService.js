import { api } from './api';

export const githubService = {
  /**
   * Get GitHub connection status
   * @returns {Promise} GitHub status information
   */
  getStatus: async () => {
    const response = await api.get('/github/status');
    return response.data;
  },

  /**
   * Get repository information
   * @returns {Promise} Repository details
   */
  getRepository: async () => {
    const response = await api.get('/github/repository');
    return response.data;
  },

  /**
   * Get list of pull requests
   * @returns {Promise} Array of pull requests
   */
  getPullRequests: async () => {
    const response = await api.get('/github/pull-requests');
    return response.data;
  },

  /**
   * Get recent commits
   * @param {number} limit - Number of commits to fetch
   * @returns {Promise} Array of commits
   */
  getCommits: async (limit = 10) => {
    const response = await api.get('/github/commits', {
      params: { limit }
    });
    return response.data;
  },

  /**
   * Trigger code improvement analysis
   * @param {Object} data - Improvement parameters
   * @returns {Promise} Improvement result
   */
  triggerImprovement: async (data) => {
    const response = await api.post('/self-improve', data);
    return response.data;
  },

  /**
   * Create a demo pull request
   * @returns {Promise} PR creation result
   */
  createDemoPR: async () => {
    const response = await api.post('/github/demo-pr');
    return response.data;
  },

  /**
   * Get improvement history
   * @returns {Promise} Array of past improvements
   */
  getImprovementHistory: async () => {
    const response = await api.get('/github/improvement-history');
    return response.data;
  },
};

export const getGitHubStatus = githubService.getStatus;

export default githubService;
