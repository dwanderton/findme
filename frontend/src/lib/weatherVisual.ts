export type WeatherFamily = "clear" | "cloudy" | "fog" | "rain" | "snow" | "thunder";

export type WeatherVisual = {
  family: WeatherFamily;
  night: boolean;
  gradient: string;
  accent: string;
  text: string;
};

export function classifyCondition(condition: string | undefined): WeatherFamily {
  const c = (condition ?? "").toLowerCase();
  if (c.includes("thunder")) return "thunder";
  if (c.includes("snow") || c.includes("grains")) return "snow";
  if (c.includes("rain") || c.includes("drizzle") || c.includes("shower")) return "rain";
  if (c.includes("fog") || c.includes("rime")) return "fog";
  if (c.includes("cloud") || c.includes("overcast")) return "cloudy";
  return "clear";
}

export function isNight(localTime: string | undefined): boolean {
  if (!localTime) return false;
  const h = Number(localTime.split(":")[0]);
  if (Number.isNaN(h)) return false;
  return h < 6 || h >= 19;
}

const GRADIENTS: Record<WeatherFamily, { day: string; night: string; accent: string }> = {
  clear: {
    day: "linear-gradient(160deg, #2e7ec9 0%, #5aa6e0 55%, #9fd0f0 100%)",
    night: "linear-gradient(160deg, #0b1733 0%, #1c2f5e 60%, #35508c 100%)",
    accent: "#ffe08a",
  },
  cloudy: {
    day: "linear-gradient(160deg, #5a6b82 0%, #7e8ea3 55%, #a7b4c6 100%)",
    night: "linear-gradient(160deg, #1a2030 0%, #2d3648 60%, #44506a 100%)",
    accent: "#cfd8e6",
  },
  fog: {
    day: "linear-gradient(160deg, #8a94a0 0%, #aeb6c0 55%, #cdd3da 100%)",
    night: "linear-gradient(160deg, #2a2f38 0%, #3d434e 60%, #565d6a 100%)",
    accent: "#e6eaef",
  },
  rain: {
    day: "linear-gradient(160deg, #2b3f54 0%, #3f5a73 55%, #5b7a93 100%)",
    night: "linear-gradient(160deg, #0d1620 0%, #1d2d3d 60%, #31485f 100%)",
    accent: "#8fc4e8",
  },
  snow: {
    day: "linear-gradient(160deg, #7d90a8 0%, #a7b8cc 55%, #dde6f0 100%)",
    night: "linear-gradient(160deg, #202838 0%, #39465c 60%, #5c6b84 100%)",
    accent: "#ffffff",
  },
  thunder: {
    day: "linear-gradient(160deg, #2a2b3a 0%, #44405e 55%, #615a86 100%)",
    night: "linear-gradient(160deg, #0a0a14 0%, #231f3a 60%, #3b3360 100%)",
    accent: "#f0c23a",
  },
};

export function weatherVisual(condition: string | undefined, localTime: string | undefined): WeatherVisual {
  const family = classifyCondition(condition);
  const night = isNight(localTime);
  const g = GRADIENTS[family];
  return {
    family,
    night,
    gradient: night ? g.night : g.day,
    accent: g.accent,
    text: "#ffffff",
  };
}
