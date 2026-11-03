/** Resolve a drop payload into a flat file list, walking any dropped folders.
 *
 * DataTransferItem accessors are only valid synchronously inside the drop
 * handler, so entries and plain files are collected before the first await.
 * Directory readers return entries in chunks (~100), so each reader is
 * drained until it yields an empty batch.
 */
export async function filesFromDataTransfer(dt: DataTransfer): Promise<File[]> {
  const dirs: FileSystemDirectoryEntry[] = [];
  const files: File[] = [];
  for (const item of Array.from(dt.items ?? [])) {
    const entry = typeof item.webkitGetAsEntry === "function" ? item.webkitGetAsEntry() : null;
    if (entry?.isDirectory) {
      dirs.push(entry as FileSystemDirectoryEntry);
    } else {
      const file = item.getAsFile?.();
      if (file) files.push(file);
    }
  }
  if (!dirs.length && !files.length) return Array.from(dt.files ?? []);
  for (const dir of dirs) await walk(dir, files);
  return files;
}

async function walk(entry: FileSystemEntry, out: File[]): Promise<void> {
  if (entry.isFile) {
    const file = await new Promise<File | null>((resolve) =>
      (entry as FileSystemFileEntry).file(resolve, () => resolve(null)),
    );
    if (file) out.push(file);
    return;
  }
  if (!entry.isDirectory) return;
  const reader = (entry as FileSystemDirectoryEntry).createReader();
  for (;;) {
    const batch = await new Promise<FileSystemEntry[]>((resolve) =>
      reader.readEntries(resolve, () => resolve([])),
    );
    if (!batch.length) return;
    for (const child of batch) await walk(child, out);
  }
}
