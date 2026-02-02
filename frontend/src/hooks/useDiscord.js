import { useQuery } from '@tanstack/react-query';
import { discordService } from '../services/discordService';

export const useDiscordStatus = () => {
  return useQuery({
    queryKey: ['discord-status'],
    queryFn: discordService.getStatus,
    refetchInterval: 30000, // Poll every 30 seconds
    staleTime: 1000 * 60 * 2, // 2 minutes
  });
};

export default useDiscordStatus;
