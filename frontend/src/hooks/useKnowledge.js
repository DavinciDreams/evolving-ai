import { useQuery } from '@tanstack/react-query';
import { knowledgeService } from '../services/knowledgeService';

export const useKnowledge = (category = '', limit = 50) => {
  return useQuery({
    queryKey: ['knowledge', category, limit],
    queryFn: () => knowledgeService.getKnowledge({ category, limit }),
    staleTime: 1000 * 60 * 5, // 5 minutes
  });
};

export default useKnowledge;
