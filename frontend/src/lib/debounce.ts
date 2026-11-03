export function debounce<A extends unknown[]>(fn: (...args: A) => void, ms: number) {
  let timer: ReturnType<typeof setTimeout> | null = null;
  const wrapped = (...args: A) => {
    if (timer) clearTimeout(timer);
    timer = setTimeout(() => fn(...args), ms);
  };
  wrapped.cancel = () => {
    if (timer) clearTimeout(timer);
  };
  return wrapped;
}

export function lowGps(coverage: { withGps: number; total: number } | undefined): boolean {
  if (!coverage || coverage.total === 0) return false;
  return coverage.withGps / coverage.total < 0.2;
}
