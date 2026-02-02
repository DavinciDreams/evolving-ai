import { api } from './api';

export const discordService = {
  /**
   * Get Discord bot status and connection information
   * @returns {Promise} Discord status
   */
  getStatus: async () => {
    const response = await api.get('/discord/status');
    return response.data;
  },
};

export const getDiscordStatus = discordService.getStatus;

export default discordService;
