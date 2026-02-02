import Card from '../components/common/Card';
import Badge from '../components/common/Badge';
import Button from '../components/common/Button';
import Spinner from '../components/common/Spinner';
import {
  useGitHubStatus,
  useGitHubRepository,
  useGitHubPullRequests,
  useGitHubCommits,
  useTriggerImprovement,
} from '../hooks/useGitHub';
import { formatRelativeTime } from '../utils/formatting';

const GitHubPage = () => {
  const { data: status, isLoading: statusLoading } = useGitHubStatus();
  const { data: repository, isLoading: repoLoading } = useGitHubRepository();
  const { data: pullRequests, isLoading: prsLoading } = useGitHubPullRequests();
  const { data: commits, isLoading: commitsLoading } = useGitHubCommits();
  const { mutate: triggerImprovement, isPending: triggeringImprovement } = useTriggerImprovement();

  return (
    <div className="max-w-7xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">GitHub Integration</h1>
        <p className="text-gray-600 mt-1">Monitor pull requests, commits, and improvements</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
        <Card title="Connection Status">
          {statusLoading ? (
            <Spinner size="sm" />
          ) : status ? (
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-gray-600">Status</span>
                <Badge variant={status.connected ? 'success' : 'danger'}>
                  {status.connected ? 'Connected' : 'Disconnected'}
                </Badge>
              </div>
              {status.repository && (
                <div className="flex items-center justify-between">
                  <span className="text-gray-600">Repository</span>
                  <span className="text-gray-900 font-medium">{status.repository}</span>
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

      <Card
        title="Actions"
        className="mb-6"
        action={
          <Button
            onClick={() => triggerImprovement({})}
            disabled={triggeringImprovement}
            size="sm"
          >
            {triggeringImprovement ? 'Triggering...' : 'Trigger Improvement'}
          </Button>
        }
      >
        <p className="text-gray-600">
          Click the button above to analyze the codebase and create improvement pull requests.
        </p>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card title="Recent Pull Requests">
          {prsLoading ? (
            <Spinner size="sm" />
          ) : pullRequests && pullRequests.length > 0 ? (
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
          ) : commits && commits.length > 0 ? (
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
