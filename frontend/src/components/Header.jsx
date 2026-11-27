import LexiLogo from './LexiLogo';
import ThresholdSlider from './ThresholdSlider';

export default function Header({
  threshold,
  onThresholdChange,
  domain,
  onDomainChange,
  compareMode,
  onToggleCompare,
  onOpenAbout,
  onNewConversation,
}) {
  return (
    <header className="px-4 py-3 border-b border-line bg-ink">
      <div className="max-w-7xl mx-auto flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <LexiLogo size={36} animated showWordmark />
          <span className="text-slate text-xs hidden sm:inline">
            Asks instead of guessing.
          </span>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          <ThresholdSlider value={threshold} onChange={onThresholdChange} />

          <div className="flex items-center gap-1.5 bg-panel border border-line rounded-xl px-2.5 py-1.5">
            <label htmlFor="lexi-domain-select" className="text-xs text-slate">
              Domain
            </label>
            <select
              id="lexi-domain-select"
              value={domain}
              onChange={(e) => onDomainChange(e.target.value)}
              className="bg-transparent text-xs text-crisp focus:outline-none focus:ring-2 focus:ring-[#6C5CE7] rounded cursor-pointer"
            >
              <option value="general" className="bg-panel text-crisp">
                general
              </option>
              <option value="requirements" className="bg-panel text-crisp">
                requirements
              </option>
            </select>
          </div>

          <button
            type="button"
            onClick={onToggleCompare}
            aria-pressed={compareMode}
            className={`px-3 py-1.5 rounded-xl text-xs font-medium border transition-colors focus:outline-none focus:ring-2 focus:ring-[#6C5CE7] ${
              compareMode
                ? 'bg-[#6C5CE7] border-[#6C5CE7] text-crisp'
                : 'bg-panel border-line text-silver hover:text-crisp'
            }`}
          >
            Compare
          </button>

          <button
            type="button"
            onClick={onOpenAbout}
            className="px-3 py-1.5 rounded-xl text-xs font-medium bg-panel border border-line text-silver hover:text-crisp focus:outline-none focus:ring-2 focus:ring-[#6C5CE7]"
          >
            How it works
          </button>

          <button
            type="button"
            onClick={onNewConversation}
            className="px-3 py-1.5 rounded-xl text-xs font-medium bg-panel border border-line text-silver hover:text-crisp focus:outline-none focus:ring-2 focus:ring-[#14B8A6]"
          >
            New conversation
          </button>
        </div>
      </div>
    </header>
  );
}
