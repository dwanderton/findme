import { describe, expect, it } from "vitest";

import { DEFAULT_TILES, MAX_TILES, pickTiles } from "../../components/Backdrop";

describe("pickTiles", () => {
  it("uses upload urls until served urls exist", () => {
    expect(pickTiles(["u1", "u2"], [])).toEqual(["u1", "u2"]);
    expect(pickTiles(["u1"], ["s1", "s2"])).toEqual(["s1", "s2"]);
  });

  it("samples down to the cap evenly", () => {
    const urls = Array.from({ length: 300 }, (_, i) => `t${i}`);
    const tiles = pickTiles(urls, []);
    expect(tiles.length).toBe(MAX_TILES);
    expect(tiles[0]).toBe("t0");
    expect(new Set(tiles).size).toBe(MAX_TILES);
  });

  it("empty everywhere yields empty", () => {
    expect(pickTiles([], [])).toEqual([]);
  });
});

describe("DEFAULT_TILES", () => {
  it("provides a demo album under the tile cap", () => {
    expect(DEFAULT_TILES.length).toBeGreaterThan(0);
    expect(DEFAULT_TILES.length).toBeLessThanOrEqual(MAX_TILES);
    for (const tile of DEFAULT_TILES) expect(tile).toMatch(/^\/muppets\/[\w-]+\.avif$/);
  });
});

import { columnize } from "../../components/Backdrop";

describe("columnize", () => {
  it("round-robins tiles into four columns", () => {
    const cols = columnize(["a", "b", "c", "d", "e", "f"], 4);
    expect(cols).toEqual([["a", "e"], ["b", "f"], ["c"], ["d"]]);
  });

  it("handles fewer tiles than columns", () => {
    const cols = columnize(["a", "b"], 4);
    expect(cols.map((c) => c.length)).toEqual([1, 1, 0, 0]);
  });
});
