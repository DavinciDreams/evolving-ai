import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

vi.mock('../../services/memoryService', () => ({
  memoryService: { getMemories: vi.fn() },
  default: { getMemories: vi.fn() },
}));

import { useMemories } from '../../hooks/useMemory';
import { memoryService } from '../../services/memoryService';

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return ({ children }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
};

describe('useMemories', () => {
  beforeEach(() => vi.clearAllMocks());

  it('fetches memories on mount with default params', async () => {
    const mockMemories = [{ id: 1, content: 'test memory' }];
    memoryService.getMemories.mockResolvedValueOnce(mockMemories);

    const { result } = renderHook(() => useMemories(), { wrapper: createWrapper() });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(memoryService.getMemories).toHaveBeenCalledWith({ search: '', limit: 20 });
    expect(result.current.data).toEqual(mockMemories);
  });

  it('passes search query and limit to API', async () => {
    memoryService.getMemories.mockResolvedValueOnce([]);

    const { result } = renderHook(() => useMemories('cats', 5), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(memoryService.getMemories).toHaveBeenCalledWith({ search: 'cats', limit: 5 });
  });

  it('starts in loading state', () => {
    memoryService.getMemories.mockImplementation(() => new Promise(() => {}));

    const { result } = renderHook(() => useMemories(), { wrapper: createWrapper() });

    expect(result.current.isLoading).toBe(true);
  });

  it('exposes error when fetch fails', async () => {
    memoryService.getMemories.mockRejectedValueOnce(new Error('DB unavailable'));

    const { result } = renderHook(() => useMemories(), { wrapper: createWrapper() });

    await waitFor(() => expect(result.current.isError).toBe(true));

    expect(result.current.error.message).toBe('DB unavailable');
  });
});
