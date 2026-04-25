import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

vi.mock('../../services/chatService', () => ({
  chatService: { sendMessage: vi.fn() },
  default: { sendMessage: vi.fn() },
}));

vi.mock('react-hot-toast', () => ({
  default: Object.assign(vi.fn(), { error: vi.fn(), success: vi.fn() }),
}));

import { useChat } from '../../hooks/useChat';
import { chatService } from '../../services/chatService';

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: { mutations: { retry: false } },
  });
  return ({ children }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
};

describe('useChat', () => {
  beforeEach(() => vi.clearAllMocks());

  it('returns sendMessage and isLoading=false initially', () => {
    const { result } = renderHook(() => useChat(), { wrapper: createWrapper() });

    expect(typeof result.current.sendMessage).toBe('function');
    expect(typeof result.current.sendMessageAsync).toBe('function');
    expect(result.current.isLoading).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it('isLoading is true while mutation is in flight', async () => {
    chatService.sendMessage.mockImplementation(() => new Promise(() => {}));

    const { result } = renderHook(() => useChat(), { wrapper: createWrapper() });

    act(() => {
      result.current.sendMessage({ query: 'hello', contextHints: [], conversationId: null });
    });

    expect(result.current.isLoading).toBe(true);
  });

  it('data is set after successful sendMessageAsync', async () => {
    const responseData = { response: 'Hi there' };
    chatService.sendMessage.mockResolvedValueOnce(responseData);

    const { result } = renderHook(() => useChat(), { wrapper: createWrapper() });

    await act(async () => {
      await result.current.sendMessageAsync({
        query: 'hello',
        contextHints: [],
        conversationId: null,
      });
    });

    expect(chatService.sendMessage).toHaveBeenCalledWith('hello', [], null);
    expect(result.current.data).toEqual(responseData);
    expect(result.current.isLoading).toBe(false);
  });

  it('error is set when mutation fails', async () => {
    const networkError = new Error('API error');
    chatService.sendMessage.mockRejectedValueOnce(networkError);

    const { result } = renderHook(() => useChat(), { wrapper: createWrapper() });

    await act(async () => {
      try {
        await result.current.sendMessageAsync({
          query: 'bad',
          contextHints: [],
          conversationId: null,
        });
      } catch (_) {
        // mutateAsync re-throws — expected
      }
    });

    expect(result.current.error).toEqual(networkError);
    expect(result.current.isLoading).toBe(false);
  });
});
