import { useCallback, useEffect, useRef, useState } from "react";

interface UseCopyOptions {
  /** How long the `copied` flag stays true after a successful copy. */
  resetMs?: number;
}

interface UseCopyReturn {
  /** True briefly after a successful copy — drive a "Copied" tooltip with this. */
  copied: boolean;
  /** Copy text to the clipboard. Resolves to true on success. */
  copy: (text: string) => Promise<boolean>;
}

/**
 * Clipboard copy with an auto-resetting flag. Used by EventHash, citation
 * code blocks, ID columns — anywhere the user needs to grab text fast.
 *
 *   const { copy, copied } = useCopy();
 *   <button onClick={() => copy(event.hash)}>
 *     {copied ? "Copied" : "Copy"}
 *   </button>
 */
export function useCopy({ resetMs = 1500 }: UseCopyOptions = {}): UseCopyReturn {
  const [copied, setCopied] = useState(false);
  const timeoutRef = useRef<number | null>(null);

  // Cancel pending reset on unmount so we don't setState after the component
  // is gone.
  useEffect(() => {
    return () => {
      if (timeoutRef.current !== null) {
        window.clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  const copy = useCallback(
    async (text: string): Promise<boolean> => {
      if (!navigator.clipboard) {
        // Some environments (older Safari, insecure contexts) lack the API.
        // Fail loudly in dev so we know, fall through in prod.
        console.warn("[useCopy] navigator.clipboard unavailable");
        return false;
      }
      try {
        await navigator.clipboard.writeText(text);
        setCopied(true);
        if (timeoutRef.current !== null) {
          window.clearTimeout(timeoutRef.current);
        }
        timeoutRef.current = window.setTimeout(() => {
          setCopied(false);
        }, resetMs);
        return true;
      } catch (err) {
        console.warn("[useCopy] failed:", err);
        return false;
      }
    },
    [resetMs],
  );

  return { copied, copy };
}
