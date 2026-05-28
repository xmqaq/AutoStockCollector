import { useCallback, useRef } from 'react';

export function useDebounce<T extends (...args: Parameters<T>) => void>(
  fn: T,
  delay: number
): T {
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const debouncedFn = useCallback(
    (...args: Parameters<T>) => {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
      }
      timerRef.current = setTimeout(() => {
        fn(...args);
      }, delay);
    },
    [fn, delay]
  ) as T;

  return debouncedFn;
}

export function useThrottle<T extends (...args: Parameters<T>) => void>(
  fn: T,
  delay: number
): T {
  const lastRun = useRef<number>(0);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const throttledFn = useCallback(
    (...args: Parameters<T>) => {
      const now = Date.now();
      const remaining = delay - (now - lastRun.current);

      if (remaining <= 0) {
        if (timerRef.current) {
          clearTimeout(timerRef.current);
          timerRef.current = null;
        }
        lastRun.current = now;
        fn(...args);
      } else if (!timerRef.current) {
        timerRef.current = setTimeout(() => {
          lastRun.current = Date.now();
          timerRef.current = null;
          fn(...args);
        }, remaining);
      }
    },
    [fn, delay]
  ) as T;

  return throttledFn;
}

import { useEffect, useState } from 'react';

export function useDebounceValue<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);

    return () => {
      clearTimeout(timer);
    };
  }, [value, delay]);

  return debouncedValue;
}

export function useDebouncedCallback<T extends (...args: Parameters<T>) => void>(
  fn: T,
  delay: number
): T {
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const debouncedFn = useCallback(
    (...args: Parameters<T>) => {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
      }
      timerRef.current = setTimeout(() => {
        fn(...args);
      }, delay);
    },
    [fn, delay]
  ) as T;

  return debouncedFn;
}