import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import MessageBubble from '../components/chat/MessageBubble';

function show(response, evaluation = null) {
  return render(<MessageBubble isUser={false} message={{ response, evaluation, timestamp: new Date().toISOString() }} />);
}
describe('safe lightweight message rendering', () => {
  it('labels model self-judgment separately from benchmark evidence', () => {
    show('Answer', 0.8);
    expect(screen.getByText(/not an independent benchmark/)).toBeInTheDocument();
    expect(screen.getByText('Score: 80%')).toBeInTheDocument();
  });
  it('does not display invalid scores as measurements', () => {
    show('Answer', { fabricated: NaN, invalid: 7 });
    expect(screen.queryByText(/Score:|benchmark/)).not.toBeInTheDocument();
  });
  it('renders common and unknown code without loading every grammar', () => {
    const { container } = show('```python\nprint("hello")\n```\n\n```madeup\nunknown-code\n```');
    expect(container.textContent).toContain('print("hello")');
    expect(container.textContent).toContain('unknown-code');
  });
  it('does not interpret raw HTML as executable markup', () => {
    const { container } = show('<img src=x onerror=alert(1)>');
    expect(container.querySelector('img')).toBeNull();
  });
});
