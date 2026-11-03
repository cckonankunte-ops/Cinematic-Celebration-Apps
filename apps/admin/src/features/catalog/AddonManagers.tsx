/**
 * Catalog add-on managers (admin-only): cakes, special decor, and combos.
 *
 * Each manager lists its items, supports create (with an R2 image upload),
 * inline edit (image optional on edit), and activate/deactivate. The shared
 * `showInactive` flag (owned by CatalogPage) filters inactive rows in/out.
 *
 * Money is entered in rupees and converted to integer paise before posting;
 * (re)activation pushes effective_to to the far future so the item is bookable
 * again (deactivate sets it to today).
 */

import { useRef, useState } from 'react';

import { formatRupees, rupeesToPaise } from '@/lib/money';
import { uploadCatalogImage } from './catalog-image';
import {
  useCakes,
  useCombos,
  useCreateCake,
  useCreateCombo,
  useCreateDecor,
  useDeactivateCake,
  useDeactivateCombo,
  useDeactivateDecor,
  useSpecialDecor,
  useUpdateCake,
  useUpdateCombo,
  useUpdateDecor,
} from './queries';
import {
  FAR_FUTURE_DATE,
  type CakeAdminRead,
  type NamedAddonAdminRead,
} from './types';

// Validity windows for new rows start in the past to dodge the IST/UTC
// boundary race (see CreateComboForm notes); reactivation uses the far future.
const EFFECTIVE_FROM = '2020-01-01';

const field = 'rounded border border-gray-300 px-2 py-1 text-sm w-full';

/**
 * Add-ons section wrapper: a shared "Show inactive" toggle plus the three
 * managers (cakes, decor, combos) laid out in a responsive grid.
 */
export function AddonManagers({
  locationId,
}: {
  locationId: number | null;
}): JSX.Element {
  const [showInactive, setShowInactive] = useState(false);
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-gray-800">Add-ons</h2>
        <label className="flex items-center gap-2 text-sm text-gray-700">
          <input
            type="checkbox"
            checked={showInactive}
            onChange={(e) => setShowInactive(e.target.checked)}
          />
          Show inactive
        </label>
      </div>
      <div className="grid gap-4 md:grid-cols-3">
        <CakeManager locationId={locationId} showInactive={showInactive} />
        <DecorManager locationId={locationId} showInactive={showInactive} />
        <ComboManager locationId={locationId} showInactive={showInactive} />
      </div>
    </div>
  );
}

function ActiveTag({ active }: { active: boolean }): JSX.Element {
  return (
    <span
      className={`rounded px-1.5 py-0.5 text-xs ${
        active ? 'bg-green-100 text-green-800' : 'bg-gray-200 text-gray-600'
      }`}
    >
      {active ? 'active' : 'inactive'}
    </span>
  );
}

/** Shared row chrome: name/price label, status tag, and activate/deactivate. */
function RowActions({
  active,
  busy,
  onEdit,
  onToggleActive,
}: {
  active: boolean;
  busy: boolean;
  onEdit: () => void;
  onToggleActive: () => void;
}): JSX.Element {
  return (
    <div className="flex items-center gap-2">
      <ActiveTag active={active} />
      <button
        type="button"
        onClick={onEdit}
        className="rounded border border-gray-300 px-1.5 py-0.5 text-xs hover:bg-gray-50"
      >
        Edit
      </button>
      <button
        type="button"
        disabled={busy}
        onClick={onToggleActive}
        className={`rounded border px-1.5 py-0.5 text-xs disabled:opacity-50 ${
          active
            ? 'border-red-300 text-red-700 hover:bg-red-50'
            : 'border-green-300 text-green-700 hover:bg-green-50'
        }`}
      >
        {active ? 'Deactivate' : 'Activate'}
      </button>
    </div>
  );
}

/** A file input + status text, reused by every create/edit form. */
function ImagePicker({
  fileRef,
  label,
}: {
  fileRef: React.RefObject<HTMLInputElement>;
  label: string;
}): JSX.Element {
  return (
    <label className="block text-xs text-gray-600">
      {label}
      <input ref={fileRef} type="file" accept="image/*" className="mt-1 block text-xs" />
    </label>
  );
}

// ---------------------------------------------------------------------------
// Cakes
// ---------------------------------------------------------------------------
export function CakeManager({
  locationId,
  showInactive,
}: {
  locationId: number | null;
  showInactive: boolean;
}): JSX.Element {
  const cakes = useCakes(locationId);
  const create = useCreateCake(locationId);
  const deactivate = useDeactivateCake(locationId);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const rows = (cakes.data ?? []).filter((c) => showInactive || c.is_active);

  return (
    <div className="space-y-2">
      <h3 className="text-sm font-semibold text-gray-700">Cakes</h3>
      {error && <p className="text-xs text-red-600">{error}</p>}
      {rows.length === 0 && <p className="text-xs text-gray-500">None.</p>}
      <ul className="space-y-1">
        {rows.map((c) =>
          editingId === c.id ? (
            <li key={c.id} className="rounded border border-gray-200 bg-white p-2">
              <CakeForm
                locationId={locationId}
                existing={c}
                onDone={() => setEditingId(null)}
                onError={setError}
              />
            </li>
          ) : (
            <li
              key={c.id}
              className="flex items-center justify-between rounded border border-gray-200 bg-white px-3 py-2 text-sm"
            >
              <span>
                {c.description}{' '}
                <span className="text-gray-500">· {formatRupees(c.price_paise)}</span>
              </span>
              <RowActions
                active={c.is_active}
                busy={deactivate.isPending}
                onEdit={() => setEditingId(c.id)}
                onToggleActive={() =>
                  c.is_active
                    ? deactivate.mutate(c.id)
                    : setEditingId(c.id) /* reactivate via edit form save */
                }
              />
            </li>
          ),
        )}
      </ul>
      <CakeForm locationId={locationId} onError={setError} create={create} />
    </div>
  );
}

function CakeForm({
  locationId,
  existing,
  onDone,
  onError,
  create,
}: {
  locationId: number | null;
  existing?: CakeAdminRead;
  onDone?: () => void;
  onError: (msg: string | null) => void;
  create?: ReturnType<typeof useCreateCake>;
}): JSX.Element {
  const isEdit = existing !== undefined;
  const [description, setDescription] = useState(existing?.description ?? '');
  const [priceRupees, setPriceRupees] = useState(
    existing ? String(existing.price_paise / 100) : '',
  );
  const fileRef = useRef<HTMLInputElement>(null);
  const update = useUpdateCake(locationId, existing?.id ?? 0);
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent): Promise<void> => {
    e.preventDefault();
    if (locationId === null) {
      return;
    }
    onError(null);
    setBusy(true);
    try {
      const file = fileRef.current?.files?.[0];
      if (!isEdit && file === undefined) {
        onError('An image is required to create a cake.');
        setBusy(false);
        return;
      }
      const objectKey = file ? await uploadCatalogImage('cake', file) : undefined;
      if (isEdit) {
        await update.mutateAsync({
          description: description.trim(),
          price_paise: rupeesToPaise(Number(priceRupees)),
          ...(objectKey ? { object_key: objectKey } : {}),
          // Saving an edit also reactivates an inactive cake.
          is_active: true,
          effective_to: FAR_FUTURE_DATE,
        });
      } else {
        await (create as ReturnType<typeof useCreateCake>).mutateAsync({
          location_id: locationId,
          description: description.trim(),
          price_paise: rupeesToPaise(Number(priceRupees)),
          object_key: objectKey as string,
          effective_from: EFFECTIVE_FROM,
        });
        setDescription('');
        setPriceRupees('');
        if (fileRef.current) {
          fileRef.current.value = '';
        }
      }
      onDone?.();
    } catch {
      onError('Could not save the cake.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} className="space-y-2 rounded border border-gray-200 bg-white p-2">
      <h4 className="text-xs font-semibold text-gray-700">{isEdit ? 'Edit cake' : 'New cake'}</h4>
      <input
        className={field}
        placeholder="Description (e.g. Chocolate truffle)"
        required
        value={description}
        onChange={(e) => setDescription(e.target.value)}
      />
      <input
        className={field}
        type="number"
        min={0}
        step="0.01"
        placeholder="Price per 0.5kg in ₹ (e.g. 400)"
        required
        value={priceRupees}
        onChange={(e) => setPriceRupees(e.target.value)}
      />
      <ImagePicker fileRef={fileRef} label={isEdit ? 'Replace image (optional)' : 'Image'} />
      <div className="flex gap-2">
        <button
          type="submit"
          disabled={locationId === null || busy}
          className="rounded bg-gray-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-gray-800 disabled:opacity-50"
        >
          {busy ? 'Saving…' : isEdit ? 'Save' : 'Create cake'}
        </button>
        {isEdit && (
          <button
            type="button"
            onClick={onDone}
            className="rounded border border-gray-300 px-3 py-1.5 text-xs hover:bg-gray-50"
          >
            Cancel
          </button>
        )}
      </div>
    </form>
  );
}

// ---------------------------------------------------------------------------
// Special decor
// ---------------------------------------------------------------------------
export function DecorManager({
  locationId,
  showInactive,
}: {
  locationId: number | null;
  showInactive: boolean;
}): JSX.Element {
  const decor = useSpecialDecor(locationId);
  const create = useCreateDecor(locationId);
  const deactivate = useDeactivateDecor(locationId);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const rows = (decor.data ?? []).filter((d) => showInactive || d.is_active);

  return (
    <div className="space-y-2">
      <h3 className="text-sm font-semibold text-gray-700">Special decor</h3>
      {error && <p className="text-xs text-red-600">{error}</p>}
      {rows.length === 0 && <p className="text-xs text-gray-500">None.</p>}
      <ul className="space-y-1">
        {rows.map((d) =>
          editingId === d.id ? (
            <li key={d.id} className="rounded border border-gray-200 bg-white p-2">
              <DecorForm
                locationId={locationId}
                existing={d}
                onDone={() => setEditingId(null)}
                onError={setError}
              />
            </li>
          ) : (
            <li
              key={d.id}
              className="flex items-center justify-between rounded border border-gray-200 bg-white px-3 py-2 text-sm"
            >
              <span>
                {d.name} <span className="text-gray-500">· {formatRupees(d.price_paise)}</span>
              </span>
              <RowActions
                active={d.is_active}
                busy={deactivate.isPending}
                onEdit={() => setEditingId(d.id)}
                onToggleActive={() =>
                  d.is_active ? deactivate.mutate(d.id) : setEditingId(d.id)
                }
              />
            </li>
          ),
        )}
      </ul>
      <DecorForm locationId={locationId} onError={setError} create={create} />
    </div>
  );
}

function DecorForm({
  locationId,
  existing,
  onDone,
  onError,
  create,
}: {
  locationId: number | null;
  existing?: NamedAddonAdminRead;
  onDone?: () => void;
  onError: (msg: string | null) => void;
  create?: ReturnType<typeof useCreateDecor>;
}): JSX.Element {
  const isEdit = existing !== undefined;
  const [name, setName] = useState(existing?.name ?? '');
  const [description, setDescription] = useState(existing?.description ?? '');
  const [priceRupees, setPriceRupees] = useState(
    existing ? String(existing.price_paise / 100) : '',
  );
  const fileRef = useRef<HTMLInputElement>(null);
  const update = useUpdateDecor(locationId, existing?.id ?? 0);
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent): Promise<void> => {
    e.preventDefault();
    if (locationId === null) {
      return;
    }
    onError(null);
    setBusy(true);
    try {
      const file = fileRef.current?.files?.[0];
      if (!isEdit && file === undefined) {
        onError('An image is required to create a decor item.');
        setBusy(false);
        return;
      }
      const objectKey = file ? await uploadCatalogImage('decor', file) : undefined;
      if (isEdit) {
        await update.mutateAsync({
          name: name.trim(),
          description: description.trim(),
          price_paise: rupeesToPaise(Number(priceRupees)),
          ...(objectKey ? { object_key: objectKey } : {}),
          is_active: true,
          effective_to: FAR_FUTURE_DATE,
        });
      } else {
        await (create as ReturnType<typeof useCreateDecor>).mutateAsync({
          location_id: locationId,
          name: name.trim(),
          description: description.trim(),
          price_paise: rupeesToPaise(Number(priceRupees)),
          object_key: objectKey as string,
          sort_order: 0,
          effective_from: EFFECTIVE_FROM,
        });
        setName('');
        setDescription('');
        setPriceRupees('');
        if (fileRef.current) {
          fileRef.current.value = '';
        }
      }
      onDone?.();
    } catch {
      onError('Could not save the decor item.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} className="space-y-2 rounded border border-gray-200 bg-white p-2">
      <h4 className="text-xs font-semibold text-gray-700">
        {isEdit ? 'Edit decor' : 'New decor'}
      </h4>
      <input
        className={field}
        placeholder="Name (e.g. Rose bouquet)"
        required
        value={name}
        onChange={(e) => setName(e.target.value)}
      />
      <input
        className={field}
        placeholder="Description"
        value={description}
        onChange={(e) => setDescription(e.target.value)}
      />
      <input
        className={field}
        type="number"
        min={0}
        step="0.01"
        placeholder="Price in ₹ (e.g. 300)"
        required
        value={priceRupees}
        onChange={(e) => setPriceRupees(e.target.value)}
      />
      <ImagePicker fileRef={fileRef} label={isEdit ? 'Replace image (optional)' : 'Image'} />
      <div className="flex gap-2">
        <button
          type="submit"
          disabled={locationId === null || busy}
          className="rounded bg-gray-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-gray-800 disabled:opacity-50"
        >
          {busy ? 'Saving…' : isEdit ? 'Save' : 'Create decor'}
        </button>
        {isEdit && (
          <button
            type="button"
            onClick={onDone}
            className="rounded border border-gray-300 px-3 py-1.5 text-xs hover:bg-gray-50"
          >
            Cancel
          </button>
        )}
      </div>
    </form>
  );
}

// ---------------------------------------------------------------------------
// Combos
// ---------------------------------------------------------------------------
export function ComboManager({
  locationId,
  showInactive,
}: {
  locationId: number | null;
  showInactive: boolean;
}): JSX.Element {
  const combos = useCombos(locationId);
  const create = useCreateCombo(locationId);
  const deactivate = useDeactivateCombo(locationId);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const rows = (combos.data ?? []).filter((c) => showInactive || c.is_active);

  return (
    <div className="space-y-2">
      <h3 className="text-sm font-semibold text-gray-700">Combos</h3>
      {error && <p className="text-xs text-red-600">{error}</p>}
      {rows.length === 0 && <p className="text-xs text-gray-500">None.</p>}
      <ul className="space-y-1">
        {rows.map((c) =>
          editingId === c.id ? (
            <li key={c.id} className="rounded border border-gray-200 bg-white p-2">
              <ComboForm
                locationId={locationId}
                existing={c}
                onDone={() => setEditingId(null)}
                onError={setError}
              />
            </li>
          ) : (
            <li
              key={c.id}
              className="flex items-center justify-between rounded border border-gray-200 bg-white px-3 py-2 text-sm"
            >
              <span>
                {c.name} <span className="text-gray-500">· {formatRupees(c.price_paise)}</span>
              </span>
              <RowActions
                active={c.is_active}
                busy={deactivate.isPending}
                onEdit={() => setEditingId(c.id)}
                onToggleActive={() =>
                  c.is_active ? deactivate.mutate(c.id) : setEditingId(c.id)
                }
              />
            </li>
          ),
        )}
      </ul>
      <ComboForm locationId={locationId} onError={setError} create={create} />
    </div>
  );
}

function ComboForm({
  locationId,
  existing,
  onDone,
  onError,
  create,
}: {
  locationId: number | null;
  existing?: NamedAddonAdminRead;
  onDone?: () => void;
  onError: (msg: string | null) => void;
  create?: ReturnType<typeof useCreateCombo>;
}): JSX.Element {
  const isEdit = existing !== undefined;
  const [name, setName] = useState(existing?.name ?? '');
  const [description, setDescription] = useState(existing?.description ?? '');
  const [priceRupees, setPriceRupees] = useState(
    existing ? String(existing.price_paise / 100) : '',
  );
  const [cakeBaseline, setCakeBaseline] = useState(
    existing?.cake_baseline_paise != null ? String(existing.cake_baseline_paise / 100) : '',
  );
  const [ledBaseline, setLedBaseline] = useState(
    existing?.led_baseline_paise != null ? String(existing.led_baseline_paise / 100) : '',
  );
  const fileRef = useRef<HTMLInputElement>(null);
  const update = useUpdateCombo(locationId, existing?.id ?? 0);
  const [busy, setBusy] = useState(false);

  const baseline = (raw: string): number | null =>
    raw.trim() === '' ? null : rupeesToPaise(Number(raw));

  const submit = async (e: React.FormEvent): Promise<void> => {
    e.preventDefault();
    if (locationId === null) {
      return;
    }
    onError(null);
    setBusy(true);
    try {
      // A combo is not an image tile; its image is optional on both create and
      // edit (the backend defaults object_key when omitted).
      const file = fileRef.current?.files?.[0];
      const objectKey = file ? await uploadCatalogImage('combo', file) : undefined;
      if (isEdit) {
        await update.mutateAsync({
          name: name.trim(),
          description: description.trim(),
          price_paise: rupeesToPaise(Number(priceRupees)),
          cake_baseline_paise: baseline(cakeBaseline),
          led_baseline_paise: baseline(ledBaseline),
          ...(objectKey ? { object_key: objectKey } : {}),
          is_active: true,
          effective_to: FAR_FUTURE_DATE,
        });
      } else {
        await (create as ReturnType<typeof useCreateCombo>).mutateAsync({
          location_id: locationId,
          name: name.trim(),
          description: description.trim(),
          price_paise: rupeesToPaise(Number(priceRupees)),
          cake_baseline_paise: baseline(cakeBaseline),
          led_baseline_paise: baseline(ledBaseline),
          effective_from: EFFECTIVE_FROM,
          ...(objectKey ? { object_key: objectKey } : {}),
        });
        setName('');
        setDescription('');
        setPriceRupees('');
        setCakeBaseline('');
        setLedBaseline('');
        if (fileRef.current) {
          fileRef.current.value = '';
        }
      }
      onDone?.();
    } catch {
      onError('Could not save the combo.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} className="space-y-2 rounded border border-gray-200 bg-white p-2">
      <h4 className="text-xs font-semibold text-gray-700">
        {isEdit ? 'Edit combo' : 'New combo'}
      </h4>
      <input
        className={field}
        placeholder="Name (e.g. Combo3)"
        required
        value={name}
        onChange={(e) => setName(e.target.value)}
      />
      <input
        className={field}
        placeholder="What's included"
        value={description}
        onChange={(e) => setDescription(e.target.value)}
      />
      <input
        className={field}
        type="number"
        min={0}
        step="0.01"
        placeholder="Combo price in ₹ (e.g. 1100)"
        required
        value={priceRupees}
        onChange={(e) => setPriceRupees(e.target.value)}
      />
      <input
        className={field}
        type="number"
        min={0}
        step="0.01"
        placeholder="Cake baseline in ₹, optional"
        value={cakeBaseline}
        onChange={(e) => setCakeBaseline(e.target.value)}
      />
      <input
        className={field}
        type="number"
        min={0}
        step="0.01"
        placeholder="LED baseline in ₹, optional"
        value={ledBaseline}
        onChange={(e) => setLedBaseline(e.target.value)}
      />
      <ImagePicker fileRef={fileRef} label="Image (optional)" />
      <div className="flex gap-2">
        <button
          type="submit"
          disabled={locationId === null || busy}
          className="rounded bg-gray-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-gray-800 disabled:opacity-50"
        >
          {busy ? 'Saving…' : isEdit ? 'Save' : 'Create combo'}
        </button>
        {isEdit && (
          <button
            type="button"
            onClick={onDone}
            className="rounded border border-gray-300 px-3 py-1.5 text-xs hover:bg-gray-50"
          >
            Cancel
          </button>
        )}
      </div>
    </form>
  );
}
