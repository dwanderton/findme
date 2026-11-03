export type SelfieChip = {
  name: string;
  state: "checking" | "ok" | "failed";
  facePx?: number;
  multipleFaces?: boolean;
  error?: string;
};

export type EnrollState = {
  userId: string | null;
  chips: SelfieChip[];
  busy: boolean;
  error: string | null;
};

export const MAX_SELFIES = 5;

export const initialEnroll: EnrollState = { userId: null, chips: [], busy: false, error: null };

type Action =
  | { type: "submit"; names: string[] }
  | { type: "success"; userId: string; faces: { selfie: number; facePx: number; multipleFaces: boolean }[] }
  | { type: "failure"; message: string; selfie?: number }
  | { type: "reset" };

export function canAddMore(s: EnrollState): boolean {
  return s.chips.filter((c) => c.state === "ok").length < MAX_SELFIES && !s.busy;
}

export function canFind(s: EnrollState): boolean {
  return s.userId !== null && !s.busy;
}

export function enrollReducer(s: EnrollState, a: Action): EnrollState {
  switch (a.type) {
    case "submit": {
      const chips = [...s.chips.filter((c) => c.state === "ok"), ...a.names.map((name) => ({ name, state: "checking" as const }))];
      return { ...s, chips, busy: true, error: null };
    }
    case "success": {
      const ok = s.chips.filter((c) => c.state === "ok");
      const pending = s.chips.filter((c) => c.state === "checking");
      const updated = pending.map((c, i) => {
        const f = a.faces[i];
        return f
          ? { ...c, state: "ok" as const, facePx: f.facePx, multipleFaces: f.multipleFaces }
          : { ...c, state: "failed" as const };
      });
      return { userId: a.userId, chips: [...ok, ...updated], busy: false, error: null };
    }
    case "failure": {
      const ok = s.chips.filter((c) => c.state === "ok");
      const pending = s.chips.filter((c) => c.state === "checking");
      const updated = pending.map((c, i) =>
        a.selfie !== undefined && i === a.selfie - ok.length
          ? { ...c, state: "failed" as const, error: a.message }
          : { ...c, state: "failed" as const },
      );
      return { ...s, chips: [...ok, ...updated], busy: false, error: a.message };
    }
    case "reset":
      return initialEnroll;
  }
}
