import { BULK_RECIPES, type BulkRecipe } from "./bulk-helpers";

export function BulkRecipeChips({
  onPick,
}: {
  onPick: (r: BulkRecipe) => void;
}) {
  return (
    <div className="bu-recipe-row" data-testid="bulk-recipe-chips">
      {BULK_RECIPES.map((r) => (
        <button
          key={r.id}
          type="button"
          className="bu-recipe"
          onClick={() => onPick(r)}
        >
          {r.label}
        </button>
      ))}
    </div>
  );
}
