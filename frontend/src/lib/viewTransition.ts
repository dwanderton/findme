import { flushSync } from "react-dom";

type DocWithVT = Document & { startViewTransition?: (cb: () => void) => unknown };

export function viewTransition(update: () => void): void {
  const doc = typeof document === "undefined" ? null : (document as DocWithVT);
  if (!doc?.startViewTransition) {
    update();
    return;
  }
  doc.startViewTransition(() => flushSync(update));
}
