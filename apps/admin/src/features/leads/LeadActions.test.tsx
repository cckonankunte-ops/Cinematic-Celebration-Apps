import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { CloseLeadDialog } from './CloseLeadDialog';
import { ContactActions } from './ContactActions';

const addActivity = vi.fn();

vi.mock('./lead-queries', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./lead-queries')>();
  return {
    ...actual,
    useAddActivity: () => ({ mutate: addActivity, isPending: false, isError: false }),
  };
});

beforeEach(() => addActivity.mockReset());

describe('CloseLeadDialog', () => {
  it('requires a reason before closing', () => {
    const onConfirm = vi.fn();
    render(
      <CloseLeadDialog
        status="lost"
        isSaving={false}
        error={null}
        onConfirm={onConfirm}
        onCancel={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: 'Close lead' }));
    expect(screen.getByText('Choose a reason.')).toBeInTheDocument();
    expect(onConfirm).not.toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText(/Reason/), { target: { value: 'price_budget' } });
    fireEvent.click(screen.getByRole('button', { name: 'Close lead' }));
    expect(onConfirm).toHaveBeenCalledWith('price_budget', null);
  });

  it('needs details for "Other"', () => {
    const onConfirm = vi.fn();
    render(
      <CloseLeadDialog
        status="not_interested"
        isSaving={false}
        error={null}
        onConfirm={onConfirm}
        onCancel={vi.fn()}
      />,
    );
    fireEvent.change(screen.getByLabelText(/Reason/), { target: { value: 'other' } });
    fireEvent.click(screen.getByRole('button', { name: 'Close lead' }));
    expect(screen.getByText(/short explanation/)).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/Details/), { target: { value: 'Moved city' } });
    fireEvent.click(screen.getByRole('button', { name: 'Close lead' }));
    expect(onConfirm).toHaveBeenCalledWith('other', 'Moved city');
  });

  it('closes on Escape', () => {
    const onCancel = vi.fn();
    render(
      <CloseLeadDialog
        status="lost"
        isSaving={false}
        error={null}
        onConfirm={vi.fn()}
        onCancel={onCancel}
      />,
    );
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(onCancel).toHaveBeenCalled();
  });
});

describe('ContactActions log-contact prompt', () => {
  const lead = { id: 5, name: 'Asha', phone: '9876543210' };

  it('offers to log a call after tapping Call, in one tap', async () => {
    addActivity.mockImplementation((_vars, opts?: { onSuccess?: () => void }) => opts?.onSuccess?.());
    render(<ContactActions lead={lead} branchName="Hulimavu" />);

    const call = screen.getByRole('link', { name: /Call/ });
    expect(call).toHaveAttribute('href', 'tel:+919876543210');
    fireEvent.click(call);

    fireEvent.click(screen.getByRole('button', { name: 'Log call' }));
    expect(addActivity).toHaveBeenCalledWith(
      { leadId: 5, body: { type: 'call' } },
      expect.any(Object),
    );
    await waitFor(() => expect(screen.getByText('Call logged.')).toBeInTheDocument());
  });

  it('offers to log a WhatsApp and can be dismissed', () => {
    render(<ContactActions lead={lead} branchName="Hulimavu" />);
    const wa = screen.getByRole('link', { name: /WhatsApp/ });
    expect(wa.getAttribute('href')).toMatch(/^https:\/\/wa\.me\/919876543210\?text=/);
    fireEvent.click(wa);
    expect(screen.getByRole('button', { name: 'Log WhatsApp' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Not now' }));
    expect(screen.queryByRole('button', { name: 'Log WhatsApp' })).toBeNull();
    expect(addActivity).not.toHaveBeenCalled();
  });
});
