import { useEffect, useState } from "react";

/**
 * Debounce a value. Returns the previous value until `delay` ms elapse
 * without further changes.
 *
 * Used for the global search input, filter inputs in tables, etc. — anywhere
 * we want to issue a server query without one per keystroke.
 *
 *   const [search, setSearch] = useState("");
 *   const debounced = useDebounce(search, 250);
 *   const { data } = useQuery({ queryKey: ['search', debounced], ... });
 */
export function useDebounce<T>(value: T, delay = 250): T {
  const [debounced, setDebounced] = useState<T>(value);

  useEffect(() => {
    const handle = window.setTimeout(() => {
      setDebounced(value);
    }, delay);
    return () => {
      window.clearTimeout(handle);
    };
  }, [value, delay]);

  return debounced;
}
