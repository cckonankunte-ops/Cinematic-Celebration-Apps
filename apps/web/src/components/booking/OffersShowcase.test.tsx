import { render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import OffersShowcase from './OffersShowcase';
import { publicApi, type PublicOffer } from '../../lib/api';

function offer(code: string, overrides: Partial<PublicOffer> = {}): PublicOffer {
  return {
    code,
    name: null,
    description: null,
    location_name: 'Hulimavu',
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
        location_name: 'JP Nagar',
        effective_from: '2027-01-01',
        effective_to: '2027-03-31',
      }),
    ]);

    render(<OffersShowcase />);

    await waitFor(() => expect(screen.getByText('WEEKDAY10')).toBeInTheDocument());
    expect(screen.getByText('Weekday Special')).toBeInTheDocument();
    expect(screen.getByText('10% off on weekdays')).toBeInTheDocument();
    expect(screen.getByText('JP Nagar')).toBeInTheDocument();
    // Validity dates are intentionally not shown on the cards.
    expect(screen.queryByText(/Valid/)).not.toBeInTheDocument();
    expect(screen.queryByText(/2027/)).not.toBeInTheDocument();
  });

  it('groups the same offer into ONE card even when validity dates differ', async () => {
    vi.spyOn(publicApi, 'listOffers').mockResolvedValue([
      offer('EARLY100', {
        name: 'Early Bird',
        location_name: 'Branch1',
        effective_from: '2026-11-15',
        effective_to: '2026-11-25',
      }),
      offer('EARLY100', {
        name: 'Early Bird',
        location_name: 'Branch2',
        effective_from: '2026-11-17',
        effective_to: '2026-11-23',
      }),
    ]);

    render(<OffersShowcase />);

    await waitFor(() => expect(screen.getByText('EARLY100')).toBeInTheDocument());
    expect(screen.getAllByRole('listitem')).toHaveLength(1);
    expect(screen.getByText('2 branches')).toBeInTheDocument();
    expect(screen.getByText('Branch1, Branch2')).toBeInTheDocument();
  });

  it('shows just one branch when only one branch currently has the offer', async () => {
    // The API only returns offers valid today, so a branch whose window has not
    // started (or has ended) is simply absent from the list.
    vi.spyOn(publicApi, 'listOffers').mockResolvedValue([
      offer('EARLY100', { name: 'Early Bird', location_name: 'Branch1' }),
    ]);

    render(<OffersShowcase />);

    await waitFor(() => expect(screen.getByText('EARLY100')).toBeInTheDocument());
    expect(screen.getByText('Branch1')).toBeInTheDocument();
    expect(screen.queryByText(/branches/)).not.toBeInTheDocument();
  });

  it('keeps offers separate when the description differs', async () => {
    vi.spyOn(publicApi, 'listOffers').mockResolvedValue([
      offer('EARLY100', { name: 'Early Bird', description: '₹100 off', location_name: 'Branch1' }),
      offer('EARLY100', { name: 'Early Bird', description: '₹200 off', location_name: 'Branch2' }),
    ]);

    render(<OffersShowcase />);

    await waitFor(() => expect(screen.getAllByText('EARLY100')).toHaveLength(2));
    expect(screen.getAllByRole('listitem')).toHaveLength(2);
  });

  it('groups the same offer from several branches into ONE card', async () => {
    vi.spyOn(publicApi, 'listOffers').mockResolvedValue([
      offer('EARLY100', { name: 'Early Bird', location_name: 'Konankunte' }),
      offer('EARLY100', { name: 'Early Bird', location_name: 'Hulimavu' }),
      offer('EARLY100', { name: 'Early Bird', location_name: 'Electronic City' }),
    ]);

    render(<OffersShowcase />);

    await waitFor(() => expect(screen.getByText('EARLY100')).toBeInTheDocument());
    // One card, not three.
    expect(screen.getAllByText('EARLY100')).toHaveLength(1);
    expect(screen.getAllByRole('listitem')).toHaveLength(1);
    expect(screen.getByText('3 branches')).toBeInTheDocument();
    // Branch names are listed in the meta line.
    expect(
      screen.getByText(/Konankunte, Hulimavu, Electronic City/),
    ).toBeInTheDocument();
  });

  it('keeps offers separate when they differ (e.g. different code or dates)', async () => {
    vi.spyOn(publicApi, 'listOffers').mockResolvedValue([
      offer('AAA', { location_name: 'Konankunte' }),
      offer('BBB', { location_name: 'Konankunte' }),
    ]);

    render(<OffersShowcase />);

    await waitFor(() => expect(screen.getByText('AAA')).toBeInTheDocument());
    expect(screen.getByText('BBB')).toBeInTheDocument();
    expect(screen.getAllByRole('listitem')).toHaveLength(2);
  });
});
