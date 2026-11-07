"use client";

import { useEffect, useRef, useState, useCallback } from "react";

export interface UsePollingOptions {
  intervalMs?: number;
  enabled?: boolean;
  immediate?: boolean;
  onError?: (err: unknown) => void;
}

/**
 * Custom React hook for live polling (CLAUDE.md §11 & AC-053).
 *
 * Configured with a default interval of 2000 ms (2 seconds) for workflow progress.
 * Automatically cleans up timer intervals on unmount and pauses when disabled.
 */
export function usePolling(
  callback: () => Promise<boolean | void> | boolean | void,
  options: UsePollingOptions = {}
) {
  const {
    intervalMs = 2000,
    enabled = true,
    immediate = false,
    onError,
  } = options;

  const [isPolling, setIsPolling] = useState(enabled);
  const savedCallback = useRef(callback);
  const savedOnError = useRef(onError);
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  // Keep latest callback ref to prevent stale closures
  useEffect(() => {
    savedCallback.current = callback;
  }, [callback]);

  useEffect(() => {
    savedOnError.current = onError;
  }, [onError]);

  // Synchronize internal polling state with enabled prop
  useEffect(() => {
    setIsPolling(enabled);
  }, [enabled]);

  const stop = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    setIsPolling(false);
  }, []);

  const start = useCallback(() => {
    setIsPolling(true);
  }, []);

  useEffect(() => {
    if (!isPolling) {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
      return;
    }

    const executePoll = async () => {
      try {
        const result = await savedCallback.current();
        // If the polling callback explicitly returns false, stop polling
        if (result === false) {
          stop();
        }
      } catch (err: unknown) {
        if (savedOnError.current) {
          savedOnError.current(err);
        }
      }
    };

    if (immediate) {
      executePoll();
    }

    timerRef.current = setInterval(executePoll, intervalMs);

    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [isPolling, intervalMs, immediate, stop]);

  return { isPolling, start, stop };
}
