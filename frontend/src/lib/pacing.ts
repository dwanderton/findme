export const STAGE_DWELL_MS = 2000;
export const COUNT_STEP_MS = 100;
export const COUNT_PACE_MAX = 50;

export const STAGE_ORDER = ["received", "extracting", "embedding", "ready"] as const;

export type PacedView = { stage: string; done: number };

export class ProgressPacer {
  private actualStageIdx = 0;
  private displayStageIdx = 0;
  private stageShownAt: number;
  private failed = false;

  private targetDone = 0;
  private total = 0;
  private displayDone = 0;
  private lastCountStepAt: number;

  constructor(now: number) {
    this.stageShownAt = now;
    this.lastCountStepAt = now;
  }

  feed(stage: string, done: number, total: number) {
    if (stage === "failed") {
      this.failed = true;
      return;
    }
    const idx = STAGE_ORDER.indexOf(stage as (typeof STAGE_ORDER)[number]);
    if (idx > this.actualStageIdx) this.actualStageIdx = idx;
    this.total = total;
    if (done > this.targetDone) this.targetDone = done;
  }

  tick(now: number): PacedView {
    if (this.failed) return { stage: "failed", done: this.displayDone };

    if (
      this.displayStageIdx < this.actualStageIdx &&
      now - this.stageShownAt >= STAGE_DWELL_MS
    ) {
      this.displayStageIdx += 1;
      this.stageShownAt = now;
      this.displayDone = 0;
      this.lastCountStepAt = now;
    }

    const displayingCurrent = this.displayStageIdx === this.actualStageIdx;
    const target = displayingCurrent ? this.targetDone : this.total;
    if (this.total > COUNT_PACE_MAX) {
      this.displayDone = target;
    } else {
      while (this.displayDone < target && now - this.lastCountStepAt >= COUNT_STEP_MS) {
        this.displayDone += 1;
        this.lastCountStepAt += COUNT_STEP_MS;
      }
      if (this.displayDone >= target) this.lastCountStepAt = Math.max(this.lastCountStepAt, now - COUNT_STEP_MS);
    }

    return { stage: STAGE_ORDER[this.displayStageIdx], done: this.displayDone };
  }
}
