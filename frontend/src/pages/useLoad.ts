import { useEffect, useState } from 'react';
export function useLoad<T>(load: () => Promise<T>) {
  const [version, setVersion] = useState(0);
  const [state, setState] = useState<{ data: T | null; error: string; loading: boolean }>({
    data: null,
    error: '',
    loading: true,
  });
  useEffect(() => {
    let current = true;
    setState({ data: null, error: '', loading: true });
    load()
      .then(data => {
        if (current) setState({ data, error: '', loading: false });
      })
      .catch((error: unknown) => {
        if (current)
          setState({
            data: null,
            error: error instanceof Error ? error.message : 'No pudimos cargar la información.',
            loading: false,
          });
      });
    return () => {
      current = false;
    };
  }, [load, version]);
  return { ...state, retry: () => setVersion(value => value + 1) };
}
