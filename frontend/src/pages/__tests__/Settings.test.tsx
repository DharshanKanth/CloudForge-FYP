import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

const mocks = vi.hoisted(() => ({
  list: vi.fn(),
  verifyCredentials: vi.fn(),
  aiStatus: vi.fn(),
}));

vi.mock('../../components/Layout', () => ({
  Layout: ({ children }: any) => children,
}));

vi.mock('../../services/api', () => ({
  cloudApi: {
    list: mocks.list,
    create: vi.fn(),
    remove: vi.fn(),
    verify: vi.fn(),
    verifyCredentials: mocks.verifyCredentials,
  },
  aiApi: { status: mocks.aiStatus },
}));

import Settings from '../Settings';

describe('Settings — cloud account verification', () => {
  beforeEach(() => {
    mocks.list.mockReset().mockResolvedValue({ data: [] });
    mocks.verifyCredentials.mockReset();
    mocks.aiStatus
      .mockReset()
      .mockResolvedValue({ data: { configured: false, provider: 'none', model: '' } });
  });

  it('tests credentials and surfaces the real provider error', async () => {
    mocks.verifyCredentials.mockResolvedValue({ data: { valid: false, error: 'InvalidClientTokenId' } });
    const { container } = render(<Settings />);
    await waitFor(() => expect(mocks.list).toHaveBeenCalled());

    fireEvent.click(screen.getByRole('button', { name: /connect aws/i }));
    fireEvent.change(screen.getByPlaceholderText('AKIA...'), {
      target: { value: 'AKIAIOSFODNN7EXAMPLE' },
    });
    const secret = container.querySelector('input[type="password"]') as HTMLInputElement;
    fireEvent.change(secret, { target: { value: 'secretvalue123' } });

    fireEvent.click(screen.getByRole('button', { name: /test connection/i }));

    expect(await screen.findByText(/InvalidClientTokenId/)).toBeInTheDocument();
    expect(mocks.verifyCredentials).toHaveBeenCalled();
  });
});
