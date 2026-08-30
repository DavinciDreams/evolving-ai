import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../../services/api';
import Card from '../common/Card';
import Button from '../common/Button';

export default function StewardPanel() {
  const cache = useQueryClient();
  const [pending, setPending] = useState(false);
  const [notice, setNotice] = useState('');
  const { data, error, isLoading } = useQuery({ queryKey: ['steward-status'],
    queryFn: () => api.get('/steward/status').then(r => r.data), refetchInterval: 10000, retry: false });
  const { data: connectors } = useQuery({ queryKey: ['connector-status'],
    queryFn: () => api.get('/connectors/status').then(r => r.data), refetchInterval: 30000, retry: false });
  const dream = async () => {
    setPending(true); setNotice('');
    try {
      const response = await api.post('/steward/dream', {}, { noRetry: true });
      setNotice(`Dream request accepted: ${response.data.job_id}. Check its job outcome below.`);
      cache.invalidateQueries({ queryKey: ['steward-status'] });
    } catch { setNotice('Dream not accepted. Check idle state and deployment configuration before retrying.'); }
    finally { setPending(false); }
  };
  return <Card title="Katbot steward">
    {isLoading && <p role="status">Loading runtime telemetry…</p>}
    {error && <p role="alert">Steward status unavailable. This runtime may still be on the older baseline.</p>}
    {data && <div className="space-y-4">
      <dl className="grid grid-cols-2 gap-2 text-sm">
        <dt>Runtime</dt><dd>{data.runtime?.busy ? 'Busy — no reentry' : 'Idle'}</dd>
        <dt>Response deadline</dt><dd>{data.runtime?.timeout_seconds} seconds</dd>
        <dt>Timeouts / failures</dt><dd>{data.runtime?.timeouts} / {data.runtime?.failed}</dd>
        <dt>Dreams</dt><dd>{data.dreams?.enabled ? (data.dreams.running ? 'Consolidating' : 'Enabled, idle-gated') : 'Disabled'}</dd>
        <dt>Last dream</dt><dd>{data.dreams?.last_result?.reason || 'No attempt yet'}</dd>
        <dt>Measured adaptation</dt><dd>{data.improvement?.enabled ? `Revision ${data.improvement.revision}` : 'Disabled'}</dd>
        <dt>Idle experiments</dt><dd>{data.learning?.enabled ? (data.learning.running ? 'Evaluating a bounded candidate' : 'Enabled, idle-gated') : 'Disabled'}</dd>
      </dl>
      <p className="text-sm text-gray-700">Dreams preserve original memories and label hypotheses. Candidate strategies need measured holdout evidence before activation. No automatic code deployment.</p>
      <Button size="sm" onClick={dream} disabled={pending || !data.dreams?.enabled || data.runtime?.busy || data.dreams?.running || data.learning?.running || data.improvement?.busy}>Request one dream cycle</Button>
      <p role="status" aria-live="polite" className="break-words text-sm">{notice}</p>
      {data.jobs?.length > 0 && <ul className="space-y-1 text-sm" aria-label="Recent steward jobs">
        {data.jobs.slice(-5).reverse().map(job => <li key={job.job_id}><span className="font-medium">{job.kind}</span>: {job.status} <code className="text-xs">{job.job_id.slice(0, 8)}</code></li>)}
      </ul>}
      <p className="text-sm text-gray-700">Connectors: {connectors?.ready ? 'ready; signed events require explicit handling' : connectors?.enabled ? 'enabled but not configured' : 'disabled or unavailable'}. Plugin code is never loaded from webhook content.</p>
    </div>}
  </Card>;
}
