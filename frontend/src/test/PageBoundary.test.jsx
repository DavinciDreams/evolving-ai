import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import PageBoundary from '../components/common/PageBoundary';

describe('page recovery boundary', () => {
  it('renders healthy children', () => {
    render(<PageBoundary><p>Healthy page</p></PageBoundary>);
    expect(screen.getByText('Healthy page')).toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('keeps navigation, hides diagnostics and requires explicit recovery', () => {
    const logs = vi.spyOn(console, 'error').mockImplementation(() => {});
    function FailedPage() { throw new Error('synthetic-private-diagnostic'); }
    try {
      render(<><nav>Navigation remains</nav><PageBoundary><FailedPage /></PageBoundary></>);
      expect(screen.getByText('Navigation remains')).toBeInTheDocument();
      expect(screen.getByRole('alert')).toHaveTextContent('No automatic retry');
      expect(screen.getByRole('alert')).toHaveTextContent('inspect its status');
      expect(screen.getByRole('button', { name: 'Reload and sign in again' })).toBeInTheDocument();
      expect(screen.queryByText('synthetic-private-diagnostic')).not.toBeInTheDocument();
    } finally { logs.mockRestore(); }
  });
});
