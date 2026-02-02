import { useState } from 'react';
import { PaperAirplaneIcon } from '@heroicons/react/24/solid';
import Button from '../common/Button';
import clsx from 'clsx';

export const ChatInput = ({ onSend, isLoading, disabled }) => {
  const [message, setMessage] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    if (message.trim() && !isLoading) {
      onSend(message.trim());
      setMessage('');
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="flex gap-2">
      <textarea
        value={message}
        onChange={(e) => setMessage(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Type your message... (Shift+Enter for new line)"
        disabled={disabled || isLoading}
        className={clsx(
          'flex-1 px-4 py-3 border border-gray-300 rounded-lg',
          'focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500',
          'resize-none',
          (disabled || isLoading) && 'opacity-50 cursor-not-allowed'
        )}
        rows={3}
      />
      <Button
        type="submit"
        disabled={!message.trim() || isLoading || disabled}
        className="self-end"
      >
        <PaperAirplaneIcon className="h-5 w-5" />
        <span className="ml-2">{isLoading ? 'Sending...' : 'Send'}</span>
      </Button>
    </form>
  );
};

export default ChatInput;
