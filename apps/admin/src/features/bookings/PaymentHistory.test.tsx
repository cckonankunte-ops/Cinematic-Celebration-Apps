import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';

import { PaymentHistory } from './PaymentHistory';
import type { PaymentRead } from './types';

// Mock the void mutation so the component renders without a QueryClient.
vi.mock('./booking-queries', () => ({
  useVoidPayment: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));

// `useAuth` is swapped per-test to toggle admin vs staff.
const useAuthMock = vi.fn();
vi.mock('@/features/auth/useAuth', () => ({
  useAuth: () => useAuthMock(),
}));

function makePayments(): PaymentRead[] {
  const base = {
    booking_id: 9,
    received_at: '2025-12-20T10:00:00Z',
    recorded_by_user_id: 1,
    provider: null,
    provider_ref: null,
  };
  return [
    // An original payment that has been voided.
    {
      ...base,
      id: 1,
      method: 'cash',
      amount_paise: 50000,
      note: 'advance',
      reverses_payment_id: null,
      is_voided: true,
      voided_by_payment_id: 2,
    },
    // Its reversing entry.
    {
      ...base,
      id: 2,
      method: 'cash',
      amount_paise: -50000,
      note: 'wrong amount',
      reverses_payment_id: 1,
      is_voided: false,
      voided_by_payment_id: null,
    },
    // A normal, non-voided payment.
    {
      ...base,
      id: 3,
      method: 'upi',
      amount_paise: 30000,
      note: null,
      reverses_payment_id: null,
      is_voided: false,
      voided_by_payment_id: null,
    },
  ];
}

describe('PaymentHistory', () => {
  beforeEach(() => {
    useAuthMock.mockReset();
  });

  it('renders the voided badge and the reversal label', () => {
    useAuthMock.mockReturnValue({ user: { role: 'admin' } });
    render(<PaymentHistory bookingId={9} payments={makePayments()} totalPaise={30000} />);

    expect(screen.getByText('Voided')).toBeInTheDocument();
    expect(screen.getByText('Reversal of #1')).toBeInTheDocument();
  });

  it('shows the Void button for admins (on the non-voided original)', () => {
    useAuthMock.mockReturnValue({ user: { role: 'admin' } });
    render(<PaymentHistory bookingId={9} payments={makePayments()} totalPaise={30000} />);

    // Only payment #3 is voidable (non-voided, non-reversal) → exactly one button.
    expect(screen.getAllByRole('button', { name: 'Void' })).toHaveLength(1);
  });

  it('hides the Void button for staff', () => {
    useAuthMock.mockReturnValue({ user: { role: 'staff' } });
    render(<PaymentHistory bookingId={9} payments={makePayments()} totalPaise={30000} />);

    expect(screen.queryByRole('button', { name: 'Void' })).not.toBeInTheDocument();
  });
});
