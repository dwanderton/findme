import { describe, expect, it } from "vitest";

import { filesFromDataTransfer } from "../folder";

function fakeFile(name: string): File {
  return new File(["x"], name, { type: "image/jpeg" });
}

function fileEntry(name: string): FileSystemEntry {
  return {
    isFile: true,
    isDirectory: false,
    name,
    file: (ok: (f: File) => void) => ok(fakeFile(name)),
  } as unknown as FileSystemEntry;
}

function dirEntry(name: string, children: FileSystemEntry[], chunkSize = 100): FileSystemEntry {
  let cursor = 0;
  return {
    isFile: false,
    isDirectory: true,
    name,
    createReader: () => ({
      readEntries: (ok: (entries: FileSystemEntry[]) => void) => {
        const batch = children.slice(cursor, cursor + chunkSize);
        cursor += batch.length;
        ok(batch);
      },
    }),
  } as unknown as FileSystemEntry;
}

function fakeDataTransfer(entries: (FileSystemEntry | null)[], files: File[] = []): DataTransfer {
  return {
    items: entries.map((entry) => ({
      webkitGetAsEntry: () => entry,
      getAsFile: () => (entry && entry.isFile ? fakeFile(entry.name) : null),
    })),
    files,
  } as unknown as DataTransfer;
}

describe("filesFromDataTransfer", () => {
  it("returns plain files when nothing is a directory", async () => {
    const dt = fakeDataTransfer([fileEntry("a.jpg"), fileEntry("b.jpg")]);
    const files = await filesFromDataTransfer(dt);
    expect(files.map((f) => f.name)).toEqual(["a.jpg", "b.jpg"]);
  });

  it("walks a dropped folder recursively", async () => {
    const nested = dirEntry("day2", [fileEntry("c.jpg")]);
    const root = dirEntry("album", [fileEntry("a.jpg"), fileEntry("b.jpg"), nested]);
    const files = await filesFromDataTransfer(fakeDataTransfer([root]));
    expect(files.map((f) => f.name).sort()).toEqual(["a.jpg", "b.jpg", "c.jpg"]);
  });

  it("drains directory readers past the per-call chunk limit", async () => {
    const children = Array.from({ length: 250 }, (_, i) => fileEntry(`p${i}.jpg`));
    const root = dirEntry("big", children, 100);
    const files = await filesFromDataTransfer(fakeDataTransfer([root]));
    expect(files).toHaveLength(250);
  });

  it("mixes loose files with folder contents", async () => {
    const dt = fakeDataTransfer([fileEntry("loose.jpg"), dirEntry("dir", [fileEntry("inner.jpg")])]);
    const files = await filesFromDataTransfer(dt);
    expect(files.map((f) => f.name).sort()).toEqual(["inner.jpg", "loose.jpg"]);
  });

  it("falls back to dt.files when entries are unsupported", async () => {
    const dt = {
      items: [{ getAsFile: () => null }],
      files: [fakeFile("fallback.jpg")],
    } as unknown as DataTransfer;
    const files = await filesFromDataTransfer(dt);
    expect(files.map((f) => f.name)).toEqual(["fallback.jpg"]);
  });
});
