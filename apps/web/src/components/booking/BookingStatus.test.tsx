import { render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import BookingStatus from './BookingStatus';
import { publicApi, type BookingStatus as Status } from '../../lib/api';

function setToken(token: string): void {
  // jsdom lets us override the search string used by the component.
  window.history.pushState({}, '', `/booking-status?token=${token}`);
}

const sampleStatus: Status = {
  status: 'accepted',
  booking_name: 'Priya S',
  plan_title: 'Starlight Package',
  slot_description: '9 AM - 12 PM',
  booking_date: '2025-12-25',
  total_paise: 450000,
  amount_paid_paise: 50000,
  amount_due_paise: 400000,
  is_paid: false,
};

describe('BookingStatus', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders the fetched booking status and derived amounts', async () => {
    setToken('k3Jx9Qm2Lp7Zt1Rv');
    vi.spyOn(publicApi, 'getBookingStatus').mockResolvedValue(sampleStatus);

    render(<BookingStatus />);

    await waitFor(() =>
      expect(screen.getByText(/Status:/i)).toBeInTheDocument(),
    );
    expect(screen.getByText('Starlight Package')).toBeInTheDocument();
    expect(screen.getByText('9 AM - 12 PM')).toBeInTheDocument();
    // Total ₹4,500.00 derived from 450000 paise.
    expect(screen.getByText('₹4,500.00')).toBeInTheDocument();
  });

  it('shows an error when no token is present', async () => {
    window.history.pushState({}, '', '/booking-status');
    render(<BookingStatus />);
    await waitFor(() =>
      expect(screen.getByText(/no booking token/i)).toBeInTheDocument(),
    );
  });
});
