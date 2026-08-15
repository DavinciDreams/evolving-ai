import { useState } from 'react';
import { ShieldCheckIcon } from '@heroicons/react/24/outline';
import { useApp } from '../../context/AppContext';
import Button from './Button';
import Card from './Card';
import Input from './Input';

export const AuthGate = ({ children }) => {
  const { isAuthenticated, authenticate } = useApp();
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
          The credential is held only in this browser tab’s memory and is cleared on refresh or logout.
        </p>
      </Card>
    </main>
  );
};

export default AuthGate;
