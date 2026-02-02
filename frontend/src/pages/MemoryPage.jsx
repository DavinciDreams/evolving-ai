import { useState } from 'react';
import Card from '../components/common/Card';
import Input from '../components/common/Input';
import Spinner from '../components/common/Spinner';
import Badge from '../components/common/Badge';
import useMemories from '../hooks/useMemory';
import { useDebounce } from '../hooks/useDebounce';
import { formatRelativeTime, truncateText } from '../utils/formatting';

const MemoryPage = () => {
  const [searchQuery, setSearchQuery] = useState('');
  const debouncedSearch = useDebounce(searchQuery, 500);
  const { data: memories, isLoading, error } = useMemories(debouncedSearch);

  return (
    <div className="max-w-7xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Memory Browser</h1>
        <p className="text-gray-600 mt-1">Browse and search through stored memories</p>
      </div>

      <Card className="mb-6">
        <Input
          type="text"
          placeholder="Search memories..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
        />
      </Card>

      {isLoading ? (
        <Card>
          <Spinner className="h-64" />
        </Card>
      ) : error ? (
        <Card>
          <div className="text-center text-red-600 py-8">
            Error loading memories: {error.message}
          </div>
        </Card>
      ) : memories && memories.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {memories.map((memory, index) => (
            <Card key={index} className="hover:shadow-lg transition-shadow">
              <div className="space-y-2">
                <Badge variant="secondary">{formatRelativeTime(memory.timestamp)}</Badge>
                <p className="text-gray-700 text-sm">{truncateText(memory.content, 150)}</p>
                {memory.metadata && (
                  <div className="pt-2 border-t">
                    <p className="text-xs text-gray-500">
                      Type: {memory.metadata.type || 'N/A'}
                    </p>
                  </div>
                )}
              </div>
            </Card>
          ))}
        </div>
      ) : (
        <Card>
          <div className="text-center text-gray-500 py-8">
            {searchQuery ? 'No memories found matching your search.' : 'No memories stored yet.'}
          </div>
        </Card>
      )}
    </div>
  );
};

export default MemoryPage;
