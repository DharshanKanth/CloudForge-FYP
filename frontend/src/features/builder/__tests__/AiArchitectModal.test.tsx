import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { AiArchitectModal } from '../AiArchitectModal';

const architectMock = vi.hoisted(() => vi.fn());
vi.mock('../../../services/api', () => ({
  aiApi: { architect: architectMock },
}));

const PROMPT = /e\.g\./i;

describe('AiArchitectModal', () => {
  beforeEach(() => architectMock.mockReset());

  it('calls the AI and reports when it is not configured', async () => {
    architectMock.mockResolvedValue({ data: { configured: false, message: 'AI is not configured' } });
    render(<AiArchitectModal onApply={vi.fn()} onClose={vi.fn()} />);
    fireEvent.change(screen.getByPlaceholderText(PROMPT), { target: { value: 'a vpc' } });
    fireEvent.click(screen.getByRole('button', { name: /generate suggestion/i }));
    expect(await screen.findByText('AI is not configured')).toBeInTheDocument();
  });

  it('applies a configured suggestion to the canvas', async () => {
    const onApply = vi.fn();
    const onClose = vi.fn();
    architectMock.mockResolvedValue({
      data: {
        configured: true,
        rationale: 'A VPC with a subnet.',
        nodes: [{ id: 'vpc', data: { resourceType: 'vpc' } }],
        edges: [{ source: 'vpc', target: 'sub' }],
        validation: { valid: true, issues: [] },
      },
    });
    render(<AiArchitectModal onApply={onApply} onClose={onClose} />);
    fireEvent.change(screen.getByPlaceholderText(PROMPT), { target: { value: 'a vpc' } });
    fireEvent.click(screen.getByRole('button', { name: /generate suggestion/i }));

    const applyBtn = await screen.findByRole('button', { name: /apply to canvas/i });
    fireEvent.click(applyBtn);
    await waitFor(() => expect(onApply).toHaveBeenCalled());
    expect(onApply.mock.calls[0][1]).toEqual([{ source: 'vpc', target: 'sub' }]);
  });
});
