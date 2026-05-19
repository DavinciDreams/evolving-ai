import { describe, it, vi, beforeAll, afterAll } from 'vitest';
import { render } from '@testing-library/react';
import { AppProvider } from '../context/AppContext';
import App from '../App';

vi.mock('../services/api', () => {
  const mockApi = {
    get: vi.fn().mockResolvedValue({ data: {} }),
    post: vi.fn().mockResolvedValue({ data: {} }),
    interceptors: {
      request: { use: vi.fn() },
      response: { use: vi.fn() },
    },
  };
  return { api: mockApi, default: mockApi };
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
  });
});
