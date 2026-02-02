import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { formatRelativeTime } from '../../utils/formatting';
import Badge from '../common/Badge';
import clsx from 'clsx';

export const MessageBubble = ({ message, isUser }) => {
  const { query, response, evaluation, timestamp } = message;
  const content = isUser ? query : response;

  return (
    <div className={clsx('flex', isUser ? 'justify-end' : 'justify-start')}>
      <div
        className={clsx(
          'max-w-3xl px-4 py-3 rounded-lg',
          isUser
            ? 'bg-indigo-600 text-white'
            : 'bg-white border border-gray-200'
        )}
      >
        {/* Content */}
        <div className={clsx('prose prose-sm max-w-none', !isUser && 'prose-gray')}>
          {isUser ? (
            <p className="text-white m-0">{content}</p>
          ) : (
            <ReactMarkdown
              components={{
                code({ node, inline, className, children, ...props }) {
                  const match = /language-(\w+)/.exec(className || '');
                  return !inline && match ? (
                    <SyntaxHighlighter
                      style={oneDark}
                      language={match[1]}
                      PreTag="div"
                      {...props}
                    >
                      {String(children).replace(/\n$/, '')}
                    </SyntaxHighlighter>
                  ) : (
                    <code className={className} {...props}>
                      {children}
                    </code>
                  );
                },
              }}
            >
              {content}
            </ReactMarkdown>
          )}
        </div>

        {/* Evaluation scores for AI responses */}
        {!isUser && evaluation && (
          <div className="mt-3 pt-3 border-t border-gray-200 flex flex-wrap gap-2">
            {Object.entries(evaluation).map(([criterion, score]) => (
              <Badge key={criterion} variant="info" className="text-xs">
                {criterion}: {(score * 100).toFixed(0)}%
              </Badge>
            ))}
          </div>
        )}

        {/* Timestamp */}
        <div
          className={clsx(
            'mt-2 text-xs',
            isUser ? 'text-indigo-100' : 'text-gray-500'
          )}
        >
          {formatRelativeTime(timestamp)}
        </div>
      </div>
    </div>
  );
};

export default MessageBubble;
