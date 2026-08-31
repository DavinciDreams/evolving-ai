import ReactMarkdown from 'react-markdown';
import { PrismLight as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import python from 'react-syntax-highlighter/dist/esm/languages/prism/python';
import rust from 'react-syntax-highlighter/dist/esm/languages/prism/rust';
import javascript from 'react-syntax-highlighter/dist/esm/languages/prism/javascript';
import typescript from 'react-syntax-highlighter/dist/esm/languages/prism/typescript';
import json from 'react-syntax-highlighter/dist/esm/languages/prism/json';
import bash from 'react-syntax-highlighter/dist/esm/languages/prism/bash';
import powershell from 'react-syntax-highlighter/dist/esm/languages/prism/powershell';
import { formatRelativeTime } from '../../utils/formatting';
import Badge from '../common/Badge';
import clsx from 'clsx';

for (const [name, grammar] of Object.entries({ python, rust, javascript, typescript, json, bash, powershell })) {
  SyntaxHighlighter.registerLanguage(name, grammar);
}
const isScore = value => typeof value === 'number' && Number.isFinite(value) && value >= 0 && value <= 1;

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
                code({ inline, className, children }) {
                  const match = /language-(\w+)/.exec(className || '');
                  return !inline && match && String(children).length <= 16000 ? (
                    <SyntaxHighlighter
                      style={oneDark}
                      language={match[1]}
                      PreTag="div"
                    >
                      {String(children).replace(/\n$/, '')}
                    </SyntaxHighlighter>
                  ) : (
                    <code className={className}>
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

        {/* Evaluation score for AI responses */}
        {!isUser && (isScore(evaluation) || (evaluation && typeof evaluation === 'object' && Object.values(evaluation).some(isScore))) && (
          <div className="mt-3 pt-3 border-t border-gray-200 flex flex-wrap gap-2">
            <span className="w-full text-xs text-gray-600">Model self-judgment — not an independent benchmark</span>
            {typeof evaluation === 'object' ? (
              Object.entries(evaluation).filter(([, score]) => isScore(score)).map(([criterion, score]) => (
                <Badge key={criterion} variant="info" className="text-xs">
                  {criterion}: {(score * 100).toFixed(0)}%
                </Badge>
              ))
            ) : (
              <Badge variant="info" className="text-xs">
                Score: {(Number(evaluation) * 100).toFixed(0)}%
              </Badge>
            )}
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
