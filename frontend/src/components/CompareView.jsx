import AnalysisPanel from './AnalysisPanel';

export default function CompareView({
  baselineResult,
  result,
  threshold,
  overriddenId,
  onSelectInterpretation,
}) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 h-full">
      <section
        aria-label="Silent guess baseline"
        className="flex flex-col h-full bg-panel border border-line rounded-2xl overflow-hidden"
      >
        <div className="px-4 py-2.5 border-b border-line bg-ink">
          <h2 className="text-sm font-semibold text-crisp">Silent guess</h2>
          <p className="text-xs text-slate">
            Baseline prompt that picks one meaning without asking
          </p>
        </div>

        <div className="flex-1 p-4 overflow-y-auto">
          {!baselineResult ? (
            <p className="text-sm text-slate">
              Send a sentence to compare Lexi against the silent-guess baseline.
            </p>
          ) : (
            <div className="bg-ink border border-line rounded-xl p-4 space-y-2">
              <span className="inline-block text-xs uppercase tracking-wider text-slate">
                Chosen meaning
              </span>
              <p className="text-sm text-crisp leading-relaxed">
                {baselineResult.chosen_meaning}
              </p>
            </div>
          )}
        </div>
      </section>

      <div className="h-full min-h-[300px]">
        <AnalysisPanel
          result={result}
          threshold={threshold}
          overriddenId={overriddenId}
          onSelectInterpretation={onSelectInterpretation}
        />
      </div>
    </div>
  );
}
