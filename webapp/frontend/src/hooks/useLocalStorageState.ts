import { useState } from "react";

/**
 * A viewer-local layout preference (column order, row height, ...) that
 * survives a reload. Not app data -- if it can't be read/written (private
 * browsing, quota), the feature still works for the current session, it
 * just won't be remembered next time.
 */
export function useLocalStorageState<T>(key: string, defaultValue: T) {
  const [value, setValue] = useState<T>(() => {
    try {
      const stored = localStorage.getItem(key);
      return stored !== null ? (JSON.parse(stored) as T) : defaultValue;
    } catch {
      return defaultValue;
    }
  });

  function set(newValue: T) {
    setValue(newValue);
    try {
      localStorage.setItem(key, JSON.stringify(newValue));
    } catch {
      // ignore
    }
  }

  return [value, set] as const;
}
