import { useState } from 'react';

import { useAddActivity } from './lead-queries';
import { customerWhatsappUrl, telHref } from './lead-whatsapp';
import type { LeadRead, ManualActivityType } from './types';

/**
 * Call and WhatsApp buttons for a lead (lead-crm R10.3, R10.4). The link opens
 * normally; afterwards a one-tap prompt offers to log the call / WhatsApp.
 * Logging a contact on a `new` lead marks it contacted (server rule, R7.3).
 */
export interface ContactActionsProps {
  lead: Pick<LeadRead, 'id' | 'name' | 'phone'>;
  branchName: string;
  compact?: boolean;
}

const LABELS: Record<'call' | 'whatsapp', string> = { call: 'call', whatsapp: 'WhatsApp' };

export function ContactActions({
  lead,
  branchName,
  compact = false,
}: ContactActionsProps): JSX.Element {
  const [prompt, setPrompt] = useState<'call' | 'whatsapp' | null>(null);
  const [logged, setLogged] = useState<string | null>(null);
  const addActivity = useAddActivity();
  const tel = telHref(lead.phone);
  const wa = customerWhatsappUrl(lead, branchName);

  const button = compact
    ? 'rounded border border-gray-300 px-2.5 py-1 text-xs font-medium text-gray-800 hover:bg-gray-100'
    : 'rounded border border-gray-300 px-3 py-2 text-sm font-medium text-gray-800 hover:bg-gray-100';

  const log = (type: ManualActivityType): void => {
    addActivity.mutate(
      { leadId: lead.id, body: { type } },
      {
        onSuccess: () => {
          setPrompt(null);
          setLogged(type === 'call' ? 'Call logged.' : 'WhatsApp logged.');
        },
      },
    );
  };

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-2">
        {tel && (
          <a
            href={tel}
            className={button}
            onClick={() => {
              setLogged(null);
              setPrompt('call');
            }}
          >
            📞 Call
          </a>
        )}
        {wa && (
          <a
            href={wa}
            target="_blank"
            rel="noreferrer"
            className={button}
            onClick={() => {
              setLogged(null);
              setPrompt('whatsapp');
            }}
          >
            💬 WhatsApp
          </a>
        )}
      </div>
      {prompt && (
        <div
          role="group"
          aria-label={`Log this ${LABELS[prompt]}?`}
          className="flex flex-wrap items-center gap-2 rounded border border-blue-200 bg-blue-50 px-3 py-2 text-sm"
        >
          <span className="text-blue-900">Log this {LABELS[prompt]}?</span>
          <button
            type="button"
            disabled={addActivity.isPending}
            onClick={() => log(prompt)}
            className="rounded bg-gray-900 px-3 py-1 text-xs font-medium text-white disabled:opacity-50"
          >
            {addActivity.isPending ? 'Logging…' : `Log ${LABELS[prompt]}`}
          </button>
          <button
            type="button"
            onClick={() => setPrompt(null)}
            className="rounded px-2 py-1 text-xs text-gray-600 hover:bg-white"
          >
            Not now
          </button>
          {addActivity.isError && <span className="text-xs text-red-600">Could not log it.</span>}
        </div>
      )}
      {logged && (
        <p role="status" className="text-xs text-green-700">
          {logged}
        </p>
      )}
    </div>
  );
}
