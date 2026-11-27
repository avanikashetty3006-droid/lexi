export default function ConfidenceBar({ confidence, threshold }) {
  const confPct = Math.max(0, Math.min(100, Math.round((confidence ?? 0) * 100)));
  const threshPct = Math.max(0, Math.min(100, Math.round((threshold ?? 0.7) * 100)));

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-xs">
        <span className="text-silver">
          Confidence:{' '}
          <strong className="text-crisp font-mono">{confPct}%</strong>
        </span>
        <span className="text-slate">
          Threshold: <strong className="text-silver font-mono">{threshPct}%</strong>
        </span>
      </div>

      <div
        className="relative h-2.5 w-full rounded-full bg-ink border border-line overflow-visible"
        role="progressbar"
        aria-valuenow={confPct}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label="Model confidence"
      >
        <div
          className="h-full rounded-full transition-all duration-300"
          style={{
            width: `${confPct}%`,
            background:
              confPct >= threshPct ? '#14B8A6' : '#6C5CE7',
          }}
        />
        <div
          title={`Threshold (${threshPct}%)`}
          style={{ left: `${threshPct}%` }}
          className="absolute -top-1 -bottom-1 w-0.5 bg-crisp"
        />
      </div>
    </div>
  );
}
