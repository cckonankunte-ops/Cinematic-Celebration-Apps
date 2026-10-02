/**
 * Modal form to record a received payment against a booking. The amount is
 * entered in rupees and converted to integer paise via `rupeesToPaise` before
 * posting. On success the dialog invalidates queries (through the mutation
 * hook) and closes.
 */

import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';

import { ApiError } from '@/api/client';
import { rupeesToPaise } from '@/lib/money';
import { useRecordPayment } from './booking-queries';
import { paymentFormSchema, type PaymentFormValues } from './booking-schema';

interface PaymentDialogProps {
  bookingId: number;
  open: boolean;
  onClose: () => void;
}

export function PaymentDialog({
  bookingId,
  open,
  onClose,
}: PaymentDialogProps): JSX.Element | null {
  const recordPayment = useRecordPayment(bookingId);
  const {
    register,
    handleSubmit,
    reset,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<PaymentFormValues>({
    resolver: zodResolver(paymentFormSchema),
    defaultValues: { method: 'upi' },
  });

  if (!open) {
    return null;
  }

  const onSubmit = handleSubmit(async (values) => {
    try {
      await recordPayment.mutateAsync({
        method: values.method,
        amount_paise: rupeesToPaise(values.amount_rupees),
        note: values.note,
      });
      reset();
      onClose();
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Failed to record payment.';
      setError('root', { message });
    }
  });

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      role="dialog"
      aria-modal="true"
      aria-label="Record payment"
    >
      <form
        onSubmit={onSubmit}
        className="w-full max-w-sm space-y-4 rounded-lg bg-white p-5 shadow-lg"
      >
        <h2 className="text-base font-semibold text-gray-900">Record payment</h2>

        <div className="space-y-1">
          <label htmlFor="method" className="block text-sm font-medium text-gray-700">
            Method
          </label>
          <select
            id="method"
            className="w-full rounded border border-gray-300 px-3 py-2 text-sm"
            {...register('method')}
          >
            <option value="cash">Cash</option>
            <option value="upi">UPI</option>
            <option value="card">Card</option>
            <option value="other">Other</option>
          </select>
        </div>

        <div className="space-y-1">
          <label htmlFor="amount" className="block text-sm font-medium text-gray-700">
            Amount (₹)
          </label>
          <input
            id="amount"
            type="number"
            step="0.01"
            min="0"
            className="w-full rounded border border-gray-300 px-3 py-2 text-sm"
            {...register('amount_rupees', { valueAsNumber: true })}
          />
          {errors.amount_rupees && (
            <p className="text-xs text-red-600">{errors.amount_rupees.message}</p>
          )}
        </div>

        <div className="space-y-1">
          <label htmlFor="note" className="block text-sm font-medium text-gray-700">
            Note (optional)
          </label>
          <input
            id="note"
            type="text"
            className="w-full rounded border border-gray-300 px-3 py-2 text-sm"
            {...register('note')}
          />
        </div>

        {errors.root && <p className="text-sm text-red-600">{errors.root.message}</p>}

        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={isSubmitting}
            className="rounded bg-gray-900 px-3 py-2 text-sm font-medium text-white hover:bg-gray-800 disabled:opacity-60"
          >
            {isSubmitting ? 'Saving…' : 'Save payment'}
          </button>
        </div>
      </form>
    </div>
  );
}
