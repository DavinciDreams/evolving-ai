import { afterEach, describe, expect, it, vi } from 'vitest';

vi.mock('react-hot-toast', () => ({
  default: Object.assign(vi.fn(), { error: vi.fn(), success: vi.fn() }),
}));

import {
  api,
  authenticateWithNostr,
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

  it('uses a NIP-07 signer and sends only public proof material', async () => {
    const pubkey = 'a'.repeat(64);
    const signedEvent = {
      id: 'b'.repeat(64),
      sig: 'c'.repeat(128),
      pubkey,
      created_at: 123,
      kind: 27235,
      tags: [],
      content: '',
    };
    const signEvent = vi.fn().mockResolvedValue(signedEvent);
    window.nostr = {
      getPublicKey: vi.fn().mockResolvedValue(pubkey),
      signEvent,
    };
    const observed = [];
    api.defaults.adapter = async (config) => {
      observed.push({ url: config.url, data: JSON.parse(config.data) });
      if (config.url.endsWith('/options')) {
        return {
          ...responseFor(config),
          data: { challenge: 'd'.repeat(43), verify_url: 'https://api.example/auth/nostr/verify' },
        };
      }
      return { ...responseFor(config), data: { signed_in: true } };
    };

    await authenticateWithNostr();

    expect(signEvent).toHaveBeenCalledWith(expect.objectContaining({
      pubkey,
      kind: 27235,
      content: '',
      tags: expect.arrayContaining([['challenge', 'd'.repeat(43)]]),
    }));
    expect(observed[1]).toEqual({
      url: '/auth/nostr/verify',
      data: { challenge: 'd'.repeat(43), event: signedEvent },
    });
    expect(JSON.stringify(observed)).not.toMatch(/nsec|private/i);
    delete window.nostr;
  });
});
