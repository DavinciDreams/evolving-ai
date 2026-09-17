import { useState } from 'react';
import { ShieldCheckIcon } from '@heroicons/react/24/outline';
import { useApp } from '../../context/AppContext';
import Button from './Button';
import Card from './Card';
import Input from './Input';

export const AuthGate = ({ children }) => {
  const { isAuthenticated, nostrEnabled, authenticate, authenticateWithNostr } = useApp();
  const [credential, setCredential] = useState('');
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (isAuthenticated) return children;

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError('');
    setIsSubmitting(true);
    try {
      await authenticate(credential);
      setCredential('');
    } catch {
      setCredential('');
      setError('The project credential was rejected. Ask a project steward for access.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleNostr = async () => {
    setError('');
    setIsSubmitting(true);
    try {
      await authenticateWithNostr();
    } catch (reason) {
      const missingSigner = reason instanceof Error && reason.message.includes('NIP-07');
      setError(missingSigner
        ? 'Enable a NIP-07 Nostr signer extension, then try again.'
        : 'This Nostr account is not authorized for Katbot.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <main className="min-h-screen bg-gray-50 flex items-center justify-center px-4">
      <Card className="w-full max-w-md">
        <div className="flex items-center gap-3 mb-5">
          <ShieldCheckIcon className="h-9 w-9 text-indigo-600" aria-hidden="true" />
          <div>
            <h1 className="text-xl font-semibold text-gray-900">Project access required</h1>
            <p className="text-sm text-gray-600">Katbot memories are private by default.</p>
          </div>
        </div>
        {nostrEnabled ? (
          <div className="mb-5">
            <Button type="button" className="w-full" disabled={isSubmitting} onClick={handleNostr}>
              {isSubmitting ? 'Waiting for signer…' : 'Continue with Nostr'}
            </Button>
            <p className="mt-2 text-xs text-gray-500">
              Your private key stays in your Nostr signer. Katbot receives only a signed proof.
            </p>
          </div>
        ) : null}
        {nostrEnabled ? (
          <div className="relative mb-5" aria-hidden="true">
            <div className="absolute inset-0 flex items-center"><div className="w-full border-t border-gray-200" /></div>
            <div className="relative flex justify-center"><span className="bg-white px-2 text-xs text-gray-500">or use automation access</span></div>
          </div>
        ) : null}
        <form onSubmit={handleSubmit} className="space-y-4">
          <Input
            label="Project credential"
            type="password"
            autoComplete="current-password"
            value={credential}
            onChange={(event) => setCredential(event.target.value)}
            disabled={isSubmitting}
            required
            autoFocus
          />
          {error ? (
            <p className="text-sm text-red-600" role="alert">{error}</p>
          ) : null}
          <Button type="submit" className="w-full" disabled={isSubmitting || !credential.trim()}>
            {isSubmitting ? 'Checking access…' : 'Continue'}
          </Button>
        </form>
        <p className="mt-4 text-xs text-gray-500">
          The API credential is held only in this browser tab’s memory and is cleared on refresh or logout.
        </p>
      </Card>
    </main>
  );
};

export default AuthGate;
