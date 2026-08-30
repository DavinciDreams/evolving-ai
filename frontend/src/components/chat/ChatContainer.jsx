import { useState, useRef, useCallback, useEffect } from 'react';
import MessageList from './MessageList';
import ChatInput from './ChatInput';
import { Link } from 'react-router-dom';
import useChat from '../../hooks/useChat';
import { SparklesIcon } from '@heroicons/react/24/outline';
import MediaPanel from './MediaPanel';

const STORAGE_KEY = 'evolving-ai-chat-messages';
const CONVERSATION_KEY = 'evolving-ai-conversation-id';

function loadMessages() {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    return stored ? JSON.parse(stored) : [];
  } catch {
    return [];
  }
}

function getConversationId() {
  let id = localStorage.getItem(CONVERSATION_KEY);
  if (!id) {
    id = `chat_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    localStorage.setItem(CONVERSATION_KEY, id);
  }
  return id;
}

export const ChatContainer = () => {
  const [messages, setMessages] = useState(loadMessages);
  const [isSending, setIsSending] = useState(false);
  const { sendMessageAsync } = useChat();

  // Persistent conversation ID
  const conversationIdRef = useRef(getConversationId());

  // Persist messages to localStorage on change
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(messages));
    } catch {
      // localStorage full or unavailable
    }
  }, [messages]);

  const handleSendMessage = async (query) => {
    if (isSending) return;
    const msgId = `msg_${Date.now()}_${Math.random().toString(36).substr(2, 6)}`;

    // Add user message immediately
    const userMessage = {
      id: msgId,
      query,
      timestamp: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMessage]);
    setIsSending(true);

    try {
      const data = await sendMessageAsync({
        query,
        conversationId: conversationIdRef.current,
      });

      // Find and update this specific message by ID
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === msgId
            ? {
                ...msg,
                response: data.response,
                evaluation: data.evaluation_score,
              }
            : msg
        )
      );
    } catch (error) {
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === msgId
            ? {
                ...msg,
                response: `Error: ${error?.response?.data?.detail || error?.message || 'Failed to get response'}`,
                isError: true,
              }
            : msg
        )
      );
    } finally {
      setIsSending(false);
    }
  };

  const handleClearChat = useCallback(() => {
    setMessages([]);
    localStorage.removeItem(STORAGE_KEY);
    const newId = `chat_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    conversationIdRef.current = newId;
    localStorage.setItem(CONVERSATION_KEY, newId);
  }, []);

  return (
    <div className="flex flex-col h-full">
      <MessageList messages={messages} isLoading={isSending} />
      <MediaPanel onUseText={handleSendMessage} disabled={isSending}
        latestResponse={[...messages].reverse().find(message => message.response && !message.isError)?.response || ''} />

      <div className="border-t border-gray-200 p-4 bg-gray-50">
        <div className="flex items-end gap-2">
          <div className="flex-1">
            <ChatInput
              onSend={handleSendMessage}
              isLoading={isSending}
              disabled={false}
            />
          </div>
          <Link to="/status" className="flex items-center gap-1 rounded-lg border border-indigo-200 bg-indigo-50 px-3 py-2 text-sm font-medium text-indigo-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-indigo-600 self-end mb-1">
            <SparklesIcon className="h-4 w-4" aria-hidden="true" />
            <span>Learning lab</span>
          </Link>
          {messages.length > 0 && (
            <button
              onClick={handleClearChat}
              className="px-3 py-2 text-sm font-medium text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-colors self-end mb-1"
              title="Clear chat history"
              aria-label="Clear chat history"
            >
              Clear
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

export default ChatContainer;
