import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import DecorByCategory from './DecorByCategory';
import type { DecorCategory, SpecialDecor } from '../../lib/api';

function decor(id: number, name: string, category: DecorCategory): SpecialDecor {
  return {
    id,
    name,
    description: '',
    price_paise: 30000,
    image_url: '',
    sort_order: id,
    category,
  };
}

describe('DecorByCategory', () => {
  it('groups items under fixed-order category headings and omits empty ones', () => {
    render(
      <DecorByCategory
        specialDecor={[
          decor(1, 'Balloons', 'extra_decoration'),
          decor(2, 'Teddy', 'gifts'),
        ]}
        decor={[]}
        onChangeDecor={vi.fn()}
      />,
    );
    expect(screen.getByText('Extra Decoration')).toBeInTheDocument();
    expect(screen.getByText('Choose Gifts')).toBeInTheDocument();
    // No special_service items -> that heading is omitted.
    expect(screen.queryByText('Special Service')).not.toBeInTheDocument();
  });

  it('selects an item with quantity 1 when ticked', () => {
    const onChangeDecor = vi.fn();
    render(
      <DecorByCategory
        specialDecor={[decor(1, 'Balloons', 'extra_decoration')]}
        decor={[]}
        onChangeDecor={onChangeDecor}
      />,
    );
    fireEvent.click(screen.getByRole('checkbox'));
    expect(onChangeDecor).toHaveBeenCalledWith([{ id: 1, quantity: 1 }]);
  });

  it('shows an empty message when there is no decor', () => {
    render(
      <DecorByCategory specialDecor={[]} decor={[]} onChangeDecor={vi.fn()} />,
    );
    expect(screen.getByText(/No special decor available/)).toBeInTheDocument();
  });
});
