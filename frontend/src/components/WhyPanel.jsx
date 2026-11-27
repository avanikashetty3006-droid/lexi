import ConfidenceBar from './ConfidenceBar';

export default function WhyPanel({ result, threshold }) {
  const voteSplit = result?.uncertainty?.vote_split || {};
  const entries = Object.entries(voteSplit);
  const entropy = result?.uncertainty?.semantic_entropy;
  const effectiveThreshold = threshold ?? result?.threshold_used ?? 0.7;

  const topShare =
    entries.length > 0 ? Math.max(...entries.map(([, v]) => Number(v) || 0)) : 0;

  let summary = 'Confidence met your threshold, so Lexi answered.';
  if (result?.needs_clarification) {
    summary = 'Runs disagreed below your threshold, so Lexi asked.';
  } else if (topShare >= 0.99) {
    summary = 'All runs agreed, so Lexi answered.';
  }

  return (
    <div className="space-y-4">
      <div className="bg-ink border border-line rounded-xl p-4 space-y-3">
        <h3 className="text-sm font-semibold text-crisp">
          Why am I seeing this?
        </h3>
        <p className="text-sm text-silver">{summary}</p>
        <ConfidenceBar
          confidence={result?.confidence}
          threshold={effectiveThreshold}
        />
        {typeof result?.confidence === 'number' && (
          <p className="text-xs text-slate">
            With your current slider ({effectiveThreshold.toFixed(2)}), Lexi{' '}
            {result.confidence < effectiveThreshold
              ? 'asks for clarification.'
              : 'answers directly.'}
          </p>
        )}
      </div>

      <div className="bg-ink border border-line rounded-xl p-4 space-y-3">
        <h4 className="text-xs font-semibold uppercase tracking-wider text-slate">
          Vote split
        </h4>
        {entries.length === 0 ? (
          <p className="text-xs text-slate">No vote split reported.</p>
        ) : (
          <div className="space-y-2.5">
            {entries.map(([id, share]) => {
              const pct = Math.max(0, Math.min(100, Math.round(share * 100)));
              const interp = result?.interpretations?.find((i) => i.id === id);
              return (
                <div key={id} className="space-y-1">
                  <div className="flex items-center justify-between text-xs gap-2">
                    <span className="text-silver truncate">
                      <span className="font-mono text-crisp uppercase mr-1.5">
                        {id}
                      </span>
                      {interp?.meaning || ''}
                    </span>
                    <span className="font-mono text-crisp shrink-0">
                      {pct}%
                    </span>
                  </div>
                  <div className="h-2 rounded-full bg-panel border border-line overflow-hidden">
                    <div
                      className="h-full rounded-full bg-[#6C5CE7]"
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      <div className="bg-ink border border-line rounded-xl p-4 flex items-center justify-between gap-4">
        <div>
          <h4 className="text-xs font-semibold uppercase tracking-wider text-slate">
            Semantic entropy
          </h4>
          <p className="text-xs text-silver mt-1">
            Measures how spread out the sampled meanings are across runs.
          </p>
        </div>
        <span className="text-base font-mono font-semibold text-crisp shrink-0">
          {typeof entropy === 'number' ? entropy.toFixed(2) : '—'}
        </span>
      </div>

      {typeof result?.latency_ms === 'number' && (
        <p className="text-xs text-slate text-right">
          Latency: {result.latency_ms} ms
        </p>
      )}
    </div>
  );
}
