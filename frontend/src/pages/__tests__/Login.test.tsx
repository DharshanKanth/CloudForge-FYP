import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Login from '../../pages/Login';

const loginMock = vi.fn();
vi.mock('../../hooks/useAuth', () => ({
  useAuth: () => ({
    login: loginMock,
    register: vi.fn(),
    logout: vi.fn(),
    user: null,
    isLoading: false,
  }),
}));

async function fillAndSubmit(container: HTMLElement) {
  const email = container.querySelector('input[type="email"]') as HTMLInputElement;
  const password = container.querySelector('input[type="password"]') as HTMLInputElement;
  fireEvent.change(email, { target: { value: 'demo@cloudforge.io' } });
  fireEvent.change(password, { target: { value: 'demo1234' } });
  // act() flushes the async submit handler and its state updates.
  await act(async () => {
    fireEvent.submit(container.querySelector('form') as HTMLFormElement);
  });
}

describe('Login page', () => {
  beforeEach(() => loginMock.mockReset());

  it('renders the sign-in form and demo shortcut', () => {
    render(
      <MemoryRouter>
        <Login />
      </MemoryRouter>
    );
    expect(screen.getByPlaceholderText('you@example.com')).toBeInTheDocument();
    expect(screen.getByText(/use demo account/i)).toBeInTheDocument();
  });

  it('submits the entered credentials via useAuth.login', async () => {
    loginMock.mockResolvedValue(undefined);
    const { container } = render(
      <MemoryRouter>
        <Login />
      </MemoryRouter>
    );
    await fillAndSubmit(container);
    expect(loginMock).toHaveBeenCalledWith('demo@cloudforge.io', 'demo1234');
  });
});
