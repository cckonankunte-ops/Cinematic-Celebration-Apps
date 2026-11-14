import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import AddonSelector from './AddonSelector';
import type { Combo, SpecialDecor } from '../../lib/api';

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

const decorItem: SpecialDecor = {
  id: 10,
  name: 'Fog entry',
  description: 'Dramatic fog entry',
  price_paise: 50000,
  image_url: '',
  sort_order: 1,
};

describe('AddonSelector special-decor quantity field', () => {
  it('lets the user clear the default 1 and type a replacement digit', () => {
    const onChangeDecor = vi.fn();
    render(
      <AddonSelector
        {...baseProps}
        combos={[]}
        specialDecor={[decorItem]}
        decor={[{ id: decorItem.id, quantity: 1 }]}
        onChangeDecor={onChangeDecor}
      />,
    );
    const qty = screen.getByLabelText(`Quantity for ${decorItem.name}`);

    // Clearing the field must be allowed (does not snap back to 1 mid-edit).
    fireEvent.change(qty, { target: { value: '' } });
    expect((qty as HTMLInputElement).value).toBe('');

    // Typing a new single digit commits that value.
    fireEvent.change(qty, { target: { value: '4' } });
    expect(onChangeDecor).toHaveBeenLastCalledWith([
      { id: decorItem.id, quantity: 4 },
    ]);
  });

  it('resets an empty quantity to 1 on blur', () => {
    const onChangeDecor = vi.fn();
    render(
      <AddonSelector
        {...baseProps}
        combos={[]}
        specialDecor={[decorItem]}
        decor={[{ id: decorItem.id, quantity: 1 }]}
        onChangeDecor={onChangeDecor}
      />,
    );
    const qty = screen.getByLabelText(`Quantity for ${decorItem.name}`);

    fireEvent.change(qty, { target: { value: '' } });
    fireEvent.blur(qty);
    expect(onChangeDecor).toHaveBeenLastCalledWith([
      { id: decorItem.id, quantity: 1 },
    ]);
  });
});
