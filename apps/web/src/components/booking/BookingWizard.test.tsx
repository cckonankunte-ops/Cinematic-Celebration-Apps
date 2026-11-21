import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
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
    vi.spyOn(publicApi, 'previewBooking').mockResolvedValue({
      plan_price_paise: 450000,
      extra_guest_paise: 0,
      kid_extra_guest_paise: 0,
      addon_lines: [],
      subtotal_paise: 450000,
      discount_paise: 0,
      food_paise: 0,
      other_paise: 0,
      cleaning_paise: 0,
      coupon_code: null,
      coupon_discount_paise: 0,
      total_paise: 450000,
      advance_paise: 50000,
      amount_paid_paise: 0,
      amount_due_paise: 450000,
    });

    render(<BookingWizard />);

    await waitFor(() =>
      expect(screen.getByText('Choose a decoration theme')).toBeInTheDocument(),
    );
    expect(screen.getByText('Starlight Package')).toBeInTheDocument();
    // Discounted chargeable price (450000 paise) is shown.
    expect(screen.getByText('₹4,500.00')).toBeInTheDocument();
    expect(
      screen.getByText(/Booking at/i).textContent,
    ).toContain('Hulimavu');
  });

  describe('Step 1 lead capture (lead-crm R2.4-R2.6)', () => {
    function mockCatalog() {
      vi.spyOn(publicApi, 'listLocations').mockResolvedValue([location]);
      vi.spyOn(publicApi, 'listPlans').mockResolvedValue([plan]);
      vi.spyOn(publicApi, 'listCakes').mockResolvedValue([]);
      vi.spyOn(publicApi, 'listSpecialDecor').mockResolvedValue([]);
      vi.spyOn(publicApi, 'listCombos').mockResolvedValue([]);
      vi.spyOn(publicApi, 'listOccasions').mockResolvedValue([]);
      vi.spyOn(publicApi, 'previewBooking').mockRejectedValue(new Error('not needed'));
      vi.spyOn(publicApi, 'availableSlots').mockResolvedValue([
        {
          id: 7,
          plan_id: 3,
          description: '11 AM - 1 PM',
          start_time: '11:00:00',
          duration_minutes: 120,
          show_combos: true,
          sort_order: 1,
          is_available: true,
        },
      ]);
    }

    async function fillStep1() {
      window.history.pushState({}, '', '/book?location=hulimavu');
      render(<BookingWizard />);
      const planButton = await screen.findAllByRole('button', { name: /Starlight Package/ });
      fireEvent.click(planButton[0]);
      fireEvent.click(await screen.findByRole('button', { name: /11 AM - 1 PM/ }));
      fireEvent.change(screen.getByLabelText(/Booking name/), { target: { value: 'Priya' } });
      fireEvent.change(screen.getByLabelText(/^Phone/), { target: { value: '9876543210' } });
    }

    beforeEach(() => {
      window.sessionStorage.clear();
      Element.prototype.scrollIntoView = vi.fn();
    });

    it('sends the lead on Next without waiting for it', async () => {
      mockCatalog();
      // A request that never finishes must not hold the visitor on Step 1.
      const lead = vi
        .spyOn(publicApi, 'createLead')
        .mockImplementation(() => new Promise(() => undefined));
      await fillStep1();

      fireEvent.click(screen.getByRole('button', { name: 'Next' }));

      expect(await screen.findByText("What's the occasion?")).toBeInTheDocument();
      expect(lead).toHaveBeenCalledTimes(1);
      expect(lead.mock.calls[0][0]).toMatchObject({
        location_id: 1,
        phone: '9876543210',
        name: 'Priya',
        plan_id: 3,
        start_time: '11:00:00',
        duration_minutes: 120,
        guests: 1,
      });
    });

    it('still moves on when the lead request fails', async () => {
      mockCatalog();
      vi.spyOn(publicApi, 'createLead').mockRejectedValue(new Error('offline'));
      await fillStep1();

      fireEvent.click(screen.getByRole('button', { name: 'Next' }));

      expect(await screen.findByText("What's the occasion?")).toBeInTheDocument();
    });
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
