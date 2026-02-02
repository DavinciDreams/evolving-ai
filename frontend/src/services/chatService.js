import { api } from './api';

export const chatService = {
  /**
   * Send a message to the agent and get a response
   * @param {string} query - The user's query
   * @param {string[]} contextHints - Optional context hints
   * @returns {Promise} Response with agent's message
   */
  sendMessage: async (query, contextHints = []) => {
    const response = await api.post('/chat', {
      query,
      context_hints: contextHints
    });
    return response.data;
  },

  // Future: WebSocket streaming implementation
  // streamMessage: (query, onChunk) => {
  //   // WebSocket implementation for streaming responses
  // }
};

export default chatService;
