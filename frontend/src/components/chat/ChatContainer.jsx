import { useState } from 'react';
import MessageList from './MessageList';
import ChatInput from './ChatInput';
import useChat from '../../hooks/useChat';

export const ChatContainer = () => {
  const [messages, setMessages] = useState([]);
  const { sendMessage, isLoading } = useChat();

  const handleSendMessage = async (query) => {
    // Add user message immediately
    const userMessage = {
      query,
      timestamp: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMessage]);

    // Send to API
    sendMessage(
      { query },
      {
        onSuccess: (data) => {
          // Update the last message with the response
          setMessages((prev) => {
            const updated = [...prev];
            const lastMessage = updated[updated.length - 1];
            updated[updated.length - 1] = {
              ...lastMessage,
              response: data.response,
              evaluation: data.evaluation,
              improved_response: data.improved_response,
            };
            return updated;
          });
        },
      }
    );
  };

  return (
    <div className="flex flex-col h-full">
      <MessageList messages={messages} isLoading={isLoading} />
      <div className="border-t border-gray-200 p-4 bg-gray-50">
        <ChatInput
          onSend={handleSendMessage}
          isLoading={isLoading}
          disabled={false}
        />
      </div>
    </div>
  );
};

export default ChatContainer;
