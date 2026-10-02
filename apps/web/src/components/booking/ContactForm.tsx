import { useState } from 'react';
import { ApiError, publicApi } from '../../lib/api';

/** Minimal contact form posting to POST /public/contact at runtime. */
export default function ContactForm() {
  const [name, setName] = useState('');
  const [phone, setPhone] = useState('');
  const [email, setEmail] = useState('');
  const [message, setMessage] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    setSuccess(null);
    try {
      const res = await publicApi.submitContact({ name, phone, email, message });
      setSuccess(res.message);
      setName('');
      setPhone('');
      setEmail('');
      setMessage('');
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : 'Could not send your message. Please try again.',
      );
    } finally {
      setSubmitting(false);
    }
  }

  if (success) {
    return <p className="rounded bg-green-50 p-4 text-green-800">{success}</p>;
  }

  return (
    <form onSubmit={onSubmit} className="grid gap-4">
      <label className="flex flex-col gap-1">
        <span className="text-sm font-medium">Name *</span>
        <input
          type="text"
          required
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="rounded border border-gray-300 px-3 py-2"
        />
      </label>
      <label className="flex flex-col gap-1">
        <span className="text-sm font-medium">Phone *</span>
        <input
          type="tel"
          required
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
          className="rounded border border-gray-300 px-3 py-2"
        />
      </label>
      <label className="flex flex-col gap-1">
        <span className="text-sm font-medium">Email *</span>
        <input
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="rounded border border-gray-300 px-3 py-2"
        />
      </label>
      <label className="flex flex-col gap-1">
        <span className="text-sm font-medium">Message *</span>
        <textarea
          required
          rows={4}
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          className="rounded border border-gray-300 px-3 py-2"
        />
      </label>
      {error && <p className="text-red-600">{error}</p>}
      <button
        type="submit"
        disabled={submitting}
        className="rounded bg-brand px-4 py-2 text-white disabled:opacity-40"
      >
        {submitting ? 'Sending…' : 'Send message'}
      </button>
    </form>
  );
}
