import { useEffect } from "react";

interface ShortcutOptions {
  /** Don't fire when an input/textarea/contenteditable is focused. Default: true. */
  ignoreInputs?: boolean;
  /** Disable without removing the listener (avoid effect churn). */
  enabled?: boolean;
}

/**
 * Register a keyboard shortcut.
 *
 * Combos use a "+"-separated string:
 *   "mod+k"     → Cmd+K on macOS, Ctrl+K elsewhere
 *   "shift+/"   → ?
 *   "g d"       → press g, then d (sequence, with 700ms gap allowed)
 *   "escape"    → single key
 *
 *   useShortcut("mod+k", () => commandPalette.open());
 *   useShortcut("?", () => helpDialog.open());
 *   useShortcut("escape", () => modal.close());
 */
export function useShortcut(
  combo: string,
  handler: (event: KeyboardEvent) => void,
  { ignoreInputs = true, enabled = true }: ShortcutOptions = {},
): void {
  useEffect(() => {
    if (!enabled) return;

    const sequence = parseCombo(combo);

    // Sequence state (for "g d"-style combos).
    let index = 0;
    let sequenceTimer: number | null = null;

    const reset = () => {
      index = 0;
      if (sequenceTimer !== null) {
        window.clearTimeout(sequenceTimer);
        sequenceTimer = null;
      }
    };

    const onKeyDown = (event: KeyboardEvent) => {
      if (ignoreInputs && isEditableTarget(event.target)) return;

      const step = sequence[index];
      if (!step) return;
      if (!matchesStep(event, step)) {
        reset();
        // Try matching as a fresh start (covers cases where the first step
        // of the sequence happens to be the same as the key just pressed).
        const first = sequence[0];
        if (first && matchesStep(event, first)) {
          index = 1;
        }
      } else {
        index += 1;
      }

      if (index >= sequence.length) {
        event.preventDefault();
        handler(event);
        reset();
        return;
      }

      // For multi-step combos, give the user a window to press the next key.
      if (sequence.length > 1) {
        if (sequenceTimer !== null) {
          window.clearTimeout(sequenceTimer);
        }
        sequenceTimer = window.setTimeout(reset, 700);
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      if (sequenceTimer !== null) {
        window.clearTimeout(sequenceTimer);
      }
    };
  }, [combo, handler, ignoreInputs, enabled]);
}

// ── internals ────────────────────────────────────────────────────────────────

interface Step {
  key: string;
  mod: boolean;
  ctrl: boolean;
  shift: boolean;
  alt: boolean;
  meta: boolean;
}

function parseCombo(combo: string): Step[] {
  // " g d " → [step("g"), step("d")]
  // " mod+k " → [step("mod+k")]
  return combo
    .trim()
    .split(/\s+/)
    .map(parseStep);
}

function parseStep(spec: string): Step {
  const parts = spec.toLowerCase().split("+").map((s) => s.trim());
  const step: Step = {
    key: "",
    mod: false,
    ctrl: false,
    shift: false,
    alt: false,
    meta: false,
  };
  for (const part of parts) {
    if (part === "mod") step.mod = true;
    else if (part === "ctrl") step.ctrl = true;
    else if (part === "shift") step.shift = true;
    else if (part === "alt" || part === "option") step.alt = true;
    else if (part === "meta" || part === "cmd" || part === "command") step.meta = true;
    else step.key = part;
  }
  return step;
}

function matchesStep(event: KeyboardEvent, step: Step): boolean {
  if (event.key.toLowerCase() !== step.key) return false;
  const isMac = /Mac|iPhone|iPad/i.test(navigator.platform);
  const modPressed = isMac ? event.metaKey : event.ctrlKey;
  if (step.mod && !modPressed) return false;
  if (step.ctrl && !event.ctrlKey) return false;
  if (step.meta && !event.metaKey) return false;
  if (step.shift !== event.shiftKey) return false;
  if (step.alt !== event.altKey) return false;
  return true;
}

function isEditableTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  const tag = target.tagName;
  if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return true;
  if (target.isContentEditable) return true;
  return false;
}
