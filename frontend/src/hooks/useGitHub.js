import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { githubService } from '../services/githubService';
import toast from 'react-hot-toast';

export const useGitHubStatus = () => {
  return useQuery({
    queryKey: ['github-status'],
    queryFn: githubService.getStatus,
    refetchInterval: 30000, // Poll every 30 seconds
  });
};

export const useGitHubRepository = () => {
  return useQuery({
    queryKey: ['github-repository'],
    queryFn: githubService.getRepository,
    staleTime: 1000 * 60 * 10, // 10 minutes
  });
};

export const useGitHubPullRequests = () => {
  return useQuery({
    queryKey: ['github-prs'],
    queryFn: githubService.getPullRequests,
    refetchInterval: 60000, // Poll every minute
  });
};

export const useGitHubCommits = (limit = 10) => {
  return useQuery({
    queryKey: ['github-commits', limit],
    queryFn: () => githubService.getCommits(limit),
    staleTime: 1000 * 60 * 5, // 5 minutes
  });
};

export const useTriggerImprovement = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: githubService.triggerImprovement,
    onSuccess: () => {
      toast.success('Improvement triggered successfully!');
      queryClient.invalidateQueries(['github-prs']);
    },
    onError: (error) => {
      toast.error(`Failed to trigger improvement: ${error.message}`);
    },
  });
};
