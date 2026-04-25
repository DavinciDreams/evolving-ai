import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('../../services/api', () => {
  const mockApi = {
    get: vi.fn(),
    post: vi.fn(),
    interceptors: {
      request: { use: vi.fn() },
      response: { use: vi.fn() },
    },
  };
  return { api: mockApi, default: mockApi };
});

vi.mock('react-hot-toast', () => ({
  default: Object.assign(vi.fn(), { error: vi.fn(), success: vi.fn() }),
}));

import { api } from '../../services/api';
import { chatService } from '../../services/chatService';
import { memoryService } from '../../services/memoryService';
import { knowledgeService } from '../../services/knowledgeService';
import { githubService } from '../../services/githubService';

describe('chatService', () => {
  beforeEach(() => vi.clearAllMocks());

  it('sendMessage posts to /chat with query and context_hints', async () => {
    api.post.mockResolvedValueOnce({ data: { response: 'Hello' } });

    const result = await chatService.sendMessage('hello', ['hint1'], 'conv-123');

    expect(api.post).toHaveBeenCalledWith('/chat', {
      query: 'hello',
      context_hints: ['hint1'],
      conversation_id: 'conv-123',
    });
    expect(result).toEqual({ response: 'Hello' });
  });

  it('sendMessage omits conversation_id when null', async () => {
    api.post.mockResolvedValueOnce({ data: {} });

    await chatService.sendMessage('hello');

    const [, payload] = api.post.mock.calls[0];
    expect(payload).not.toHaveProperty('conversation_id');
    expect(payload.context_hints).toEqual([]);
  });

  it('sendMessage propagates errors', async () => {
    api.post.mockRejectedValueOnce(new Error('Network error'));

    await expect(chatService.sendMessage('hello')).rejects.toThrow('Network error');
  });
});

describe('memoryService', () => {
  beforeEach(() => vi.clearAllMocks());

  it('getMemories calls GET /memories with params object', async () => {
    api.get.mockResolvedValueOnce({ data: [{ id: 1 }] });

    const result = await memoryService.getMemories({ search: 'test', limit: 5 });

    expect(api.get).toHaveBeenCalledWith('/memories', { params: { search: 'test', limit: 5 } });
    expect(result).toEqual([{ id: 1 }]);
  });

  it('getMemories works with no params', async () => {
    api.get.mockResolvedValueOnce({ data: [] });

    await memoryService.getMemories();

    expect(api.get).toHaveBeenCalledWith('/memories', { params: {} });
  });

  it('searchMemories calls GET /memories with search and limit', async () => {
    api.get.mockResolvedValueOnce({ data: [] });

    await memoryService.searchMemories('cats', 5);

    expect(api.get).toHaveBeenCalledWith('/memories', { params: { search: 'cats', limit: 5 } });
  });
});

describe('knowledgeService', () => {
  beforeEach(() => vi.clearAllMocks());

  it('getKnowledge calls GET /knowledge with params', async () => {
    api.get.mockResolvedValueOnce({ data: [{ id: 1, category: 'Technical' }] });

    const result = await knowledgeService.getKnowledge({ category: 'Technical' });

    expect(api.get).toHaveBeenCalledWith('/knowledge', { params: { category: 'Technical' } });
    expect(result).toEqual([{ id: 1, category: 'Technical' }]);
  });

  it('getByCategory calls GET /knowledge filtered by category', async () => {
    api.get.mockResolvedValueOnce({ data: [] });

    await knowledgeService.getByCategory('General');

    expect(api.get).toHaveBeenCalledWith('/knowledge', { params: { category: 'General' } });
  });
});

describe('githubService', () => {
  beforeEach(() => vi.clearAllMocks());

  it('getStatus calls GET /github/status', async () => {
    api.get.mockResolvedValueOnce({ data: { connected: true } });

    const result = await githubService.getStatus();

    expect(api.get).toHaveBeenCalledWith('/github/status');
    expect(result).toEqual({ connected: true });
  });

  it('triggerImprovement posts to /self-improve', async () => {
    api.post.mockResolvedValueOnce({ data: { started: true } });

    const result = await githubService.triggerImprovement({ target: 'api.py' });

    expect(api.post).toHaveBeenCalledWith('/self-improve', { target: 'api.py' });
    expect(result).toEqual({ started: true });
  });

  it('getStatus propagates errors', async () => {
    api.get.mockRejectedValueOnce(new Error('Forbidden'));

    await expect(githubService.getStatus()).rejects.toThrow('Forbidden');
  });

  it('getPullRequests calls GET /github/pull-requests', async () => {
    api.get.mockResolvedValueOnce({ data: [] });

    await githubService.getPullRequests();

    expect(api.get).toHaveBeenCalledWith('/github/pull-requests');
  });
});
