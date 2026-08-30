import Card from '../components/common/Card';
import Badge from '../components/common/Badge';
import { Link } from 'react-router-dom';
import Spinner from '../components/common/Spinner';
import {
  useGitHubStatus,
  useGitHubRepository,
  useGitHubPullRequests,
  useGitHubCommits,
} from '../hooks/useGitHub';
import { formatRelativeTime } from '../utils/formatting';

const GitHubPage = () => {
  const { data: status, isLoading: statusLoading, isError: statusError } = useGitHubStatus();
  const { data: repository, isLoading: repoLoading, isError: repoError } = useGitHubRepository();
  const { data: prData, isLoading: prsLoading, isError: prsError } = useGitHubPullRequests();
  const { data: commitData, isLoading: commitsLoading, isError: commitsError } = useGitHubCommits();
  const pullRequests = Array.isArray(prData) ? prData : prData?.open_pull_requests;
  const commits = Array.isArray(commitData) ? commitData : commitData?.recent_commits;

  return (
    <div className="max-w-7xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">GitHub Integration</h1>
        <p className="text-gray-600 mt-1">Read-only repository status, pull requests, and commits</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
        <Card title="Connection Status">
          {statusLoading ? (
            <Spinner size="sm" />
          ) : statusError ? (
            <p role="status" className="text-gray-600">Connection status unavailable. Check authentication and service status.</p>
          ) : status ? (
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-gray-600">Status</span>
                <Badge variant={status.github_connected ? 'success' : 'danger'}>
                  {status.github_connected ? 'Connected' : 'Disconnected'}
                </Badge>
              </div>
              {status.repository_name && (
                <div className="flex items-center justify-between">
                  <span className="text-gray-600">Repository</span>
                  <span className="text-gray-900 font-medium">{status.repository_name}</span>
                </div>
              )}
            </div>
          ) : (
            <p className="text-gray-500">No status available</p>
          )}
        </Card>

        <Card title="Repository Info">
          {repoLoading ? (
            <Spinner size="sm" />
          ) : repoError ? (
            <p role="status" className="text-gray-600">Repository information unavailable. A failed read does not indicate an empty repository.</p>
          ) : repository ? (
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-gray-600">Stars</span>
                <span className="text-gray-900 font-medium">{repository.stars || 0}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-gray-600">Forks</span>
                <span className="text-gray-900 font-medium">{repository.forks || 0}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-gray-600">Language</span>
                <span className="text-gray-900 font-medium">{repository.language || 'N/A'}</span>
              </div>
            </div>
          ) : (
            <p className="text-gray-500">No repository info available</p>
          )}
        </Card>
      </div>

      <Card title="Read-only integration" className="mb-6">
        <p className="text-gray-600">
          Legacy code modification, demo pull requests, and direct issue publication are retired.
          This page does not change your repository. Publishing changes requires a separately authorized workflow.
        </p>
        <p className="text-gray-600 mt-3">
          The <Link to="/status" className="text-blue-700 underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2">measured steward controls</Link> evaluate
          bounded response strategies with explicit promotion and rollback; they do not publish code or train model weights.
        </p>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card title="Recent Pull Requests">
          {prsLoading ? (
            <Spinner size="sm" />
          ) : prsError || !Array.isArray(pullRequests) ? (
            <p role="status" className="text-gray-600">Pull request history unavailable. No conclusion about repository activity can be drawn.</p>
          ) : pullRequests.length > 0 ? (
            <div className="space-y-3">
              {pullRequests.map((pr, index) => (
                <div key={index} className="border-b border-gray-200 pb-3 last:border-0">
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <p className="font-medium text-gray-900">{pr.title}</p>
                      <p className="text-sm text-gray-500 mt-1">
                        #{pr.number} • {formatRelativeTime(pr.created_at)}
                      </p>
                    </div>
                    <Badge variant={pr.state === 'open' ? 'success' : 'secondary'}>
                      {pr.state}
                    </Badge>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-gray-500">No pull requests found</p>
          )}
        </Card>

        <Card title="Recent Commits">
          {commitsLoading ? (
            <Spinner size="sm" />
          ) : commitsError || !Array.isArray(commits) ? (
            <p role="status" className="text-gray-600">Commit history unavailable. No conclusion about repository activity can be drawn.</p>
          ) : commits.length > 0 ? (
            <div className="space-y-3">
              {commits.map((commit, index) => (
                <div key={index} className="border-b border-gray-200 pb-3 last:border-0">
                  <p className="font-medium text-gray-900 text-sm">{commit.message}</p>
                  <p className="text-xs text-gray-500 mt-1">
                    {commit.author} • {formatRelativeTime(commit.date)}
                  </p>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-gray-500">No commits found</p>
          )}
        </Card>
      </div>
    </div>
  );
};

export default GitHubPage;
