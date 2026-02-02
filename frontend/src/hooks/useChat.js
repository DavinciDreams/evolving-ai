import { useMutation } from '@tanstack/react-query';
import { chatService } from '../services/chatService';
import toast from 'react-hot-toast';

export const useChat = () => {
  const sendMessage = useMutation({
    mutationFn: ({ query, contextHints = [] }) =>
      chatService.sendMessage(query, contextHints),
    onSuccess: (data) => {
      // Optionally show success feedback
      console.log('Message sent successfully', data);
    },
    onError: (error) => {
      console.error('Error sending message:', error);
      toast.error('Failed to send message');
    },
  });

  return {
    sendMessage: sendMessage.mutate,
    isLoading: sendMessage.isPending,
    error: sendMessage.error,
    data: sendMessage.data,
  };
};

export default useChat;
