import { render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import BookingWizard from './BookingWizard';
import { publicApi, type Location, type Plan } from '../../lib/api';

const location: Location = {
  id: 1,
  name: 'Hulimavu',
  slug: 'hulimavu',
  address: 'Bannerghatta Road',
  phone: '9876543210',
};

const plan: Plan = {
  id: 3,
  location_id: 1,
  title: 'Starlight Package',
  description: 'Perfect for birthdays',
  details: null,
  plan_type: 1,
  list_price_paise: 500000,
  price_paise: 450000,
  people_allowed: 4,
  max_people_allowed: 8,
  extra_guest_paise: 20000,
  advance_paise: 50000,
  gallery_urls: [],
};

describe('BookingWizard', () => {
  afterEach(() => {
    vi.restoreAllMocks();
    window.history.pushState({}, '', '/book?location=hulimavu');
  });

  it('renders step 1 with plans fetched for the location', async () => {
    window.history.pushState({}, '', '/book?location=hulimavu');
    vi.spyOn(publicApi, 'listLocations').mockResolvedValue([location]);
    vi.spyOn(publicApi, 'listPlans').mockResolvedValue([plan]);
    vi.spyOn(publicApi, 'listCakes').mockResolvedValue([]);
    vi.spyOn(publicApi, 'listSpecialDecor').mockResolvedValue([]);
    vi.spyOn(publicApi, 'listCombos').mockResolvedValue([]);
    vi.spyOn(publicApi, 'listOccasions').mockResolvedValue([]);

    render(<BookingWizard />);

    await waitFor(() =>
      expect(screen.getByText('Choose a plan and date')).toBeInTheDocument(),
    );
    expect(screen.getByText('Starlight Package')).toBeInTheDocument();
    // Discounted chargeable price (450000 paise) is shown.
    expect(screen.getByText('₹4,500.00')).toBeInTheDocument();
    expect(
      screen.getByText(/Booking at/i).textContent,
    ).toContain('Hulimavu');
  });

  it('shows an error when the location slug cannot be resolved', async () => {
    window.history.pushState({}, '', '/book?location=unknown');
    vi.spyOn(publicApi, 'listLocations').mockResolvedValue([location]);

    render(<BookingWizard />);

    await waitFor(() =>
      expect(screen.getByText(/could not load this location/i)).toBeInTheDocument(),
    );
  });
});
