import { useEffect, useState } from "react";

/**
 * Reactive media-query matcher. SSR-safe: returns `false` on first render
 * (no `window`), syncs on mount.
 *
 *   const isMd = useMediaQuery("(min-width: 768px)");
 *   const prefersDark = useMediaQuery("(prefers-color-scheme: dark)");
 *   const reducedMotion = useMediaQuery("(prefers-reduced-motion: reduce)");
 */
export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined" || !window.matchMedia) return;
    const mql = window.matchMedia(query);
    setMatches(mql.matches);
    const onChange = (event: MediaQueryListEvent) => {
      setMatches(event.matches);
    };
    mql.addEventListener("change", onChange);
    return () => {
      mql.removeEventListener("change", onChange);
    };
  }, [query]);

  return matches;
}

/** Tailwind breakpoint matchers for convenience. */
export const useIsMobile = (): boolean => !useMediaQuery("(min-width: 768px)");
export const useIsDesktop = (): boolean => useMediaQuery("(min-width: 1024px)");
export const usePrefersDark = (): boolean => useMediaQuery("(prefers-color-scheme: dark)");
export const usePrefersReducedMotion = (): boolean =>
  useMediaQuery("(prefers-reduced-motion: reduce)");
