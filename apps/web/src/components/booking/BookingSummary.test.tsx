import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import BookingSummary from './BookingSummary';
import type { PriceBreakdownRead } from '../../lib/api';

function breakdown(overrides: Partial<PriceBreakdownRead> = {}): PriceBreakdownRead {
  return {
    plan_price_paise: 300000,
    extra_guest_paise: 0,
    kid_extra_guest_paise: 0,
    addon_lines: [],
    subtotal_paise: 300000,
    discount_paise: 0,
    food_paise: 0,
    other_paise: 0,
    cleaning_paise: 0,
    coupon_code: null,
    coupon_discount_paise: 0,
    total_paise: 300000,
    advance_paise: 100000,
    amount_paid_paise: 0,
    amount_due_paise: 300000,
    ...overrides,
  };
}

describe('BookingSummary', () => {
  it('shows the server total and advance when collapsed', () => {
    render(<BookingSummary breakdown={breakdown()} adults={2} kids={0} />);
    expect(screen.getByText('₹3,000.00')).toBeInTheDocument(); // total
    expect(screen.getByText('₹1,000.00')).toBeInTheDocument(); // advance
  });

  it('S1: Balance = Total − Advance (from server fields) when expanded', () => {
    render(
      <BookingSummary
        breakdown={breakdown({ total_paise: 500000, advance_paise: 150000 })}
        adults={2}
        kids={0}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: /Total/ }));
    // Balance = 500000 - 150000 = 350000 paise = ₹3,500.00
    const balanceRow = screen.getByText(/Balance/).closest('div');
    expect(balanceRow?.textContent).toContain('₹3,500.00');
  });

  it('G1: shows a Kids count and a Kids charge line when kids are present', () => {
    render(
      <BookingSummary
        breakdown={breakdown({
          // Adult extra (20000) + kid extra (7500) = 27500 combined.
          extra_guest_paise: 27500,
          kid_extra_guest_paise: 7500,
        })}
        adults={2}
        kids={3}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: /Total/ }));
    expect(screen.getByText('Kids (3–10 yrs)')).toBeInTheDocument();
    // Kid charge line labelled with the kid count; assert its amount within
    // that row (the adult extra line also happens to be ₹75.00).
    const kidChargeRow = screen.getByText('Kids (3)').closest('div');
    expect(kidChargeRow?.textContent).toContain('₹75.00');
  });

  it('does not show a kids line when there are no kids', () => {
    render(<BookingSummary breakdown={breakdown()} adults={4} kids={0} />);
    fireEvent.click(screen.getByRole('button', { name: /Total/ }));
    expect(screen.queryByText('Kids (3–10 yrs)')).not.toBeInTheDocument();
  });

  it('renders a hint instead of figures when no breakdown yet', () => {
    render(<BookingSummary breakdown={null} adults={1} kids={0} />);
    expect(screen.getByText(/Pick a plan and time/)).toBeInTheDocument();
  });
});
