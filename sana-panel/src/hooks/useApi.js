import { useState, useEffect, useCallback, useRef } from 'react';

/**
 * هوک سفارشی برای فراخوانی API
 *
 * @param {Function} apiFunction - تابع API که باید فراخوانی شود
 * @param {Array} deps - وابستگی‌ها (مثل useEffect)
 * @param {Object} options - تنظیمات اضافی
 * @returns {Object} { data, loading, error, refetch }
 */
export function useApi(apiFunction, deps = [], options = {}) {
  const { immediate = true, initialData = null, keepDataOnRefetch = false } = options;

  const [data, setData] = useState(initialData);
  const [loading, setLoading] = useState(immediate);
  const [error, setError] = useState(null);
  const isMountedRef = useRef(true);
  const hasLoadedRef = useRef(false);

  const fetchData = useCallback(async () => {
    if (!keepDataOnRefetch || !hasLoadedRef.current) {
      setLoading(true);
    }
    setError(null);

    try {
      const result = await apiFunction();
      if (isMountedRef.current) {
        setData(result);
        hasLoadedRef.current = true;
      }
      return result;
    } catch (err) {
      if (isMountedRef.current && (!keepDataOnRefetch || !hasLoadedRef.current)) {
        setError(err);
      }
      throw err;
    } finally {
      if (isMountedRef.current) {
        setLoading(false);
      }
    }
  }, [apiFunction, keepDataOnRefetch]);

  useEffect(() => {
    isMountedRef.current = true;
    if (immediate) {
      fetchData().catch(() => {});
    }
    return () => {
      isMountedRef.current = false;
    };
  }, deps); // eslint-disable-line react-hooks/exhaustive-deps

  return { data, loading, error, refetch: fetchData };
}
