export function downloadBase64Zip(filename: string, contentBase64: string) {
  const bin = atob(contentBase64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  const blob = new Blob([bytes], { type: "application/zip" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export function buildExportOptions(input: {
  techName: string;
  displayName: string;
  installMode: "python" | "data";
  includeExtensions: boolean;
  extendModels: string;
  extraDepends: string;
  selectedDepends: string[];
}) {
  const extend = input.extendModels
    .split(/[\s,]+/)
    .map((s) => s.trim())
    .filter(Boolean);
  const freeForm = input.extraDepends
    .split(/[\s,]+/)
    .map((s) => s.trim())
    .filter(Boolean);
  const depends = Array.from(new Set([...input.selectedDepends, ...freeForm]));
  return {
    technical_name: input.techName,
    display_name: input.displayName,
    install_mode: input.installMode,
    include_extensions: input.includeExtensions,
    extend_models: extend.length ? extend : null,
    depends: depends.length ? depends : null,
  };
}
