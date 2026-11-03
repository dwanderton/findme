import { describe, expect, it } from "vitest";

import { classifyCondition, isNight, weatherVisual } from "../weatherVisual";

describe("classifyCondition", () => {
  it("maps WMO text to families", () => {
    expect(classifyCondition("clear sky")).toBe("clear");
    expect(classifyCondition("mainly clear")).toBe("clear");
    expect(classifyCondition("partly cloudy")).toBe("cloudy");
    expect(classifyCondition("overcast")).toBe("cloudy");
    expect(classifyCondition("fog")).toBe("fog");
    expect(classifyCondition("depositing rime fog")).toBe("fog");
    expect(classifyCondition("light drizzle")).toBe("rain");
    expect(classifyCondition("heavy rain")).toBe("rain");
    expect(classifyCondition("violent showers")).toBe("rain");
    expect(classifyCondition("light snow")).toBe("snow");
    expect(classifyCondition("snow grains")).toBe("snow");
    expect(classifyCondition("thunderstorm with hail")).toBe("thunder");
  });

  it("defaults unknown to clear", () => {
    expect(classifyCondition(undefined)).toBe("clear");
    expect(classifyCondition("")).toBe("clear");
  });
});

describe("isNight", () => {
  it("before 6 and at/after 19 is night", () => {
    expect(isNight("05:30")).toBe(true);
    expect(isNight("19:00")).toBe(true);
    expect(isNight("23:59")).toBe(true);
  });
  it("daytime hours are day", () => {
    expect(isNight("06:00")).toBe(false);
    expect(isNight("14:20")).toBe(false);
    expect(isNight("18:59")).toBe(false);
  });
  it("missing time is day", () => {
    expect(isNight(undefined)).toBe(false);
  });
});

describe("weatherVisual", () => {
  it("picks day vs night gradient", () => {
    const day = weatherVisual("clear sky", "14:20");
    const night = weatherVisual("clear sky", "22:00");
    expect(day.night).toBe(false);
    expect(night.night).toBe(true);
    expect(day.gradient).not.toBe(night.gradient);
  });
  it("every family yields a gradient and accent", () => {
    for (const cond of ["clear sky", "overcast", "fog", "rain", "snow", "thunderstorm"]) {
      const v = weatherVisual(cond, "12:00");
      expect(v.gradient).toContain("gradient");
      expect(v.accent).toMatch(/^#/);
    }
  });
});
