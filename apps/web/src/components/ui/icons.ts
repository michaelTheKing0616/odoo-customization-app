/** Central icon mapping — import lucide icons only from here (UIX-2). */
export {
  Brush as IconHousekeeping,
  BriefcaseBusiness as IconClient,
  Clock as IconCron,
  Combine as IconDedupe,
  FileText as IconReports,
  FileCode2 as IconQwebViews,
  Mail as IconMailTemplates,
  FlaskConical as IconSandbox,
  GitBranch as IconPipelines,
  GripVertical as IconDragHandle,
  Layers as IconBulk,
  PanelsTopLeft as IconMenus,
  Plug as IconConnection,
  Settings2 as IconConfig,
  Shield as IconAccess,
  Users as IconUsers,
  Sparkles as IconExpert,
  FilePen as IconDraftStudio,
  Upload as IconImport,
  Globe as IconWebsite,
  Code2 as IconCodeStudio,
  Undo2 as IconUndo,
  Redo2 as IconRedo,
  Search,
  Moon,
  Sun,
  Menu,
  ChevronRight,
  ChevronDown,
  ChevronUp,
  X,
  Package,
  Loader2,
  HelpCircle,
  Command,
  AlertTriangle,
  Info,
  CircleAlert,
  Copy,
  Workflow as IconPowerOps,
  Bell as IconReminders,
  Bot as IconOdooExpert,
  FolderKanban as IconProjects,
  Terminal as IconScriptRunner,
  SlidersHorizontal as IconInstanceConfig,
  Wrench as IconOperations,
  ExternalLink,
  Check,
  Lock,
  // Suite keystone set (spec 12)
  BookOpenText as IconSearchDocs,
  Scale as IconDecide,
  ScanSearch as IconInspector,
  Puzzle as IconCapability,
  ArrowRightLeft as IconTransition,
  Layers as IconMassEdit,
  Activity as IconActivity,
  DoorOpen as IconPortal,
  ShieldCheck as IconCheckChange,
  ArrowUpCircle as IconUpgrade,
  BadgeDollarSign as IconMoneyGuard,
  CalendarClock as IconSendLater,
} from "lucide-react";

import type { ComponentType } from "react";

export type IconComponent = ComponentType<{ className?: string; "aria-hidden"?: boolean }>;

/** Keystone bot signs (SPEC 20.2): stroke paths/circles drawn in the arch opening, 256 grid. */
export type KeystoneBot = "expert" | "ask" | "builder" | "inspector" | "runner" | "guard";
export type KeystoneGlyph = { paths: string[]; circles?: { cx: number; cy: number; r: number }[] };
export const KEYSTONE_ARCH =
  "M80.09 63.22A100 100 0 0 0 28 151V208H88V149A40 40 0 0 1 100.68 119.79ZM175.91 63.22A100 100 0 0 1 228 151V208H168V149A40 40 0 0 0 155.32 119.79Z";
export const KEYSTONE_STONE = "M93.8 57.03A100 100 0 0 1 162.2 57.03L142.32 111.65A40 40 0 0 0 113.68 111.65Z";
export const KEYSTONE_GLYPHS: Record<KeystoneBot, KeystoneGlyph> = {
  // Expert: three rays over the keystone, the "lit" arch.
  expert: { paths: ["M128 6V30M70 22L84 40M186 22L172 40", "M116 168L128 150L140 168L128 186Z"] },
  ask: { paths: ["M114 156A14 14 0 1 1 132 170C128 172 128 176 128 180M128 196V197"] },
  builder: { paths: ["M108 196V166H148V196M108 166L128 148L148 166"] },
  inspector: { paths: ["M136 180L150 194"], circles: [{ cx: 124, cy: 168, r: 16 }] },
  runner: { paths: ["M112 150L134 172L112 194M136 150L158 172L136 194"] },
  guard: { paths: ["M128 146L150 154V172C150 186 140 194 128 198C116 194 106 186 106 172V154Z"] },
};
export const KEYSTONE_BADGES: Record<"done" | "needs_you" | "thinking", string> = {
  done: "M6 12.5L10 16.5L18 8",
  needs_you: "M12 6V13M12 17.5V18",
  thinking: "M6 12H6.5M12 12H12.5M18 12H18.5",
};

// Touch 98: Ingenium's own icons for Odoo ideas (same grid and stroke as Lucide).
export { IngModel, IngField, IngView, IngAutomation, IngApprovalRule, IngBridgeFlow, IngNumbering, IngHistory } from "./ingeniumIcons";
// Approved swap: these app-wide names now draw Ingenium's own icons.
export {
  IngModel as IconModels,
  IngField as IconFields,
  IngView as IconViews,
  IngAutomation as IconAutomations,
  IngApprovalRule as IconApprovals,
  IngNumbering as IconIdGenerator,
  IngHistory as IconSnapshots,
  IngBridgeFlow as IconBridge,
} from "./ingeniumIcons";
