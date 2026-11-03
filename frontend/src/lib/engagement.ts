export const IDLE_MS = 300_000;

const ACTIVITY_EVENTS = ["pointerdown", "pointermove", "keydown", "wheel", "touchstart", "scroll"] as const;

/* Reports whether the user is engaged: tab visible and some interaction within
 * idleMs. Consumers gate their backend polling on it — every poll an
 * unattended tab makes keeps a GPU worker's idle timeout from expiring.
 * Starts engaged; onChange fires only on transitions. */
export function watchEngagement(onChange: (engaged: boolean) => void, idleMs = IDLE_MS): () => void {
  let engaged = true;
  let idle = false;
  let timer: ReturnType<typeof setTimeout> | null = null;

  const emit = () => {
    const next = !document.hidden && !idle;
    if (next !== engaged) {
      engaged = next;
      onChange(next);
    }
  };

  const armIdleTimer = () => {
    if (timer) clearTimeout(timer);
    timer = setTimeout(() => {
      idle = true;
      emit();
    }, idleMs);
  };

  const onActivity = () => {
    idle = false;
    armIdleTimer();
    emit();
  };

  const onVisibility = () => {
    if (!document.hidden) {
      idle = false;
      armIdleTimer();
    }
    emit();
  };

  for (const e of ACTIVITY_EVENTS) window.addEventListener(e, onActivity, { passive: true });
  document.addEventListener("visibilitychange", onVisibility);
  armIdleTimer();

  return () => {
    if (timer) clearTimeout(timer);
    for (const e of ACTIVITY_EVENTS) window.removeEventListener(e, onActivity);
    document.removeEventListener("visibilitychange", onVisibility);
  };
}
