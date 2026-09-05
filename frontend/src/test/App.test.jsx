import { describe, it, expect, vi, beforeAll, afterAll } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { AppProvider } from '../context/AppContext';
import App from '../App';
import {
  clearProjectApiKey,
  setProjectApiKey,
  validateProjectApiKey,
} from '../services/api';

vi.mock('../services/api', () => {
  const mockApi = {
    get: vi.fn().mockResolvedValue({ data: {} }),
    post: vi.fn().mockResolvedValue({ data: {} }),
    interceptors: {
      request: { use: vi.fn() },
      response: { use: vi.fn() },
    },
  };
  return {
    api: mockApi,
    default: mockApi,
    clearProjectApiKey: vi.fn(),
    setProjectApiKey: vi.fn(),
    validateProjectApiKey: vi.fn(),
  };
});

vi.mock('react-hot-toast', () => ({
  default: Object.assign(vi.fn(), { error: vi.fn(), success: vi.fn() }),
  Toaster: () => null,
}));

const originalError = console.error;
beforeAll(() => {
  console.error = (...args) => {
    if (typeof args[0] === 'string' && args[0].includes('React Router')) return;
    originalError(...args);
  };
});
afterAll(() => {
  console.error = originalError;
});

describe('App', () => {
  it('renders without crashing', () => {
    // AppProvider supplies QueryClientProvider + AppContext.
    // App supplies its own BrowserRouter — do NOT add a second Router here.
    render(
      <AppProvider>
        <App />
      </AppProvider>
    );
    expect(screen.getByRole('heading', { name: 'Project access required' })).toBeInTheDocument();
    expect(screen.getByLabelText('Project credential')).toHaveAttribute('type', 'password');
  });

  it('keeps the project credential out of browser storage and clears it on logout', async () => {
    const user = userEvent.setup();
    validateProjectApiKey.mockResolvedValueOnce({ is_initialized: true });
    render(
      <AppProvider>
        <App />
      </AppProvider>
    );

    await user.type(screen.getByLabelText('Project credential'), 'tab-memory-only-key');
    await user.click(screen.getByRole('button', { name: 'Continue' }));

    expect(await screen.findByText('AI Agent Dashboard')).toBeInTheDocument();
    expect(setProjectApiKey).toHaveBeenCalledWith('tab-memory-only-key');
    const storedValues = (storage) => Array.from(
      { length: storage.length },
      (_, index) => storage.getItem(storage.key(index))
    );
    expect(storedValues(localStorage)).not.toContain('tab-memory-only-key');
    expect(storedValues(sessionStorage)).not.toContain('tab-memory-only-key');

    await user.click(screen.getByRole('button', { name: 'Log out' }));
    expect(clearProjectApiKey).toHaveBeenCalled();
    expect(screen.getByRole('heading', { name: 'Project access required' })).toBeInTheDocument();
  });
});
