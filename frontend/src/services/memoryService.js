import { api } from './api';

export const memoryService = {
  /**
   * Get memories with optional search and pagination
   * @param {Object} params - Query parameters
   * @param {string} params.search - Search query
   * @param {number} params.limit - Number of results
   * @param {number} params.offset - Pagination offset
   * @returns {Promise} Array of memory entries
   */
  getMemories: async (params = {}) => {
    const response = await api.get('/memories', { params });
    return response.data;
  },

  /**
   * Search for specific memories
   * @param {string} search - Search query
   * @param {number} limit - Number of results
   * @returns {Promise} Array of matching memories
   */
  searchMemories: async (search, limit = 10) => {
    const response = await api.get('/memories', {
      params: { search, limit }
    });
    return response.data;
  },
};

export default memoryService;
