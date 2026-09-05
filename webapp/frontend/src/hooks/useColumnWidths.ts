import { useRef, useState } from "react";

const MIN_COLUMN_WIDTH = 60;

function loadStored(
  key: string | undefined,
  fallback: Record<string, number>,
): Record<string, number> {
  if (!key) return fallback;
  try {
    const stored = localStorage.getItem(key);
    return stored ? { ...fallback, ...JSON.parse(stored) } : fallback;
  } catch {
    return fallback;
  }
}

function saveStored(key: string | undefined, value: Record<string, number>) {
  if (!key) return;
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // private browsing / quota exceeded -- the resize still works for this
    // session, it just won't be remembered next time.
  }
}

/**
 * Per-column pixel widths, adjustable by dragging a handle on the right
 * edge of a header cell. Mantine's Table has no built-in column resizing,
 * and this is a small enough need that a hand-rolled drag handler is
 * simpler than adopting a full data-grid library for it.
 *
 * storageKey persists the widths across reloads (a viewer-local layout
 * preference, not app data) -- localStorage is written once per drag, on
 * mouseup, not on every mousemove tick.
 */
export function useColumnWidths(initial: Record<string, number>, storageKey?: string) {
  const [widths, setWidths] = useState(() => loadStored(storageKey, initial));
  const widthsRef = useRef(widths);
  widthsRef.current = widths;

  function startResize(key: string, startX: number) {
    const startWidth = widthsRef.current[key];
    let latest = widthsRef.current;

    function onMouseMove(event: MouseEvent) {
      const delta = event.clientX - startX;
      latest = { ...latest, [key]: Math.max(MIN_COLUMN_WIDTH, startWidth + delta) };
      setWidths(latest);
    }

    function onMouseUp() {
      document.removeEventListener("mousemove", onMouseMove);
      document.removeEventListener("mouseup", onMouseUp);
      saveStored(storageKey, latest);
    }

    document.addEventListener("mousemove", onMouseMove);
    document.addEventListener("mouseup", onMouseUp);
  }

  return { widths, startResize };
}
