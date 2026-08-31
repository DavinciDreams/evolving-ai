import { useEffect, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../../services/api';
import Card from '../common/Card';
import Button from '../common/Button';

const inputClass = 'block w-full rounded-md border-gray-300 text-sm focus:border-indigo-500 focus:ring-indigo-500';
const terminal = ['completed', 'failed', 'cancelled'];
const percentage = value => typeof value === 'number' && Number.isFinite(value) ? `${Math.round(value * 100)}%` : 'Not measured';

export default function LearningLabPanel() {
  const cache = useQueryClient();
  const [fixtureText, setFixtureText] = useState('');
  const [format, setFormat] = useState('plain');
  const [words, setWords] = useState(500);
  const [flags, setFlags] = useState({ separate_evidence: true, acknowledge_uncertainty: true, verify_calculations: false });
  const [reason, setReason] = useState('');
  const [pending, setPending] = useState(false);
  const [notice, setNotice] = useState('');
  const [jobId, setJobId] = useState('');
  const [runId, setRunId] = useState('');
  const { data: state } = useQuery({ queryKey: ['steward-status'],
    queryFn: ({ signal }) => api.get('/steward/status', { signal }).then(r => r.data), refetchInterval: 10000, retry: false });
  const { data: job, error: jobError } = useQuery({ queryKey: ['steward-job', jobId], enabled: Boolean(jobId),
    queryFn: ({ signal }) => api.get(`/steward/jobs/${encodeURIComponent(jobId)}`, { signal, noRetry: true }).then(r => r.data),
    refetchInterval: query => terminal.includes(query.state.data?.status) || query.state.error ? false : 1500, retry: false });
  const { data: selectedReport, error: reportError } = useQuery({ queryKey: ['improvement-report', runId], enabled: Boolean(runId),
    queryFn: ({ signal }) => api.get(`/steward/improvement/runs/${encodeURIComponent(runId)}`, { signal, noRetry: true }).then(r => r.data), retry: false });
  useEffect(() => {
    if (terminal.includes(job?.status)) {
      cache.invalidateQueries({ queryKey: ['steward-status'] });
      cache.invalidateQueries({ queryKey: ['improvement-report'] });
    }
  }, [jobId, job?.status, cache]);
  const report = runId ? selectedReport : (job?.result?.kind === 'evaluation' ? job.result : null);
  const lab = state?.improvement;
  const busy = pending || state?.runtime?.busy || state?.dreams?.running || state?.learning?.running || lab?.busy ||
    (jobId && !jobError && (!job || !terminal.includes(job.status)));

  const submit = async (path, payload) => {
    if (pending) return;
    setPending(true); setNotice('');
    try {
      const { data } = await api.post(path, payload, { noRetry: true });
      setJobId(data.job_id);
      setNotice('Request accepted, not yet completed. Follow the job outcome below.');
      cache.invalidateQueries({ queryKey: ['steward-status'] });
    } catch { setNotice('Request was not confirmed. Check runtime status before explicitly retrying; no automatic replay occurred.'); }
    finally { setPending(false); }
  };
  const evaluate = event => {
    event.preventDefault();
    let cases;
    try {
      if (fixtureText.length > 500000) throw new Error();
      const suite = JSON.parse(fixtureText);
      cases = Array.isArray(suite) ? suite : suite.cases;
      if (!Array.isArray(cases) || cases.length < 4 || cases.length > 24) throw new Error();
    } catch { setNotice('Enter valid JSON with 4–24 benchmark cases. Nothing was submitted.'); return; }
    const id = crypto.randomUUID();
    setRunId('');
    submit('/steward/improvement/evaluate', { candidate_id: `operator-${id}`, run_id: `run-${id}`,
      strategy: { response_format: format, max_response_words: Number(words), ...flags }, cases });
  };
  const activate = () => submit('/steward/improvement/promote', { run_id: report.run_id, expected_revision: report.baseline_revision });
  const rollback = event => {
    event.preventDefault();
    submit('/steward/improvement/rollback', { expected_revision: lab.revision, reason: reason.trim() });
  };

  return <Card title="Measured learning lab">
    <div className="space-y-4 text-sm">
      <p>Test bounded response preferences against your trusted exact-answer fixtures. No generated code, tool execution, or weight updates. Tests consume provider credits and store redacted evidence in HAM.</p>
      <p>Idle experiments: {state?.learning?.enabled ? (state.learning.auto_promote ? 'Enabled with automatic promotion' : 'Enabled; stage for review') : 'Disabled'}. Active revision: {lab?.revision ?? 'unavailable'}.</p>
      {!lab?.enabled && <p role="status">The operator must configure HAM and enable the improvement lab before use.</p>}
      <details>
        <summary className="cursor-pointer font-medium focus-visible:outline focus-visible:outline-indigo-600">Create a measured candidate</summary>
        <form onSubmit={evaluate} className="mt-3 space-y-3">
          <fieldset disabled={!lab?.enabled || busy} className="space-y-3 disabled:opacity-60">
            <legend className="font-medium">Candidate preferences</legend>
            <label className="block">Preferred format<select className={inputClass} value={format} onChange={e => setFormat(e.target.value)}><option value="plain">Plain text</option><option value="json">JSON when compatible</option></select></label>
            <label className="block">Maximum response words<input type="number" min="1" max="2000" required value={words} onChange={e => setWords(e.target.value)} className={inputClass} /></label>
            {Object.entries({ separate_evidence: 'Separate evidence from inference', acknowledge_uncertainty: 'Acknowledge material uncertainty', verify_calculations: 'Verify arithmetic and units' }).map(([key, label]) =>
              <label key={key} className="flex items-center gap-2"><input type="checkbox" checked={flags[key]} onChange={e => setFlags(previous => ({ ...previous, [key]: e.target.checked }))} />{label}</label>)}
            <label className="block">Trusted benchmark JSON<textarea required rows={7} maxLength={500000} value={fixtureText} onChange={e => setFixtureText(e.target.value)} aria-describedby="benchmark-help" className={`${inputClass} font-mono`} /></label>
            <p id="benchmark-help">Use a cases array: case_id, prompt, expected, split (development or holdout), and critical (boolean). At least two distinct cases per split, including a critical safety/regression case. Expected answers are withheld from the model. Do not paste credentials. Repeated holdout reuse is not independent validation.</p>
            <Button type="submit" size="sm">Evaluate candidate — uses provider credits</Button>
          </fieldset>
        </form>
      </details>
      <label className="block">Inspect recent experiment<select className={inputClass} value={runId} onChange={e => setRunId(e.target.value)}><option value="">Most recent requested job</option>{lab?.staged_runs?.map(id => <option key={id} value={id}>{id}</option>)}</select></label>
      <p role="status" aria-live="polite">{notice}</p>
      {jobId && <p>Job <code className="break-all">{jobId}</code>: {job?.status || (jobError ? 'unavailable; inspect HAM before retrying' : 'checking')}.</p>}
      {reportError && <p role="alert">Report unavailable or expired. Retrieve its durable HAM artifact before acting.</p>}
      {report && <section aria-label="Experiment evidence" className="space-y-2 rounded-lg border border-gray-200 p-3">
        <p className="font-medium">{report.baseline_revision !== lab?.revision ? 'Earlier revision — evaluate again before activation' : report.status === 'staged' && report.eligible ? 'Eligible for explicit activation' : 'Not eligible for activation'}</p>
        <p>Run: <code className="break-all">{report.run_id}</code></p>
        {report.scores && <table className="w-full text-left"><caption className="text-left">Exact-match fixture pass rates; not general intelligence scores</caption><thead><tr><th scope="col">Split</th><th scope="col">Baseline</th><th scope="col">Candidate</th></tr></thead><tbody>{['development', 'holdout'].map(split => <tr key={split}><th scope="row">{split}</th><td>{percentage(report.scores[split]?.baseline)}</td><td>{percentage(report.scores[split]?.candidate)}</td></tr>)}</tbody></table>}
        {!report.memory_id && <p role="alert">Durable evidence is not yet confirmed. Activation will require a successful HAM write before changing guidance.</p>}
        <p>HAM evidence ID: <code>{report.memory_id || 'not confirmed'}</code>. Provider calls: {report.calls ?? 'unknown'}.</p>
        {report.reasons?.length > 0 && <ul className="list-inside list-disc">{report.reasons.map(item => <li key={item}>{item.replaceAll('_', ' ')}</li>)}</ul>}
        <p>Activation changes future response guidance only. No claim of generalization beyond this suite.</p>
        <Button size="sm" disabled={!lab?.enabled || busy || !report.eligible || report.status !== 'staged' || report.baseline_revision !== lab.revision} onClick={activate}>Activate measured candidate</Button>
      </section>}
      <form onSubmit={rollback} className="space-y-2 border-t border-gray-200 pt-3">
        <label className="block">Rollback reason<input maxLength={500} required value={reason} onChange={e => setReason(e.target.value)} className={inputClass} /></label>
        <Button type="submit" variant="outline" size="sm" disabled={!lab?.enabled || busy || !lab.rollback_depth || !reason.trim()}>Restore previous guidance</Button>
        {lab?.state_memory_id && <p>Latest state HAM ID: <code>{lab.state_memory_id}</code>. Pin this exact ID when restarting the single-worker service.</p>}
      </form>
    </div>
  </Card>;
}
