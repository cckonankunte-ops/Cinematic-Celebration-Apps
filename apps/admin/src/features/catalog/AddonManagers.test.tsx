import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';

import { CakeManager } from './AddonManagers';
import type { CakeAdminRead } from './types';

const deactivateCake = vi.fn();

// Mutable fixtures the mocked hooks read from, reset per test.
let cakeRows: CakeAdminRead[] = [];

vi.mock('./queries', () => ({
  useCakes: () => ({ data: cakeRows }),
  useCreateCake: () => ({ mutateAsync: vi.fn().mockResolvedValue({}), isPending: false }),
  useUpdateCake: () => ({ mutateAsync: vi.fn().mockResolvedValue({}), isPending: false }),
  useDeactivateCake: () => ({ mutate: deactivateCake, isPending: false }),
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
