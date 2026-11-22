/**
 * Quick-add a lead in about 10 seconds (lead-crm R4): phone first with the
 * phone keypad, source defaults to WhatsApp, optional name, note, follow-up and
 * enquiry code. Saving opens the lead with a toast; an existing open lead for
 * the same number is reused (the server attaches instead of duplicating).
 */

import { zodResolver } from '@hookform/resolvers/zod';
import { useState } from 'react';
import { Controller, useForm } from 'react-hook-form';
import { Link, useNavigate } from 'react-router-dom';

import { ApiError } from '@/api/client';
import { useLocation } from '@/features/location/useLocation';
import { FollowUpPicker } from './FollowUpPicker';
import { useCreateLead } from './lead-queries';
import { quickAddSchema, type QuickAddInput } from './lead-schema';
import { quickAddToast, type LeadToastState } from './lead-toast';
import { MANUAL_SOURCES, SOURCE_LABELS } from './types';

const inputClass =
  'w-full rounded border border-gray-300 px-3 py-2 text-sm focus:border-gray-500 focus:outline-none';

export function QuickAddLeadPage(): JSX.Element {
  const navigate = useNavigate();
  const { locations, selectedLocationId, canSwitch } = useLocation();
  const create = useCreateLead();
  const [serverError, setServerError] = useState<string | null>(null);

  const {
    register,
    control,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<QuickAddInput>({
    resolver: zodResolver(quickAddSchema),
    defaultValues: {
      phone: '',
      source: 'whatsapp',
      location_id: selectedLocationId ?? undefined,
      name: '',
      note: '',
      follow_up_at: '',
      enquiry_code: '',
    },
  });

  const onSubmit = handleSubmit(async (values) => {
    setServerError(null);
    // The resolver already validated; parse once more for the transformed types
    // (10-digit phone, upper-case code, blanks dropped). Transforms are idempotent.
    const body = quickAddSchema.parse(values);
    try {
      const result = await create.mutateAsync(body);
      const state: LeadToastState = { toast: quickAddToast(result) };
      navigate(`/leads/${result.lead.id}`, { state });
    } catch (err) {
      setServerError(err instanceof ApiError ? err.message : 'Failed to save the lead.');
    }
  });

  const err = (message?: string) =>
    message ? <p className="text-xs text-red-600">{message}</p> : null;

  return (
    <div className="mx-auto max-w-lg space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-gray-900">Add lead</h1>
        <Link to="/leads" className="text-sm text-gray-600 hover:underline">
          Cancel
        </Link>
      </div>

      <form
        onSubmit={onSubmit}
        noValidate
        className="space-y-4 rounded border border-gray-200 bg-white p-4"
      >
        <label className="block space-y-1 text-sm">
          <span className="font-medium text-gray-700">Phone *</span>
          <input
            type="tel"
            inputMode="tel"
            autoComplete="off"
            autoFocus
            placeholder="98765 43210"
            className={inputClass}
            aria-invalid={Boolean(errors.phone)}
            {...register('phone')}
          />
          {err(errors.phone?.message)}
        </label>

        <label className="block space-y-1 text-sm">
          <span className="font-medium text-gray-700">Source</span>
          <select className={inputClass} {...register('source')}>
            {MANUAL_SOURCES.map((s) => (
              <option key={s} value={s}>
                {SOURCE_LABELS[s]}
              </option>
            ))}
          </select>
        </label>

        <label className="block space-y-1 text-sm">
          <span className="font-medium text-gray-700">Name</span>
          <input
            type="text"
            autoComplete="off"
            className={inputClass}
            aria-invalid={Boolean(errors.name)}
            {...register('name')}
          />
          {err(errors.name?.message)}
        </label>

        {canSwitch ? (
          <label className="block space-y-1 text-sm">
            <span className="font-medium text-gray-700">Branch *</span>
            <select
              className={inputClass}
              aria-invalid={Boolean(errors.location_id)}
              {...register('location_id', { valueAsNumber: true })}
            >
              {locations.map((l) => (
                <option key={l.id} value={l.id}>
                  {l.name}
                </option>
              ))}
            </select>
            {err(errors.location_id?.message)}
          </label>
        ) : (
          <p className="text-sm text-gray-600">
            Branch:{' '}
            <span className="font-medium text-gray-900">
              {locations.find((l) => l.id === selectedLocationId)?.name ?? '—'}
            </span>
          </p>
        )}

        <label className="block space-y-1 text-sm">
          <span className="font-medium text-gray-700">Note</span>
          <textarea
            rows={3}
            placeholder="What did they ask about?"
            className={inputClass}
            aria-invalid={Boolean(errors.note)}
            {...register('note')}
          />
          {err(errors.note?.message)}
        </label>

        <div className="space-y-1 text-sm">
          <span className="font-medium text-gray-700">Follow-up</span>
          <Controller
            control={control}
            name="follow_up_at"
            render={({ field }) => (
              <FollowUpPicker value={field.value ?? ''} onChange={field.onChange} />
            )}
          />
        </div>

        <label className="block space-y-1 text-sm">
          <span className="font-medium text-gray-700">Enquiry code</span>
          <input
            type="text"
            autoComplete="off"
            autoCapitalize="characters"
            maxLength={12}
            placeholder="From the WhatsApp message, e.g. W4K7XQ"
            className={`${inputClass} uppercase`}
            aria-invalid={Boolean(errors.enquiry_code)}
            {...register('enquiry_code')}
          />
          {err(errors.enquiry_code?.message)}
        </label>

        {serverError && <p className="text-sm text-red-600">{serverError}</p>}

        <button
          type="submit"
          disabled={isSubmitting || create.isPending}
          className="w-full rounded bg-gray-900 px-3 py-2.5 text-sm font-medium text-white hover:bg-gray-800 disabled:opacity-50"
        >
          {isSubmitting || create.isPending ? 'Saving…' : 'Save lead'}
        </button>
      </form>
    </div>
  );
}
