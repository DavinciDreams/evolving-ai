import { api } from './api';

export const chatService = {
  /**
   * Send a message to the agent and get a response
   * @param {string} query - The user's query
   * @param {string[]} contextHints - Optional context hints
   * @param {string} conversationId - Optional conversation ID for tracking
   * @returns {Promise} Response with agent's message
   */
  sendMessage: async (query, contextHints = [], conversationId = null) => {
    const payload = {
      query,
      context_hints: contextHints
    };

    if (conversationId) {
      payload.conversation_id = conversationId;
    }

    const response = await api.post('/chat', payload);
    return response.data;
  },

  // Future: WebSocket streaming implementation
  // streamMessage: (query, onChunk) => {
  //   // WebSocket implementation for streaming responses
  // }
};

export default chatService;
