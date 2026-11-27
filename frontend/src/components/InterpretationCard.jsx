export default function InterpretationCard({
  interpretation,
  isSelected,
  isOverridden,
  sourceExplanation,
  onSelect,
}) {
  const pct =
    typeof interpretation.probability === 'number'
      ? `${Math.round(interpretation.probability * 100)}%`
      : null;

  return (
    <button
      type="button"
      onClick={() => onSelect?.(interpretation.id)}
      aria-pressed={isSelected}
      className={`w-full text-left rounded-xl p-3.5 border transition-colors focus:outline-none focus:ring-2 focus:ring-[#6C5CE7] ${
        isSelected
          ? 'bg-ink border-[#6C5CE7] ring-1 ring-[#6C5CE7]'
          : 'bg-ink border-line hover:border-slate'
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <p className="text-sm font-medium text-crisp leading-snug">
          {interpretation.meaning}
        </p>
        {pct !== null && (
          <span className="shrink-0 text-xs font-semibold px-2 py-0.5 rounded-full bg-panel border border-line text-silver">
            {pct}
          </span>
        )}
      </div>

      {sourceExplanation && (
        <p className="mt-1.5 text-xs text-silver">{sourceExplanation}</p>
      )}

      <div className="mt-2 flex items-center justify-between text-xs gap-2">
        <span className="text-slate uppercase tracking-wide">
          {interpretation.id}
        </span>

        <div className="flex items-center gap-2">
          {isOverridden && (
            <span className="px-2 py-0.5 rounded-full bg-[#6C5CE7]/20 border border-[#6C5CE7] text-crisp">
              you corrected Lexi
            </span>
          )}
          {isSelected ? (
            <span className="text-[#14B8A6] font-medium">Selected meaning</span>
          ) : (
            <span className="text-slate">Click if this is what you meant</span>
          )}
        </div>
      </div>
    </button>
  );
}
