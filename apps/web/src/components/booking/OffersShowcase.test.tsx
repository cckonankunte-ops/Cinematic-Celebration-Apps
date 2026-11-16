import { render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import OffersShowcase from './OffersShowcase';
import { publicApi, type PublicOffer } from '../../lib/api';

function offer(code: string, overrides: Partial<PublicOffer> = {}): PublicOffer {
  return {
    code,
    name: null,
    description: null,
    effective_from: null,
    effective_to: null,
    ...overrides,
  };
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe('OffersShowcase', () => {
  it('renders nothing when there are no public offers', async () => {
    vi.spyOn(publicApi, 'listOffers').mockResolvedValue([]);
    const { container } = render(<OffersShowcase />);
    // Starts empty (offers === null) and stays empty after the empty resolve.
    await waitFor(() => expect(publicApi.listOffers).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });

  it('renders nothing when the request fails', async () => {
    vi.spyOn(publicApi, 'listOffers').mockRejectedValue(new Error('boom'));
    const { container } = render(<OffersShowcase />);
    await waitFor(() => expect(publicApi.listOffers).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });

  it('renders code, name, description and validity when offers exist', async () => {
    vi.spyOn(publicApi, 'listOffers').mockResolvedValue([
      offer('WEEKDAY10', {
        name: 'Weekday Special',
        description: '10% off on weekdays',
        effective_from: '2027-01-01',
        effective_to: '2027-03-31',
      }),
    ]);

    render(<OffersShowcase />);

    await waitFor(() => expect(screen.getByText('WEEKDAY10')).toBeInTheDocument());
    expect(screen.getByText('Weekday Special')).toBeInTheDocument();
    expect(screen.getByText('10% off on weekdays')).toBeInTheDocument();
    expect(screen.getByText(/Valid 01 Jan 2027/)).toBeInTheDocument();
  });
});
