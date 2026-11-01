"use client";
import { useSyncExternalStore } from "react";

function subscribe(query: string) {
  return (onChange: () => void) => {
    const mql = window.matchMedia(query);
    mql.addEventListener("change", onChange);
    return () => mql.removeEventListener("change", onChange);
  };
}

/** SSR-safe media query hook. Returns false on the server/first paint and
 * syncs to the real value on mount, so no window reference leaks into SSR. */
export function useMediaQuery(query: string) {
  return useSyncExternalStore(subscribe(query), () => window.matchMedia(query).matches, () => false);
}
