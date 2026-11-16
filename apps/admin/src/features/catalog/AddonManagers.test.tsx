import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';

import { CakeManager, DecorManager } from './AddonManagers';
import type { CakeAdminRead, NamedAddonAdminRead } from './types';

const deactivateCake = vi.fn();
const createDecor = vi.fn().mockResolvedValue({});

// Mutable fixtures the mocked hooks read from, reset per test.
let cakeRows: CakeAdminRead[] = [];
let decorRows: NamedAddonAdminRead[] = [];

vi.mock('./queries', () => ({
  useCakes: () => ({ data: cakeRows }),
  useCreateCake: () => ({ mutateAsync: vi.fn().mockResolvedValue({}), isPending: false }),
  useUpdateCake: () => ({ mutateAsync: vi.fn().mockResolvedValue({}), isPending: false }),
  useDeactivateCake: () => ({ mutate: deactivateCake, isPending: false }),
  useSpecialDecor: () => ({ data: decorRows }),
  useCreateDecor: () => ({ mutateAsync: createDecor, isPending: false }),
  useUpdateDecor: () => ({ mutateAsync: vi.fn().mockResolvedValue({}), isPending: false }),
  useDeactivateDecor: () => ({ mutate: vi.fn(), isPending: false }),
}));

// The image-upload helper is network-bound; stub it.
vi.mock('./catalog-image', () => ({
  uploadCatalogImage: vi.fn().mockResolvedValue('cakes/test-key'),
}));

function cake(id: number, active: boolean): CakeAdminRead {
  return {
    id,
    location_id: 1,
    description: `Cake ${id}`,
    price_paise: 40000,
    object_key: 'k',
    image_url: 'https://cdn/k',
    effective_from: '2020-01-01',
    effective_to: '2099-12-31',
    is_active: active,
  };
}

describe('CakeManager', () => {
  beforeEach(() => {
    deactivateCake.mockClear();
    cakeRows = [cake(1, true), cake(2, false)];
  });

  it('hides inactive cakes by default and shows them when toggled on', () => {
    const { rerender } = render(<CakeManager locationId={1} showInactive={false} />);
    expect(screen.getByText('Cake 1')).toBeInTheDocument();
    expect(screen.queryByText('Cake 2')).not.toBeInTheDocument();

    rerender(<CakeManager locationId={1} showInactive />);
    expect(screen.getByText('Cake 2')).toBeInTheDocument();
  });

  it('deactivates an active cake', () => {
    render(<CakeManager locationId={1} showInactive />);
    // The first row (active Cake 1) shows a Deactivate button.
    const deactivateButtons = screen.getAllByRole('button', { name: 'Deactivate' });
    fireEvent.click(deactivateButtons[0]);
    expect(deactivateCake).toHaveBeenCalledWith(1);
  });

  it('shows an Activate button for an inactive cake', () => {
    render(<CakeManager locationId={1} showInactive />);
    expect(screen.getByRole('button', { name: 'Activate' })).toBeInTheDocument();
  });
});

function decor(id: number, category: NamedAddonAdminRead['category']): NamedAddonAdminRead {
  return {
    id,
    location_id: 1,
    name: `Decor ${id}`,
    description: '',
    category,
    price_paise: 30000,
    object_key: 'k',
    image_url: 'https://cdn/k',
    effective_from: '2020-01-01',
    effective_to: '2099-12-31',
    is_active: true,
  };
}

describe('DecorManager category', () => {
  beforeEach(() => {
    createDecor.mockClear();
    decorRows = [];
  });

  it('renders a category select with the three labels in the create form', () => {
    render(<DecorManager locationId={1} showInactive />);
    const select = screen.getByRole('combobox', { name: 'Category' }) as HTMLSelectElement;
    const options = Array.from(select.options).map((o) => o.textContent);
    expect(options).toEqual(['Extra Decoration', 'Choose Gifts', 'Special Service']);
    // Defaults to the first (extra_decoration) value.
    expect(select.value).toBe('extra_decoration');
  });

  it('shows the category label in the decor list row', () => {
    decorRows = [decor(1, 'gifts')];
    render(<DecorManager locationId={1} showInactive />);
    // "Decor 1" is its own text node in the row; assert the category label is
    // present in that same list item's normalized text.
    const row = screen.getByText('Decor 1', { exact: false }).closest('li');
    expect(row).not.toBeNull();
    expect(row?.textContent).toContain('Choose Gifts');
  });
});
