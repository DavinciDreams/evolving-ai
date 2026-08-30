import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { AxiosError } from 'axios';

vi.mock('react-hot-toast', () => ({
  default: Object.assign(vi.fn(), { error: vi.fn(), success: vi.fn() }),
}));

import { api, clearProjectApiKey, getRequestQueueStatus, setProjectApiKey } from '../../services/api';

const responseFor = (config) => ({ data: {}, status: 200, statusText: 'OK', headers: {}, config });
const rejected = (config, status, code = 'ERR_BAD_RESPONSE') => {
  const response = status ? { status, data: { detail: 'opaque-response-secret' }, config } : undefined;
  const error = new AxiosError('opaque-error-secret', code, config, { raw: 'transport-secret' }, response);
  error.cause = { raw: 'cause-secret', config };
  return error;
};

beforeEach(() => {
  clearProjectApiKey();
  vi.clearAllMocks();
});

afterEach(() => {
  clearProjectApiKey();
  vi.useRealTimers();
});

describe('bounded explicit API actions', () => {
  it.each([500, 502, 503, 504, 429])('never retries a POST after HTTP %s', async (status) => {
    const adapter = vi.fn(async config => { throw rejected(config, status); });
    api.defaults.adapter = adapter;
    await expect(api.post('/media/speech', { text: 'hello' })).rejects.toThrow();
    expect(adapter).toHaveBeenCalledTimes(1);
    expect(getRequestQueueStatus().queueLength).toBe(0);
  });

  it('never retries a timed-out POST even without a noRetry option', async () => {
    const adapter = vi.fn(async config => { throw rejected(config, undefined, 'ECONNABORTED'); });
    api.defaults.adapter = adapter;
    await expect(api.post('/steward/dream', {})).rejects.toThrow();
    expect(adapter).toHaveBeenCalledTimes(1);
  });

  it('explains retired actions without echoing response text or offering a retry', async () => {
    const adapter = vi.fn(async config => {
      const error = rejected(config, 410);
      error.message = 'timeout opaque-error-secret';
      error.response.data.detail = 'timeout opaque-response-secret';
      throw error;
    });
    api.defaults.adapter = adapter;
    const error = await api.post('/self-improve', {}).catch(value => value);
    expect(error.message).toBe('This legacy action is retired. Use measured steward controls or a separately authorized publishing workflow.');
    expect(error.response.data.detail).toBe(error.message);
    expect(String(error) + JSON.stringify(error)).not.toMatch(/opaque|timeout|retry/i);
    expect(adapter).toHaveBeenCalledTimes(1);
  });

  it('honors noRetry for GET requests', async () => {
    const adapter = vi.fn(async config => { throw rejected(config, 500); });
    api.defaults.adapter = adapter;
    await expect(api.get('/media/status', { noRetry: true })).rejects.toThrow();
    expect(adapter).toHaveBeenCalledTimes(1);
  });

  it('recovers after a network error without reloading or replaying the failed POST', async () => {
    const calls = [];
    api.defaults.adapter = async config => {
      calls.push(config.url);
      if (calls.length === 1) throw rejected(config, undefined, 'ERR_NETWORK');
      return responseFor(config);
    };
    await expect(api.post('/media/vision', { data_base64: 'private-image' })).rejects.toThrow();
    expect(getRequestQueueStatus().isOnline).toBe(false);
    await expect(api.get('/media/status')).resolves.toMatchObject({ status: 200 });
    expect(getRequestQueueStatus()).toEqual({ isOnline: true, queueLength: 0, isProcessing: false });
    expect(calls).toEqual(['/media/vision', '/media/status']);
  });

  it('allows a later explicitly requested POST to test network recovery', async () => {
    let calls = 0;
    api.defaults.adapter = async config => {
      calls += 1;
      if (calls === 1) throw rejected(config, undefined, 'ERR_NETWORK');
      return responseFor(config);
    };
    await expect(api.post('/media/speech', { text: 'first' })).rejects.toThrow();
    await expect(api.post('/media/speech', { text: 'explicit second attempt' })).resolves.toMatchObject({ status: 200 });
    expect(calls).toBe(2);
  });

  it('removes credentials, bodies, transport objects and server input echoes from errors', async () => {
    setProjectApiKey('project-secret');
    api.defaults.adapter = async config => { throw rejected(config, 422); };
    const error = await api.post('/media/vision', { data_base64: 'private-image-secret' }).catch(value => value);
    expect(error.config).toBeUndefined();
    expect(error.request).toBeUndefined();
    expect(error.cause).toBeUndefined();
    expect(error.response.config).toBeUndefined();
    expect(error.response.status).toBe(422);
    for (const secret of ['project-secret', 'private-image-secret', 'opaque-response-secret', 'opaque-error-secret', 'transport-secret', 'cause-secret']) {
      expect(String(error) + JSON.stringify(error)).not.toContain(secret);
    }
  });

  it('does not replay credentials after logout during a safe-read backoff', async () => {
    vi.useFakeTimers();
    setProjectApiKey('must-not-replay');
    const attempted = [];
    api.defaults.adapter = async config => {
      attempted.push(config.headers.get('X-API-Key'));
      throw rejected(config, 500);
    };
    const outcome = api.get('/status').catch(error => error);
    await vi.advanceTimersByTimeAsync(0);
    expect(attempted).toEqual(['must-not-replay']);
    clearProjectApiKey();
    await vi.runAllTimersAsync();
    expect(await outcome).toBeInstanceOf(Error);
    expect(attempted).toEqual(['must-not-replay']);
  });

  it('still retries a safe GET when credentials remain current', async () => {
    vi.useFakeTimers();
    let calls = 0;
    api.defaults.adapter = async config => {
      calls += 1;
      if (calls === 1) throw rejected(config, 500);
      return responseFor(config);
    };
    const request = api.get('/status');
    await vi.runAllTimersAsync();
    await expect(request).resolves.toMatchObject({ status: 200 });
    expect(calls).toBe(2);
  });

  it('treats explicit cancellation as cancellation, not offline mode', async () => {
    api.defaults.adapter = async config => responseFor(config);
    await api.get('/status');
    const abort = new AbortController();
    abort.abort();
    const error = await api.get('/status', { signal: abort.signal }).catch(value => value);
    expect(error.code).toBe('ERR_CANCELED');
    expect(getRequestQueueStatus().isOnline).toBe(true);
  });
});
