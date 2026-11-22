import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from 'react';

/** A location the user may operate against. */
export interface LocationOption {
  id: number;
  name: string;
  slug: string;
  /** Branch phone; WhatsApp links fall back to it when `whatsapp_phone` is unset. */
  phone?: string | null;
  /** Branch WhatsApp number (lead-crm R11.3). */
  whatsapp_phone?: string | null;
}

interface LocationContextValue {
  /** All locations the user may switch between. */
  locations: LocationOption[];
  /** Currently selected location id, or null if none is selected. */
  selectedLocationId: number | null;
  /** Whether the user may switch locations (admins) vs is fixed (staff). */
  canSwitch: boolean;
  selectLocation: (id: number) => void;
}

const LocationContext = createContext<LocationContextValue | null>(null);

interface LocationProviderProps {
  children: ReactNode;
  /**
   * The locations available to the signed-in user. Admins receive every
   * active location; staff receive only their single assigned location.
   */
  locations: LocationOption[];
  /** Staff are pinned to one location and cannot switch. */
  canSwitch: boolean;
  /** Initial selection; defaults to the first available location. */
  initialLocationId?: number | null;
}

/** sessionStorage key for the admin's selected location (per browser tab). */
const SELECTED_LOCATION_KEY = 'cc.admin.selectedLocationId';

export function LocationProvider({
  children,
  locations,
  canSwitch,
  initialLocationId,
}: LocationProviderProps): JSX.Element {
  // Lazy init: for a user who may switch (admin), restore the last-selected
  // location from sessionStorage so a page refresh keeps the same branch for
  // the tab/session. Only accept a stored id that is still in the user's
  // available locations; otherwise fall back to the provided default. Staff
  // (canSwitch=false) are always pinned to their assigned location.
  const [selectedLocationId, setSelectedLocationId] = useState<number | null>(
    () => {
      const fallback = initialLocationId ?? locations[0]?.id ?? null;
      if (!canSwitch || typeof window === 'undefined') {
        return fallback;
      }
      const stored = Number(
        window.sessionStorage.getItem(SELECTED_LOCATION_KEY),
      );
      if (Number.isFinite(stored) && locations.some((l) => l.id === stored)) {
        return stored;
      }
      return fallback;
    },
  );

  const selectLocation = useCallback(
    (id: number) => {
      if (!canSwitch) {
        return;
      }
      setSelectedLocationId(id);
      if (typeof window !== 'undefined') {
        window.sessionStorage.setItem(SELECTED_LOCATION_KEY, String(id));
      }
    },
    [canSwitch],
  );

  const value = useMemo<LocationContextValue>(
    () => ({ locations, selectedLocationId, canSwitch, selectLocation }),
    [locations, selectedLocationId, canSwitch, selectLocation],
  );

  return (
    <LocationContext.Provider value={value}>
      {children}
    </LocationContext.Provider>
  );
}

/** Access the current location context. Throws if used outside the provider. */
export function useLocation(): LocationContextValue {
  const ctx = useContext(LocationContext);
  if (ctx === null) {
    throw new Error('useLocation must be used within a LocationProvider');
  }
  return ctx;
}
