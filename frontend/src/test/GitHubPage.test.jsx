import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import GitHubPage from '../pages/GitHubPage';
import * as github from '../hooks/useGitHub';

vi.mock('../hooks/useGitHub', () => ({
  useGitHubStatus: vi.fn(),
  useGitHubRepository: vi.fn(),
  useGitHubPullRequests: vi.fn(),
  useGitHubCommits: vi.fn(),
  useTriggerImprovement: vi.fn(() => { throw new Error('Retired mutation must not be mounted'); }),
}));

const display = () => render(<MemoryRouter><GitHubPage /></MemoryRouter>);

beforeEach(() => {
  vi.clearAllMocks();
  github.useGitHubStatus.mockReturnValue({ data: { github_connected: false } });
  github.useGitHubRepository.mockReturnValue({ data: undefined });
  github.useGitHubPullRequests.mockReturnValue({ data: { open_pull_requests: [], count: 0 } });
  github.useGitHubCommits.mockReturnValue({ data: { recent_commits: [], count: 0 } });
});

describe('read-only GitHub page', () => {
  it('explains the authority boundary without mounting retired mutation controls', () => {
    display();
    expect(screen.getByText('Read-only integration')).toBeInTheDocument();
    expect(screen.getByText(/Publishing changes requires a separately authorized workflow/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'measured steward controls' })).toHaveAttribute('href', '/status');
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
    expect(github.useTriggerImprovement).not.toHaveBeenCalled();
  });

  it('renders the real backend response envelopes instead of claiming no activity', () => {
    github.useGitHubPullRequests.mockReturnValue({ data: { open_pull_requests: [{ number: 59, title: 'Memory cutover', state: 'open', created_at: '2026-08-30T12:00:00Z' }], count: 1 } });
    github.useGitHubCommits.mockReturnValue({ data: { recent_commits: [{ sha: 'abc123', message: 'Bound steward jobs', author: 'Operator', date: '2026-08-30T12:00:00Z' }], count: 1 } });
    display();
    expect(screen.getByText('Memory cutover')).toBeInTheDocument();
    expect(screen.getByText('Bound steward jobs')).toBeInTheDocument();
    expect(screen.queryByText(/No .* found/)).not.toBeInTheDocument();
  });

  it('distinguishes failed collection from empty activity and never renders raw error detail', () => {
    const failure = { isError: true, error: new Error('private-provider-detail') };
    github.useGitHubStatus.mockReturnValue(failure);
    github.useGitHubRepository.mockReturnValue(failure);
    github.useGitHubPullRequests.mockReturnValue(failure);
    github.useGitHubCommits.mockReturnValue(failure);
    display();
    expect(screen.getAllByRole('status')).toHaveLength(4);
    expect(screen.queryByText(/No .* found/)).not.toBeInTheDocument();
    expect(screen.queryByText(/private-provider-detail/)).not.toBeInTheDocument();
  });

  it('reports empty results only after successful valid collection', () => {
    display();
    expect(screen.getByText('No pull requests found')).toBeInTheDocument();
    expect(screen.getByText('No commits found')).toBeInTheDocument();
  });
});
