import { useId, useState } from 'react';

import { formatDateTime, istToIso, toIstInputValue } from '@/lib/dates';
import { PRESETS, PRESET_LABELS, presetToIso } from './follow-up-presets';

/**
 * Follow-up picker (lead-crm R10.5, R10.6): one-tap presets plus a custom IST
 * date and time. `value` is an ISO timestamp, or '' for no follow-up.
 */
export interface FollowUpPickerProps {
  value: string;
  onChange: (iso: string) => void;
  /** Show a "No follow-up" choice (quick-add); hidden when clearing is separate. */
  allowNone?: boolean;
}

export function FollowUpPicker({
  value,
  onChange,
  allowNone = true,
}: FollowUpPickerProps): JSX.Element {
  const id = useId();
  const [custom, setCustom] = useState(false);
  const chip =
    'rounded-full border px-3 py-1.5 text-xs font-medium transition hover:border-gray-500';

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-2" role="group" aria-label="Follow-up presets">
        {allowNone && (
          <button
            type="button"
            onClick={() => {
              setCustom(false);
              onChange('');
            }}
            aria-pressed={value === '' && !custom}
            className={`${chip} ${value === '' && !custom ? 'border-gray-900 bg-gray-900 text-white' : 'border-gray-300 text-gray-700'}`}
          >
            No follow-up
          </button>
        )}
        {PRESETS.map((preset) => (
          <button
            key={preset}
            type="button"
            onClick={() => {
              setCustom(false);
              onChange(presetToIso(preset));
            }}
            className={`${chip} border-gray-300 text-gray-700`}
          >
            {PRESET_LABELS[preset]}
          </button>
        ))}
        <button
          type="button"
          onClick={() => setCustom(true)}
          aria-pressed={custom}
          className={`${chip} ${custom ? 'border-gray-900 bg-gray-900 text-white' : 'border-gray-300 text-gray-700'}`}
        >
          Custom
        </button>
      </div>
      {custom && (
        <label htmlFor={`${id}-custom`} className="block text-xs text-gray-600">
          Date and time (IST)
          <input
            id={`${id}-custom`}
            type="datetime-local"
            className="mt-1 block rounded border border-gray-300 px-2 py-1.5 text-sm"
            value={value ? toIstInputValue(value) : ''}
            onChange={(e) => {
              const [date, time] = e.target.value.split('T');
              onChange(date && time ? istToIso(date, time) : '');
            }}
          />
        </label>
      )}
      {value && (
        <p className="text-xs text-gray-600" aria-live="polite">
          Follow up: <span className="font-medium text-gray-900">{formatDateTime(value)}</span>
        </p>
      )}
    </div>
  );
}
