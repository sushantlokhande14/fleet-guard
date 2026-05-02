import { useCallback, useEffect, useRef, useState } from "react";

export interface AsyncState<T> {
  data: T | undefined;
  error: Error | undefined;
  loading: boolean;
  reload: () => void;
}

/**
 * Run an async loader when `deps` change. With `pollMs`, reload on that interval
 * while `poll(data)` returns true (e.g. while a campaign is still running).
 */
export function useAsync<T>(
  load: () => Promise<T>,
  deps: unknown[],
  opts: { pollMs?: number; poll?: (data: T | undefined) => boolean } = {},
): AsyncState<T> {
  const [data, setData] = useState<T>();
  const [error, setError] = useState<Error>();
  const [loading, setLoading] = useState(true);
  const [tick, setTick] = useState(0);
  const latest = useRef(0);

  const reload = useCallback(() => setTick((t) => t + 1), []);

  useEffect(() => {
    const id = ++latest.current;
    setLoading(true);
    load()
      .then((d) => {
        if (id !== latest.current) return; // a newer request won
        setData(d);
        setError(undefined);
      })
      .catch((e: unknown) => {
        if (id === latest.current) setError(e instanceof Error ? e : new Error(String(e)));
      })
      .finally(() => {
        if (id === latest.current) setLoading(false);
      });
  }, [...deps, tick]);

  const { pollMs, poll } = opts;
  useEffect(() => {
    if (!pollMs || !(poll?.(data) ?? true)) return;
    const t = setTimeout(reload, pollMs);
    return () => clearTimeout(t);
  }, [data, pollMs, poll, reload]);

  return { data, error, loading, reload };
}
