"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";

import { fetchCapabilities } from "./service";
import type { Capabilities } from "./types";

const CapabilitiesContext = createContext<{
  capabilities: Capabilities | null;
  loading: boolean;
  refresh: () => Promise<void>;
}>({
  capabilities: null,
  loading: true,
  refresh: async () => {},
});

/**
 * Loads the viewing user's approval capabilities once on mount and exposes a
 * `refresh()` that updates the queue counts after a decision is made. The nav
 * item stays hidden until capabilities resolve (no flash of a wrong badge).
 */
export function CapabilitiesProvider({ children }: { children: React.ReactNode }) {
  const [capabilities, setCapabilities] = useState<Capabilities | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const next = await fetchCapabilities();
      setCapabilities(next);
    } catch {
      // Retain the last successfully fetched capabilities on transient
      // failures so a momentary network error never hides the queue badge.
    }
  }, []);

  useEffect(() => {
    let active = true;
    (async () => {
      const next = await fetchCapabilities().catch(() => null);
      if (!active) return;
      setCapabilities(next);
      setLoading(false);
    })();
    return () => {
      active = false;
    };
  }, []);

  return (
    <CapabilitiesContext.Provider value={{ capabilities, loading, refresh }}>
      {children}
    </CapabilitiesContext.Provider>
  );
}

export function useCapabilities() {
  return useContext(CapabilitiesContext);
}