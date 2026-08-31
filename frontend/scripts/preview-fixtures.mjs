/** Loopback-only UI fixtures. Never imports backend code or calls external services. */
import { createServer } from 'node:http';

const jobs = {};
const report = { kind: 'evaluation', run_id: 'synthetic-run', status: 'staged', eligible: true,
  baseline_revision: 0, memory_id: 'synthetic-evidence-not-in-HAM', calls: 8, reasons: [],
  scores: { development: { baseline: 0.5, candidate: 1 }, holdout: { baseline: 0.5, candidate: 1 } } };
const lab = { enabled: true, revision: 0, busy: false, rollback_depth: 0,
  staged_runs: ['synthetic-run'], state_memory_id: null };
const data = {
  '/status': { is_initialized: true, session_id: 'SYNTHETIC-PREVIEW', total_interactions: 0,
    memory_count: 0, knowledge_count: 0, uptime: 'UI fixture only' },
  '/health': { status: 'healthy', agent_initialized: true, github_available: false },
  '/github/status': { github_connected: false, auto_pr_enabled: false },
  '/discord/status': { enabled: false, connected: false },
  '/connectors/status': { enabled: false, ready: false },
  '/media/status': { capabilities: { vision: { ready: false }, transcription: { ready: false }, speech: { ready: false } } },
};
createServer(async (request, response) => {
  response.setHeader('Access-Control-Allow-Origin', 'http://127.0.0.1:5179');
  response.setHeader('Access-Control-Allow-Headers', 'Content-Type, X-API-Key');
  response.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  response.setHeader('Cache-Control', 'no-store');
  response.setHeader('Content-Type', 'application/json');
  if (request.method === 'OPTIONS') { response.writeHead(204); response.end(); return; }
  const send = (status, value) => { response.writeHead(status); response.end(JSON.stringify(value)); };
  if (request.headers['x-api-key'] !== 'synthetic-local-preview') return send(401, { detail: 'Synthetic preview credential required' });
  const path = new URL(request.url, 'http://127.0.0.1:8079').pathname;
  if (request.method === 'GET') {
    if (path === '/steward/status') return send(200, { runtime: { busy: false, timeout_seconds: 60, timeouts: 0, failed: 0 },
      dreams: { enabled: true, running: false, last_result: { reason: 'Synthetic UI fixture' } }, improvement: lab,
      learning: { enabled: true, auto_promote: false, running: false }, jobs: Object.values(jobs) });
    if (path.startsWith('/steward/jobs/')) return send(200, jobs[path.split('/').at(-1)] || { status: 'failed' });
    if (path.startsWith('/steward/improvement/runs/')) return send(200, report);
    return send(200, data[path] || {});
  }
  let body = '';
  for await (const chunk of request) {
    body += chunk;
    if (body.length > 524288) return send(413, { detail: 'Fixture request too large' });
  }
  let payload;
  try { payload = body ? JSON.parse(body) : {}; } catch { return send(422, { detail: 'Invalid JSON' }); }
  if (path === '/chat') return send(200, { response: 'Synthetic preview response. No model was called and no memory was stored.',
    evaluation_score: null, memory_stored: false, knowledge_updated: false });
  if (path === '/steward/improvement/promote') {
    if (payload.expected_revision !== lab.revision) return send(409, { detail: 'Synthetic revision conflict' });
    lab.revision += 1; lab.rollback_depth = 1; lab.state_memory_id = 'synthetic-state-not-in-HAM';
  } else if (path === '/steward/improvement/rollback') {
    lab.revision += 1; lab.rollback_depth = 0;
  }
  if (path.startsWith('/steward/')) {
    const job_id = `synthetic-job-${Object.keys(jobs).length + 1}`;
    jobs[job_id] = { job_id, kind: path.endsWith('/dream') ? 'dream' : 'improvement', status: 'completed',
      result: path.endsWith('/evaluate') ? report : { kind: 'state', revision: lab.revision, reason: 'Synthetic only' } };
    return send(202, { job_id, status: 'queued' });
  }
  return send(404, { detail: 'No synthetic fixture for this route' });
}).listen(8079, '127.0.0.1', () => {
  console.info('Synthetic UI fixture API: http://127.0.0.1:8079 (no external services)');
});
