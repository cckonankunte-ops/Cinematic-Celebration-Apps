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

export function LocationProvider({
  children,
  locations,
  canSwitch,
  initialLocationId,
}: LocationProviderProps): JSX.Element {
  const [selectedLocationId, setSelectedLocationId] = useState<number | null>(
    initialLocationId ?? locations[0]?.id ?? null,
  );

  const selectLocation = useCallback(
    (id: number) => {
      if (!canSwitch) {
        return;
      }
      setSelectedLocationId(id);
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
