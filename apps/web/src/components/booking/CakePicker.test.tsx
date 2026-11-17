import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import CakePicker from './CakePicker';
import type { Cake } from '../../lib/api';

const cakes: Cake[] = [
  { id: 1, description: 'Chocolate truffle', price_paise: 40000, image_url: '' },
];

function setup() {
  const onCakeChange = vi.fn();
  const onCakeWeightChange = vi.fn();
  const onWeightPopupDone = vi.fn();
  render(
    <div>
      <button type="button">Next</button>
      <p>Blank area</p>
      <CakePicker
        cakes={cakes}
        cakeId={null}
        cakeWeightHalfKg={1}
        onCakeChange={onCakeChange}
        onCakeWeightChange={onCakeWeightChange}
        onWeightPopupDone={onWeightPopupDone}
      />
    </div>,
  );
  return { onCakeChange, onCakeWeightChange, onWeightPopupDone };
}

describe('CakePicker weight popup', () => {
  it('selecting a cake defaults the weight to 0.5 kg and opens the popup', () => {
    const { onCakeChange, onCakeWeightChange } = setup();
    fireEvent.click(screen.getByRole('button', { name: /Chocolate truffle/ }));
    expect(onCakeChange).toHaveBeenCalledWith(1);
    expect(onCakeWeightChange).toHaveBeenCalledWith(1); // 1 half-kg = 0.5 kg
    expect(screen.getByText('Choose weight')).toBeInTheDocument();
  });

  it('moves on (onWeightPopupDone) once a weight is picked', () => {
    const { onCakeWeightChange, onWeightPopupDone } = setup();
    fireEvent.click(screen.getByRole('button', { name: /Chocolate truffle/ }));
    fireEvent.click(screen.getByRole('button', { name: '1 kg' }));
    expect(onCakeWeightChange).toHaveBeenLastCalledWith(2);
    expect(onWeightPopupDone).toHaveBeenCalledTimes(1);
    expect(screen.queryByText('Choose weight')).not.toBeInTheDocument();
  });

  it('tapping blank space closes the popup, keeps the default, and moves on', () => {
    const { onWeightPopupDone } = setup();
    fireEvent.click(screen.getByRole('button', { name: /Chocolate truffle/ }));
    fireEvent.mouseDown(screen.getByText('Blank area'));
    expect(screen.queryByText('Choose weight')).not.toBeInTheDocument();
    expect(onWeightPopupDone).toHaveBeenCalledTimes(1);
  });

  it('tapping another button closes the popup but does NOT move on', () => {
    const { onWeightPopupDone } = setup();
    fireEvent.click(screen.getByRole('button', { name: /Chocolate truffle/ }));
    fireEvent.mouseDown(screen.getByRole('button', { name: 'Next' }));
    expect(screen.queryByText('Choose weight')).not.toBeInTheDocument();
    expect(onWeightPopupDone).not.toHaveBeenCalled();
  });
});
