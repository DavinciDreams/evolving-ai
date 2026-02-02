import { useQuery } from '@tanstack/react-query';
import { memoryService } from '../services/memoryService';

export const useMemories = (searchQuery = '', limit = 20) => {
  return useQuery({
    queryKey: ['memories', searchQuery, limit],
    queryFn: () => memoryService.getMemories({ search: searchQuery, limit }),
    staleTime: 1000 * 60 * 2, // 2 minutes
  });
};

export default useMemories;
