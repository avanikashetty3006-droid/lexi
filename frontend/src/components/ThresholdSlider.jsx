export default function ThresholdSlider({ value, onChange }) {
  return (
    <div className="flex items-center gap-2.5 bg-panel border border-line rounded-xl px-3 py-1.5">
      <label
        htmlFor="lexi-threshold-slider"
        className="text-xs text-silver whitespace-nowrap"
      >
        Ask less
      </label>
      <input
        id="lexi-threshold-slider"
        type="range"
        min="0.5"
        max="0.95"
        step="0.05"
        value={value}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        aria-label="Clarification threshold"
        className="w-24 sm:w-28 accent-[#6C5CE7] cursor-pointer focus:outline-none focus:ring-2 focus:ring-[#14B8A6] rounded"
      />
      <span className="text-xs text-silver whitespace-nowrap">Ask more</span>
      <span className="text-xs font-mono text-crisp bg-ink border border-line rounded px-1.5 py-0.5">
        {value.toFixed(2)}
      </span>
    </div>
  );
}
