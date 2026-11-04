import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import AddonSelector from './AddonSelector';
import type { Combo } from '../../lib/api';

const baseProps = {
  cakes: [],
  specialDecor: [],
  showCombos: true,
  cakeId: null,
  cakeWeightHalfKg: 1,
  decor: [],
  comboIds: [],
  ledName: '',
  couponCode: '',
  onCakeChange: vi.fn(),
  onCakeWeightChange: vi.fn(),
  onChangeDecor: vi.fn(),
  onToggleCombo: vi.fn(),
  onLedNameChange: vi.fn(),
  onCouponChange: vi.fn(),
};

const comboWithSaving: Combo = {
  id: 1,
  name: 'Combo-1',
  description: 'Fog + cake',
  price_paise: 70000,
  image_url: '',
  worth_paise: 100000,
  savings_paise: 30000,
};

const comboNoSaving: Combo = {
  id: 2,
  name: 'Combo-2',
  description: 'Just fog',
  price_paise: 50000,
  image_url: '',
  worth_paise: null,
  savings_paise: 0,
};

describe('AddonSelector combo hero cards', () => {
  it('shows strike-through worth and a "Save" badge when savings_paise > 0', () => {
    render(<AddonSelector {...baseProps} combos={[comboWithSaving]} />);
    // The saving badge appears.
    expect(screen.getByText(/Save ₹300/i)).toBeInTheDocument();
    // The worth is shown struck through (₹1,000) alongside the price (₹700).
    expect(screen.getByText(/₹1,000/)).toBeInTheDocument();
    expect(screen.getByText(/₹700/)).toBeInTheDocument();
  });

  it('shows price only (no strike-through, no badge) when savings_paise === 0', () => {
    render(<AddonSelector {...baseProps} combos={[comboNoSaving]} />);
    expect(screen.queryByText(/Save ₹/i)).not.toBeInTheDocument();
    expect(screen.getByText(/₹500/)).toBeInTheDocument();
  });

  it('does not render combos when showCombos is false', () => {
    render(
      <AddonSelector {...baseProps} showCombos={false} combos={[comboWithSaving]} />,
    );
    expect(screen.queryByText('Combo-1')).not.toBeInTheDocument();
  });
});
