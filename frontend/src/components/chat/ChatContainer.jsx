import { useState, useRef, useCallback, useEffect } from 'react';
import MessageList from './MessageList';
import ChatInput from './ChatInput';
import { ImprovementStatus } from './ImprovementStatus';
import useChat from '../../hooks/useChat';
import { useTriggerImprovement } from '../../hooks/useGitHub';
import { SparklesIcon } from '@heroicons/react/24/outline';

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

  // Improvement state
  const [improvementState, setImprovementState] = useState(null);
  const improvementStartTimeRef = useRef(null);

  // Persistent conversation ID
  const conversationIdRef = useRef(getConversationId());

  const { mutate: triggerImprovement, isPending: isImproving } = useTriggerImprovement();

  // Persist messages to localStorage on change
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(messages));
    } catch {
      // localStorage full or unavailable
    }
  }, [messages]);

  const handleSendMessage = async (query) => {
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

  const handleTriggerImprovement = useCallback(() => {
    const startTime = new Date().toISOString();
    improvementStartTimeRef.current = startTime;

    setImprovementState({
      isActive: true,
      isComplete: false,
      hasError: false,
      errorMessage: '',
      progressUpdates: [
        {
          event_type: 'analyzing',
          data: { stage: 'analyzing', message: 'Starting self-improvement analysis...', progress: 10 },
          timestamp: startTime,
        },
      ],
      prCreated: false,
      prNumber: null,
      prUrl: null,
      startTime,
    });

    triggerImprovement(
      { create_pr: true },
      {
        onSuccess: (data) => {
          setImprovementState((prev) => ({
            ...prev,
            isComplete: true,
            hasError: false,
            prCreated: data.pr_created || false,
            prNumber: data.pr_number,
            prUrl: data.pr_url,
            progressUpdates: [
              ...prev.progressUpdates,
              {
                event_type: 'validation',
                data: {
                  stage: 'validation',
                  message: `Generated ${data.improvements_generated} improvements, ${data.improvements_validated} validated`,
                  progress: 80,
                },
                timestamp: new Date().toISOString(),
              },
              {
                event_type: 'complete',
                data: {
                  stage: 'complete',
                  message: data.pr_created
                    ? `Pull request #${data.pr_number} created successfully`
                    : `${data.improvements_validated} improvements validated (potential: ${(data.improvement_potential * 100).toFixed(0)}%)`,
                  progress: 100,
                  details: {
                    generated: data.improvements_generated,
                    validated: data.improvements_validated,
                    potential: data.improvement_potential,
                  },
                },
                timestamp: new Date().toISOString(),
              },
            ],
          }));
        },
        onError: (error) => {
          setImprovementState((prev) => ({
            ...prev,
            isComplete: false,
            hasError: true,
            errorMessage: error.response?.data?.detail || error.message || 'Improvement failed',
            progressUpdates: [
              ...prev.progressUpdates,
              {
                event_type: 'error',
                data: { stage: 'error', message: 'Improvement process failed', progress: 0 },
                timestamp: new Date().toISOString(),
              },
            ],
          }));
        },
      }
    );
  }, [triggerImprovement]);

  const handleRetryImprovement = useCallback(() => {
    handleTriggerImprovement();
  }, [handleTriggerImprovement]);

  const handleCancelImprovement = useCallback(() => {
    setImprovementState(null);
  }, []);

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

      {/* Improvement Status */}
      {improvementState?.isActive && (
        <div className="px-4 py-2">
          <ImprovementStatus
            improvementType="full_improvement_cycle"
            progressUpdates={improvementState.progressUpdates}
            isComplete={improvementState.isComplete}
            hasError={improvementState.hasError}
            errorMessage={improvementState.errorMessage}
            prCreated={improvementState.prCreated}
            prNumber={improvementState.prNumber}
            prUrl={improvementState.prUrl}
            startTime={improvementState.startTime}
            onRetry={handleRetryImprovement}
            onCancel={!improvementState.isComplete && !improvementState.hasError ? handleCancelImprovement : null}
          />
        </div>
      )}

      <div className="border-t border-gray-200 p-4 bg-gray-50">
        <div className="flex items-end gap-2">
          <div className="flex-1">
            <ChatInput
              onSend={handleSendMessage}
              isLoading={isSending}
              disabled={false}
            />
          </div>
          <button
            onClick={handleTriggerImprovement}
            disabled={isImproving || (improvementState?.isActive && !improvementState?.isComplete && !improvementState?.hasError)}
            className="flex items-center gap-1 px-3 py-2 text-sm font-medium text-indigo-600 bg-indigo-50 border border-indigo-200 rounded-lg hover:bg-indigo-100 disabled:opacity-50 disabled:cursor-not-allowed transition-colors self-end mb-1"
            title="Trigger self-improvement cycle"
          >
            <SparklesIcon className="h-4 w-4" />
            <span className="hidden sm:inline">Improve</span>
          </button>
          {messages.length > 0 && (
            <button
              onClick={handleClearChat}
              className="px-3 py-2 text-sm font-medium text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-colors self-end mb-1"
              title="Clear chat history"
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
