import { api } from './api';

export const knowledgeService = {
  /**
   * Get knowledge base entries with optional filtering
   * @param {Object} params - Query parameters
   * @param {string} params.category - Filter by category
   * @param {number} params.limit - Number of results
   * @param {number} params.offset - Pagination offset
   * @returns {Promise} Array of knowledge entries
   */
  getKnowledge: async (params = {}) => {
    const response = await api.get('/knowledge', { params });
    return response.data;
  },

  /**
   * Get knowledge entries by category
   * @param {string} category - Category to filter by
   * @returns {Promise} Array of knowledge entries
   */
  getByCategory: async (category) => {
    const response = await api.get('/knowledge', {
      params: { category }
    });
    return response.data;
  },
};

export default knowledgeService;
