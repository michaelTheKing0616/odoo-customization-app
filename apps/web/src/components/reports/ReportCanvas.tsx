"use client";

export type ReportBlockType =
  | "heading"
  | "field"
  | "label_field"
  | "o2m_table"
  | "image"
  | "divider"
  | "text"
  | "page_break";

export type ReportBlock = {
  id: string;
  type: ReportBlockType;
  text?: string;
  field?: string;
  label?: string;
  o2m_field?: string;
  level?: number;
  image_src?: string;
  columns?: Array<{ field: string; label: string }>;
};

export type ReportDesignSpec = {
  name: string;
  model: string;
  report_key: string;
  use_external_layout: boolean;
  t_lang?: string | null;
  mode: "primary" | "inherit";
  inherit?: {
    base_report_key: string;
    xpath: string;
    position: "inside" | "after" | "before" | "replace";
  };
  blocks: ReportBlock[];
};

type ReportCanvasProps = {
  blocks: ReportBlock[];
  paperLabel?: string;
  useExternalLayout?: boolean;
  selectedId?: string | null;
  onSelect?: (id: string) => void;
  onMove?: (id: string, dir: -1 | 1) => void;
};

function blockPreview(block: ReportBlock): string {
  switch (block.type) {
    case "heading":
      return block.text || "Heading";
    case "field":
      return `[${block.field || "field"}]`;
    case "label_field":
      return `${block.label || "Label"}: [${block.field || "field"}]`;
    case "o2m_table":
      return `Table: ${block.o2m_field || "line_ids"}`;
    case "image":
      return block.image_src === "company_logo" ? "Company logo" : `Image: ${block.field || "?"}`;
    case "divider":
      return "— — —";
    case "page_break":
      return "— page break —";
    default:
      return block.text || "Text";
  }
}

export function ReportCanvas({
  blocks,
  paperLabel = "A4",
  useExternalLayout = true,
  selectedId,
  onSelect,
  onMove,
}: ReportCanvasProps) {
  return (
    <div className="mx-auto max-w-[210mm] border border-[#3d2a38] bg-white text-[#1a1218] shadow-lg">
      {useExternalLayout && (
        <div className="border-b border-dashed border-[#ccc] bg-[#f8f4f6] px-6 py-3 text-xs text-[#714B67]">
          web.external_layout — header / footer placeholder ({paperLabel})
        </div>
      )}
      <div className="min-h-[240mm] px-10 py-8">
        {blocks.length === 0 && (
          <p className="text-center text-sm text-[#888]">
            Add blocks from the palette — visual first, QWeb code in the Code tab.
          </p>
        )}
        {blocks.map((block) => {
          const selected = selectedId === block.id;
          return (
            <div
              key={block.id}
              className={`group relative mb-3 rounded border px-3 py-2 ${
                selected ? "border-[#714B67] bg-[#fdf8fb]" : "border-transparent hover:border-[#ddd]"
              }`}
              onClick={() => onSelect?.(block.id)}
              onKeyDown={(e) => {
                if (e.key === "Enter") onSelect?.(block.id);
              }}
              role="button"
              tabIndex={0}
            >
              {block.type === "heading" && (
                <div
                  className="font-semibold text-[#714B67]"
                  style={{ fontSize: block.level === 1 ? "1.25rem" : "1rem" }}
                >
                  {blockPreview(block)}
                </div>
              )}
              {block.type === "divider" && <hr className="border-[#ccc]" />}
              {block.type === "page_break" && (
                <p className="text-center text-xs text-[#999]">{blockPreview(block)}</p>
              )}
              {block.type === "o2m_table" && (
                <table className="w-full border-collapse text-xs">
                  <thead>
                    <tr className="border-b bg-[#f5f5f5]">
                      {(block.columns || [{ field: "name", label: "Line" }]).map((c) => (
                        <th key={c.field} className="px-2 py-1 text-left">
                          {c.label}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td colSpan={(block.columns || []).length || 1} className="px-2 py-2 text-[#888]">
                        … lines from {block.o2m_field || "line_ids"} …
                      </td>
                    </tr>
                  </tbody>
                </table>
              )}
              {!["heading", "divider", "page_break", "o2m_table"].includes(block.type) && (
                <p className="text-sm">{blockPreview(block)}</p>
              )}
              {onMove && (
                <div className="absolute right-1 top-1 hidden gap-1 group-hover:flex">
                  <button
                    type="button"
                    className="rounded bg-[#eee] px-1 text-xs"
                    onClick={(e) => {
                      e.stopPropagation();
                      onMove(block.id, -1);
                    }}
                  >
                    ↑
                  </button>
                  <button
                    type="button"
                    className="rounded bg-[#eee] px-1 text-xs"
                    onClick={(e) => {
                      e.stopPropagation();
                      onMove(block.id, 1);
                    }}
                  >
                    ↓
                  </button>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export const RENTAL_AGREEMENT_STARTER: ReportBlock[] = [
  { id: "h1", type: "heading", text: "Rental Agreement", level: 1 },
  { id: "logo", type: "image", image_src: "company_logo" },
  { id: "cust", type: "label_field", label: "Customer", field: "partner_id" },
  { id: "veh", type: "label_field", label: "Vehicle", field: "vehicle_id" },
  { id: "dates", type: "label_field", label: "Period", field: "date_start" },
  { id: "lines", type: "o2m_table", o2m_field: "line_ids", columns: [
    { field: "product_id", label: "Item" },
    { field: "price_unit", label: "Rate" },
  ]},
  { id: "sig", type: "text", text: "Signed: _________________________" },
];
