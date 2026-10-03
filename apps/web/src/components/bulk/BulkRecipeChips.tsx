import { BULK_RECIPES, type BulkRecipe } from "./bulk-helpers";

export function BulkRecipeChips({
  onPick,
}: {
  onPick: (r: BulkRecipe) => void;
}) {
  return (
    <div className="mb-4 flex flex-wrap gap-2" data-testid="bulk-recipe-chips">
      {BULK_RECIPES.map((r) => (
        <button
          key={r.id}
          type="button"
          className="h-8 rounded-md border border-border-subtle bg-surface px-3 text-xs font-medium text-ink hover:border-accent/40"
          onClick={() => onPick(r)}
        >
          {r.label}
        </button>
      ))}
    </div>
  );
}
