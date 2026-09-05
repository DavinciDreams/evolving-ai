import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import LearningLabPanel from '../components/status/LearningLabPanel';
import { api } from '../services/api';

vi.mock('../services/api', () => ({ api: { get: vi.fn(), post: vi.fn() } }));
const fixtures = ['dev1', 'dev2', 'hold1', 'hold2'].map((id, index) => ({ case_id: id,
  prompt: `Unique question ${index}`, expected: `${index}`, split: index < 2 ? 'development' : 'holdout', critical: index === 3 }));
let state;
let report;
function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  return render(<QueryClientProvider client={client}><LearningLabPanel /></QueryClientProvider>);
}
beforeEach(() => {
  vi.clearAllMocks();
  state = { runtime: { busy: false }, dreams: {}, learning: { enabled: false }, improvement: {
    enabled: true, busy: false, revision: 2, rollback_depth: 1, staged_runs: ['run-1'], state_memory_id: '777' } };
  report = { kind: 'evaluation', status: 'staged', eligible: true, baseline_revision: 2,
    run_id: 'run-1', memory_id: '778', calls: 8,
    scores: { development: { baseline: 0.5, candidate: 1 }, holdout: { baseline: 0.5, candidate: 1 } }, reasons: [] };
  api.get.mockImplementation(path => Promise.resolve({ data: path === '/steward/status' ? state :
    path.includes('/jobs/') ? { status: 'completed', result: report } : report }));
  api.post.mockResolvedValue({ data: { job_id: 'job-1', status: 'queued' } });
});

describe('measured learning operator controls', () => {
  it('never submits without explicit action or while disabled', async () => {
    state.improvement.enabled = false;
    show();
    await screen.findByText(/must configure HAM/);
    fireEvent.click(screen.getByText('Create a measured candidate'));
    expect(screen.getByRole('button', { name: /Evaluate candidate/ })).toBeDisabled();
    expect(api.post).not.toHaveBeenCalled();
  });
  it('rejects invalid fixtures locally', async () => {
    show();
    fireEvent.click(screen.getByText('Create a measured candidate'));
    await waitFor(() => expect(screen.getByRole('button', { name: /Evaluate candidate/ })).toBeEnabled());
    fireEvent.change(screen.getByLabelText('Trusted benchmark JSON'), { target: { value: 'not-json' } });
    fireEvent.click(screen.getByRole('button', { name: /Evaluate candidate/ }));
    await screen.findByText(/Nothing was submitted/);
    expect(api.post).not.toHaveBeenCalled();
  });
  it('queues a bounded candidate without replay or implicit activation', async () => {
    show();
    fireEvent.click(screen.getByText('Create a measured candidate'));
    await waitFor(() => expect(screen.getByRole('button', { name: /Evaluate candidate/ })).toBeEnabled());
    fireEvent.change(screen.getByLabelText('Trusted benchmark JSON'), { target: { value: JSON.stringify({ cases: fixtures }) } });
    fireEvent.click(screen.getByRole('button', { name: /Evaluate candidate/ }));
    await screen.findByText('Eligible for explicit activation');
    expect(screen.getByText(/Job completed\. Inspect the outcome/)).toBeInTheDocument();
    expect(screen.queryByText(/Request accepted, not yet completed/)).not.toBeInTheDocument();
    expect(api.post).toHaveBeenCalledTimes(1);
    expect(api.post.mock.calls[0]).toEqual(['/steward/improvement/evaluate', expect.objectContaining({ cases: fixtures,
      strategy: expect.objectContaining({ response_format: 'plain', separate_evidence: true }) }), { noRetry: true }]);
  });
  it('uses the evaluated revision for explicit promotion', async () => {
    show();
    await waitFor(() => expect(screen.getByRole('option', { name: 'run-1' })).toBeInTheDocument());
    fireEvent.change(screen.getByLabelText('Inspect recent experiment'), { target: { value: 'run-1' } });
    fireEvent.click(await screen.findByRole('button', { name: 'Activate measured candidate' }));
    await screen.findByText(/Job completed\. Inspect the outcome/);
    expect(api.post).toHaveBeenCalledWith('/steward/improvement/promote', { run_id: 'run-1', expected_revision: 2 }, { noRetry: true });
  });
  it('disables promotion for stale evidence', async () => {
    report.baseline_revision = 1;
    show();
    await screen.findByRole('option', { name: 'run-1' });
    fireEvent.change(screen.getByLabelText('Inspect recent experiment'), { target: { value: 'run-1' } });
    expect(await screen.findByRole('button', { name: 'Activate measured candidate' })).toBeDisabled();
  });
  it('requires a reason and explicit action for rollback', async () => {
    show();
    expect(screen.getByRole('button', { name: 'Restore previous guidance' })).toBeDisabled();
    await screen.findByText(/Latest state HAM ID/);
    fireEvent.change(screen.getByLabelText('Rollback reason'), { target: { value: 'Observed a regression' } });
    fireEvent.click(screen.getByRole('button', { name: 'Restore previous guidance' }));
    await screen.findByText(/Job completed\. Inspect the outcome/);
    expect(api.post).toHaveBeenCalledWith('/steward/improvement/rollback', { expected_revision: 2, reason: 'Observed a regression' }, { noRetry: true });
  });
});
