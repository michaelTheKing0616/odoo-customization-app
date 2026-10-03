export function downloadZipBase64(tech: string, zipBase64: string) {
  const bin = atob(zipBase64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  const blob = new Blob([bytes], { type: "application/zip" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${tech || "module"}.zip`;
  a.click();
  URL.revokeObjectURL(url);
}
