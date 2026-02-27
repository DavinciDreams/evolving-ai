import { useMutation } from '@tanstack/react-query';
import { chatService } from '../services/chatService';
import toast from 'react-hot-toast';

export const useChat = () => {
  const mutation = useMutation({
    mutationFn: ({ query, contextHints = [], conversationId = null }) =>
      chatService.sendMessage(query, contextHints, conversationId),
    onError: (error) => {
      console.error('Error sending message:', error);
      toast.error(error?.response?.data?.detail || error?.message || 'Failed to send message');
    },
  });

  return {
    sendMessageAsync: mutation.mutateAsync,
    sendMessage: mutation.mutate,
    isLoading: mutation.isPending,
    error: mutation.error,
    data: mutation.data,
  };
};

export default useChat;
