import { useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../services/api';
import Button from '../common/Button';

const imageTypes = ['image/png', 'image/jpeg', 'image/webp'];
const audioTypes = ['audio/wav', 'audio/mpeg', 'audio/webm', 'audio/ogg', 'audio/flac', 'audio/mp4'];
const extractionPrefix = '[Unverified media extraction]\n';
const readBase64 = (file) => new Promise((resolve, reject) => {
  const reader = new FileReader();
  reader.onload = () => resolve(String(reader.result).split(',')[1]);
  reader.onerror = () => reject(new Error('Could not read this file.'));
  reader.readAsDataURL(file);
});

export default function MediaPanel({ onUseText, latestResponse = '', disabled = false }) {
  const { data: status } = useQuery({ queryKey: ['media-status'],
    queryFn: () => api.get('/media/status').then(r => r.data), retry: false, staleTime: 60000 });
  const [file, setFile] = useState(null);
  const [prompt, setPrompt] = useState('Describe this image.');
  const [result, setResult] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [audioUrl, setAudioUrl] = useState('');
  const urlRef = useRef('');
  const mounted = useRef(true);
  const abortRef = useRef(null);
  useEffect(() => { mounted.current = true; return () => {
    mounted.current = false;
    abortRef.current?.abort();
    if (urlRef.current) URL.revokeObjectURL(urlRef.current);
  }; }, []);
  const isImage = file && imageTypes.includes(file.type);
  const capability = isImage ? 'vision' : 'transcription';

  const inspect = async () => {
    if (!file || busy || disabled) return;
    setError(''); setResult('');
    if (![...imageTypes, ...audioTypes].includes(file.type)) {
      setError('Choose PNG, JPEG, WebP, WAV, MP3, WebM, Ogg, FLAC, or M4A.'); return;
    }
    if (file.size > (isImage ? 5 : 10) * 1024 * 1024) {
      setError(`File exceeds the ${isImage ? 5 : 10} MiB limit.`); return;
    }
    setBusy(true);
    const controller = new AbortController(); abortRef.current = controller;
    try {
      const data_base64 = await readBase64(file);
      if (!mounted.current || controller.signal.aborted) return;
      const response = await api.post(isImage ? '/media/vision' : '/media/transcribe', {
        mime_type: file.type, data_base64, ...(isImage ? { prompt, detail: 'low' } : {}),
      }, { noRetry: true, signal: controller.signal });
      if (mounted.current) setResult(response.data.text);
    } catch { if (mounted.current) setError('Media request failed. Check capability status and try again explicitly.'); }
    finally { if (mounted.current) setBusy(false); }
  };

  const speak = async () => {
    if (busy || disabled || !latestResponse) return;
    setBusy(true); setError('');
    const controller = new AbortController(); abortRef.current = controller;
    try {
      const response = await api.post('/media/speech', { text: latestResponse.slice(0, 4096) },
        { responseType: 'blob', noRetry: true, signal: controller.signal });
      if (!mounted.current) return;
      if (urlRef.current) URL.revokeObjectURL(urlRef.current);
      urlRef.current = URL.createObjectURL(response.data); setAudioUrl(urlRef.current);
    } catch { if (mounted.current) setError('Speech generation failed; no automatic retry was attempted.'); }
    finally { if (mounted.current) setBusy(false); }
  };

  return <details className="border-t border-gray-200 bg-white p-3 text-sm">
    <summary className="cursor-pointer font-medium text-indigo-800 focus-visible:outline focus-visible:outline-2">Audio & vision</summary>
    <div className="mt-3 space-y-3">
      <p className="text-gray-700">Uploads go to the configured media provider only when you choose Analyze / transcribe. Media is not stored in HAM. Reviewed text sent to chat becomes part of chat history and memory; check it before sending.</p>
      <label className="block">Image or audio file
        <input className="mt-1 block max-w-full" type="file" accept={[...imageTypes, ...audioTypes].join(',')}
          disabled={busy || disabled} onChange={e => { setFile(e.target.files?.[0] || null); setResult(''); setError(''); }} />
      </label>
      {isImage && <label className="block">Question about the image
        <input className="mt-1 block w-full rounded border-gray-300" value={prompt} maxLength={4096}
          onChange={e => setPrompt(e.target.value)} disabled={busy} />
      </label>}
      <p className="text-gray-600">Vision: {status?.capabilities?.vision?.ready ? 'ready' : 'not configured'} · Transcription: {status?.capabilities?.transcription?.ready ? 'ready' : 'not configured'}</p>
      <div className="flex flex-wrap gap-2">
        <Button size="sm" onClick={inspect} disabled={disabled || busy || !file || !status?.capabilities?.[capability]?.ready || (isImage && !prompt.trim())}>Analyze / transcribe</Button>
        <Button size="sm" variant="outline" onClick={speak} disabled={disabled || busy || !latestResponse || !status?.capabilities?.speech?.ready}>Read last reply aloud</Button>
      </div>
      <div role="status" aria-live="polite">{busy ? 'Processing media…' : ''}</div>
      {error && <p role="alert" className="text-red-700">{error}</p>}
      {result && <div className="space-y-2">
        <label className="block">Extracted text — unverified
          <textarea className="mt-1 block w-full rounded border-gray-300" rows={4} value={result}
            maxLength={10000 - extractionPrefix.length} onChange={e => setResult(e.target.value)} />
        </label>
        <Button size="sm" variant="outline" disabled={disabled || busy || !result.trim() || result.length + extractionPrefix.length > 10000}
          onClick={() => onUseText(extractionPrefix + result)}>Send reviewed text to chat</Button>
      </div>}
      {audioUrl && <div><p>AI-generated voice. First 4,096 characters of the reply; the original reply is the text transcript.</p><audio controls src={audioUrl} aria-label="AI-generated reading of the last reply" /></div>}
    </div>
  </details>;
}
