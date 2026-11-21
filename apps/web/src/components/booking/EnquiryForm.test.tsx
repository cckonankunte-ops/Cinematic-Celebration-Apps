import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError, publicApi, type Location } from '../../lib/api';
import ContactForm from './ContactForm';
import QuickEnquiry from './QuickEnquiry';

const branches: Location[] = [
  { id: 1, name: 'Hulimavu', slug: 'hulimavu', address: null, phone: '9876500000' },
  { id: 2, name: 'Ecity', slug: 'ecity', address: null, phone: '9876500001' },
];

function fill(label: RegExp, value: string) {
  fireEvent.change(screen.getByLabelText(label), { target: { value } });
}

async function ready() {
  await waitFor(() => expect(screen.getByRole('option', { name: 'Ecity' })).toBeInTheDocument());
}

beforeEach(() => {
  window.localStorage.clear();
  vi.spyOn(publicApi, 'listLocations').mockResolvedValue(branches);
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('QuickEnquiry', () => {
  it('submits a homepage enquiry and shows the branch to call', async () => {
    const spy = vi
      .spyOn(publicApi, 'submitEnquiry')
      .mockResolvedValue({ message: 'Thanks! Our team will call or WhatsApp you shortly.' });
    render(<QuickEnquiry />);
    await ready();

    fill(/^Name/, 'Asha');
    fill(/^Phone/, '98765 43210');
    fill(/^Branch/, '2');
    fill(/What are you celebrating/, 'Anniversary');
    fireEvent.click(screen.getByRole('button', { name: /call back/i }));

    await waitFor(() => expect(screen.getByRole('status')).toBeInTheDocument());
    expect(spy).toHaveBeenCalledTimes(1);
    const body = spy.mock.calls[0][0];
    expect(body).toMatchObject({
      source: 'homepage_form',
      location_id: 2,
      name: 'Asha',
      phone: '98765 43210',
      message: 'Anniversary',
    });
    expect(body.website).toBeUndefined();
    expect(body.email).toBeUndefined();
    expect(screen.getByRole('link', { name: '9876500001' })).toHaveAttribute(
      'href',
      'tel:+919876500001',
    );
  });

  it('shows field errors and sends nothing when required fields are missing', async () => {
    const spy = vi.spyOn(publicApi, 'submitEnquiry');
    render(<QuickEnquiry />);
    await ready();

    fill(/^Phone/, '12345');
    fireEvent.click(screen.getByRole('button', { name: /call back/i }));

    expect(await screen.findByText('Please enter your name.')).toBeInTheDocument();
    expect(screen.getByText('Enter a valid Indian mobile number.')).toBeInTheDocument();
    expect(screen.getByText('Please choose a branch.')).toBeInTheDocument();
    expect(spy).not.toHaveBeenCalled();
  });

  it('keeps the values when the server rejects the enquiry', async () => {
    vi.spyOn(publicApi, 'submitEnquiry').mockRejectedValue(
      new ApiError('VALIDATION_ERROR', 'The request failed validation.', 422),
    );
    render(<QuickEnquiry />);
    await ready();

    fill(/^Name/, 'Asha');
    fill(/^Phone/, '9876543210');
    fill(/^Branch/, '1');
    fireEvent.click(screen.getByRole('button', { name: /call back/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent(/check your details/i);
    expect(screen.getByLabelText(/^Name/)).toHaveValue('Asha');
    expect(screen.getByLabelText(/^Phone/)).toHaveValue('9876543210');
  });

  it('hides the honeypot from people and assistive tech', async () => {
    const { container } = render(<QuickEnquiry />);
    await ready();
    expect(screen.queryByRole('textbox', { name: /website/i })).toBeNull();
    const trap = container.querySelector('input[name="website"]');
    expect(trap).not.toBeNull();
    expect(trap).toHaveAttribute('tabindex', '-1');
    expect(trap?.closest('[aria-hidden="true"]')).not.toBeNull();
  });

  it('passes a filled honeypot to the server (which then stores nothing)', async () => {
    const spy = vi.spyOn(publicApi, 'submitEnquiry').mockResolvedValue({ message: 'Thanks!' });
    const { container } = render(<QuickEnquiry />);
    await ready();

    fill(/^Name/, 'Bot');
    fill(/^Phone/, '9876543210');
    fill(/^Branch/, '1');
    fireEvent.change(container.querySelector('input[name="website"]') as Element, {
      target: { value: 'http://spam.example' },
    });
    fireEvent.click(screen.getByRole('button', { name: /call back/i }));

    await waitFor(() => expect(spy).toHaveBeenCalled());
    expect(spy.mock.calls[0][0].website).toBe('http://spam.example');
  });
});

describe('ContactForm', () => {
  it('posts a contact_form enquiry with an optional email', async () => {
    const spy = vi.spyOn(publicApi, 'submitEnquiry').mockResolvedValue({ message: 'Thanks!' });
    render(<ContactForm />);
    await ready();

    fill(/^Name/, 'Ravi');
    fill(/^Phone/, '9123456780');
    fill(/^Branch/, '1');
    fill(/^Message/, 'Do you host proposals?');
    fireEvent.click(screen.getByRole('button', { name: /send message/i }));

    await waitFor(() => expect(spy).toHaveBeenCalled());
    expect(spy.mock.calls[0][0]).toMatchObject({
      source: 'contact_form',
      location_id: 1,
      message: 'Do you host proposals?',
    });
    expect(spy.mock.calls[0][0].email).toBeUndefined();
  });

  it('rejects a malformed email but accepts an empty one', async () => {
    const spy = vi.spyOn(publicApi, 'submitEnquiry').mockResolvedValue({ message: 'Thanks!' });
    render(<ContactForm />);
    await ready();

    fill(/^Name/, 'Ravi');
    fill(/^Phone/, '9123456780');
    fill(/^Branch/, '1');
    fill(/^Email/, 'not-an-email');
    fireEvent.click(screen.getByRole('button', { name: /send message/i }));
    expect(await screen.findByText(/valid email/i)).toBeInTheDocument();
    expect(spy).not.toHaveBeenCalled();

    fill(/^Email/, '');
    fireEvent.click(screen.getByRole('button', { name: /send message/i }));
    await waitFor(() => expect(spy).toHaveBeenCalled());
  });
});
