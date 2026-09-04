import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import MediaPanel from '../components/chat/MediaPanel';
import StewardPanel from '../components/status/StewardPanel';
import { api } from '../services/api';
import vercelConfig from '../../vercel.json';

vi.mock('../services/api', () => ({ api: { get: vi.fn(), post: vi.fn() } }));

function show(component) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  return render(<QueryClientProvider client={client}>{component}</QueryClientProvider>);
}

beforeEach(() => { vi.clearAllMocks(); });

describe('media and stewardship controls', () => {
  it('allows only local and generated-blob audio through the deployment CSP', () => {
    const source = vercelConfig.headers.flatMap(item => item.headers)
      .find(header => header.key === 'Content-Security-Policy')?.value;
    expect(source).toContain("media-src 'self' blob:");
  });
  it('does not upload on file selection and requires a ready capability', async () => {
    api.get.mockResolvedValue({ data: { capabilities: { vision: { ready: false } } } });
    show(<MediaPanel onUseText={vi.fn()} />);
    fireEvent.click(screen.getByText('Audio & vision'));
    fireEvent.change(screen.getByLabelText('Image or audio file'), {
      target: { files: [new File(['image'], 'sample.png', { type: 'image/png' })] },
    });
    expect(screen.getByRole('button', { name: 'Analyze / transcribe' })).toBeDisabled();
    expect(api.post).not.toHaveBeenCalled();
  });

  it('requires review before extracted text becomes a chat message', async () => {
    api.get.mockResolvedValue({ data: { capabilities: { vision: { ready: true } } } });
    api.post.mockResolvedValue({ data: { text: 'Unverified image description' } });
    const send = vi.fn(); show(<MediaPanel onUseText={send} />);
    fireEvent.click(screen.getByText('Audio & vision'));
    fireEvent.change(screen.getByLabelText('Image or audio file'), {
      target: { files: [new File(['image'], 'sample.png', { type: 'image/png' })] },
    });
    await waitFor(() => expect(screen.getByRole('button', { name: 'Analyze / transcribe' })).toBeEnabled());
    fireEvent.click(screen.getByRole('button', { name: 'Analyze / transcribe' }));
    expect(await screen.findByDisplayValue('Unverified image description')).toBeInTheDocument();
    expect(send).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'Send reviewed text to chat' }));
    expect(send).toHaveBeenCalledWith('[Unverified media extraction]\nUnverified image description');
    expect(api.post.mock.calls[0][2]).toMatchObject({ noRetry: true });
  });

  it('reports missing connector configuration rather than readiness', async () => {
    api.get.mockImplementation(path => Promise.resolve({ data: path === '/connectors/status'
      ? { enabled: true, ready: false } : { runtime: {}, dreams: { enabled: false }, improvement: {} } }));
    show(<StewardPanel />);
    expect(await screen.findByText(/enabled but not configured/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Request one dream cycle' })).toBeDisabled();
    expect(api.post).not.toHaveBeenCalled();
  });

  it('makes a non-retrying asynchronous dream request', async () => {
    api.get.mockResolvedValue({ data: { runtime: { busy: false }, dreams: { enabled: true }, improvement: {} } });
    api.post.mockResolvedValue({ data: { job_id: 'test-job', status: 'queued' } });
    show(<StewardPanel />);
    fireEvent.click(await screen.findByRole('button', { name: 'Request one dream cycle' }));
    await screen.findByText(/Dream request accepted: test-job/);
    expect(api.post).toHaveBeenCalledWith('/steward/dream', {}, { noRetry: true });
  });
});
