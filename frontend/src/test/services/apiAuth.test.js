import { afterEach, describe, expect, it, vi } from 'vitest';

vi.mock('react-hot-toast', () => ({
  default: Object.assign(vi.fn(), { error: vi.fn(), success: vi.fn() }),
}));

import {
  api,
  clearProjectApiKey,
  setProjectApiKey,
} from '../../services/api';

const responseFor = (config) => ({
  data: {},
  status: 200,
  statusText: 'OK',
  headers: {},
  config,
});

afterEach(() => {
  clearProjectApiKey();
});

describe('project credential transport', () => {
  it('adds the in-memory project credential and removes it after logout', async () => {
    const observed = [];
    api.defaults.adapter = async (config) => {
      observed.push(config.headers.get('X-API-Key'));
      return responseFor(config);
    };

    setProjectApiKey('memory-only-key');
    await api.get('/status');
    clearProjectApiKey();
    await api.get('/status');

    expect(observed).toEqual(['memory-only-key', undefined]);
  });

  it('does not overwrite a credential supplied for an explicit validation request', async () => {
    let observed;
    api.defaults.adapter = async (config) => {
      observed = config.headers.get('X-API-Key');
      return responseFor(config);
    };

    setProjectApiKey('old-key');
    await api.get('/status', { headers: { 'X-API-Key': 'candidate-key' } });

    expect(observed).toBe('candidate-key');
  });
});
