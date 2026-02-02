import { useState } from 'react';
import Card from '../components/common/Card';
import Badge from '../components/common/Badge';
import Spinner from '../components/common/Spinner';
import useKnowledge from '../hooks/useKnowledge';
import { KNOWLEDGE_CATEGORIES } from '../utils/constants';
import { formatScore } from '../utils/formatting';
import clsx from 'clsx';

const KnowledgePage = () => {
  const [selectedCategory, setSelectedCategory] = useState('');
  const { data: knowledge, isLoading, error } = useKnowledge(selectedCategory);

  return (
    <div className="max-w-7xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Knowledge Base</h1>
        <p className="text-gray-600 mt-1">Explore the agent's knowledge organized by categories</p>
      </div>

      <Card className="mb-6">
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => setSelectedCategory('')}
            className={clsx(
              'px-4 py-2 rounded-md text-sm font-medium transition-colors',
              selectedCategory === ''
                ? 'bg-indigo-600 text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            )}
          >
            All
          </button>
          {KNOWLEDGE_CATEGORIES.map((category) => (
            <button
              key={category}
              onClick={() => setSelectedCategory(category)}
              className={clsx(
                'px-4 py-2 rounded-md text-sm font-medium transition-colors',
                selectedCategory === category
                  ? 'bg-indigo-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              )}
            >
              {category}
            </button>
          ))}
        </div>
      </Card>

      {isLoading ? (
        <Card>
          <Spinner className="h-64" />
        </Card>
      ) : error ? (
        <Card>
          <div className="text-center text-red-600 py-8">
            Error loading knowledge: {error.message}
          </div>
        </Card>
      ) : knowledge && knowledge.length > 0 ? (
        <div className="space-y-4">
          {knowledge.map((item, index) => (
            <Card key={index}>
              <div className="space-y-3">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <p className="text-gray-900 font-medium">{item.content}</p>
                  </div>
                  <Badge variant="primary">{item.category}</Badge>
                </div>
                <div className="flex items-center gap-4 text-sm text-gray-500">
                  <span>Confidence: {formatScore(item.confidence)}</span>
                  <span>•</span>
                  <span>Used: {item.usage_count || 0} times</span>
                </div>
              </div>
            </Card>
          ))}
        </div>
      ) : (
        <Card>
          <div className="text-center text-gray-500 py-8">
            {selectedCategory ? `No knowledge in category "${selectedCategory}".` : 'No knowledge stored yet.'}
          </div>
        </Card>
      )}
    </div>
  );
};

export default KnowledgePage;
