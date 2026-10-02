import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

import { PaymentDialog } from './PaymentDialog';

// Mock the mutation hook so the dialog can be rendered in isolation without a
// QueryClient or a live API. `mutateAsync` records the body it was called with.
const mutateAsync = vi.fn().mockResolvedValue({ id: 1 });
vi.mock('./booking-queries', () => ({
  useRecordPayment: () => ({ mutateAsync, isPending: false }),
}));

describe('PaymentDialog', () => {
  beforeEach(() => {
    mutateAsync.mockClear();
  });

  it('renders nothing when closed', () => {
    const { container } = render(
      <PaymentDialog bookingId={1} open={false} onClose={() => {}} />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it('renders the form fields when open', () => {
    render(<PaymentDialog bookingId={1} open onClose={() => {}} />);
    expect(screen.getByText('Record payment')).toBeInTheDocument();
    expect(screen.getByLabelText('Method')).toBeInTheDocument();
    expect(screen.getByLabelText('Amount (₹)')).toBeInTheDocument();
  });

  it('converts rupees to paise and records the payment on submit', async () => {
    const onClose = vi.fn();
    render(<PaymentDialog bookingId={9} open onClose={onClose} />);

    fireEvent.change(screen.getByLabelText('Amount (₹)'), { target: { value: '500' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save payment' }));

    await waitFor(() => expect(mutateAsync).toHaveBeenCalledTimes(1));
    expect(mutateAsync).toHaveBeenCalledWith(
      expect.objectContaining({ method: 'upi', amount_paise: 50000 }),
    );
    await waitFor(() => expect(onClose).toHaveBeenCalled());
  });

  it('does not submit when the amount is empty', async () => {
    render(<PaymentDialog bookingId={1} open onClose={() => {}} />);
    fireEvent.click(screen.getByRole('button', { name: 'Save payment' }));
    await waitFor(() => expect(mutateAsync).not.toHaveBeenCalled());
  });
});
