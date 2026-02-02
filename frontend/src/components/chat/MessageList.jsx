import { useEffect, useRef } from 'react';
import MessageBubble from './MessageBubble';
import Spinner from '../common/Spinner';

export const MessageList = ({ messages, isLoading }) => {
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  if (messages.length === 0 && !isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center text-gray-500">
        <div className="text-center">
          <p className="text-lg font-medium">No messages yet</p>
          <p className="text-sm mt-1">Start a conversation with the AI agent</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto px-4 py-6 space-y-4">
      {messages.map((message, index) => (
        <div key={index}>
          {/* User message */}
          <MessageBubble message={message} isUser={true} />

          {/* AI response */}
          {message.response && (
            <div className="mt-4">
              <MessageBubble message={message} isUser={false} />
            </div>
          )}
        </div>
      ))}

      {/* Loading indicator */}
      {isLoading && (
        <div className="flex justify-start">
          <div className="bg-white border border-gray-200 px-4 py-3 rounded-lg">
            <Spinner size="sm" />
          </div>
        </div>
      )}

      <div ref={messagesEndRef} />
    </div>
  );
};

export default MessageList;
