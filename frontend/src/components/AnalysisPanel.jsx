import { useState } from 'react';
import SpanHighlight from './SpanHighlight';
import InterpretationCard from './InterpretationCard';
import ConfidenceBar from './ConfidenceBar';
import WhyPanel from './WhyPanel';
import MeaningMap from './MeaningMap';

const TABS = [
  { id: 'meanings', label: 'Meanings' },
  { id: 'why', label: 'Why' },
  { id: 'map', label: 'Map' },
];

export default function AnalysisPanel({
  result,
  threshold,
  overriddenId,
  onSelectInterpretation,
}) {
  const [activeTab, setActiveTab] = useState('meanings');
  const activeResolvedId = overriddenId || result?.resolved_interpretation_id;

  return (
    <section
      aria-label="Analysis"
      className="flex flex-col h-full bg-panel border border-line rounded-2xl overflow-hidden"
    >
      <div
        role="tablist"
        aria-label="Analysis views"
        className="flex items-center gap-1 p-2 border-b border-line bg-ink"
      >
        {TABS.map((tab) => {
          const selected = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              role="tab"
              type="button"
              aria-selected={selected}
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-[#6C5CE7] ${
                selected
                  ? 'bg-[#6C5CE7] text-crisp'
                  : 'text-silver hover:text-crisp hover:bg-panel'
              }`}
            >
              {tab.label}
            </button>
          );
        })}
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        {!result ? (
          <div className="h-full flex items-center justify-center text-center p-6">
            <p className="text-sm text-slate max-w-xs">
              Send a sentence in the chat to inspect possible meanings, vote
              uncertainty, and the meaning map.
            </p>
          </div>
        ) : activeTab === 'meanings' ? (
          result.ambiguous === false ? (
            <div className="space-y-4">
              <div className="rounded-xl p-4 bg-ink border border-[#10B981]">
                <div className="flex items-center gap-2 mb-2">
                  <span
                    aria-hidden="true"
                    className="inline-block w-2.5 h-2.5 rounded-full bg-[#10B981]"
                  />
                  <h3 className="text-sm font-semibold text-[#10B981]">
                    No ambiguity found
                  </h3>
                </div>
                <p className="text-sm text-crisp">
                  {result.interpretations?.[0]?.meaning || result.sentence}
                </p>
              </div>
              <div className="bg-ink border border-line rounded-xl p-4">
                <ConfidenceBar
                  confidence={result.confidence}
                  threshold={threshold}
                />
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              <SpanHighlight
                sentence={result.sentence}
                ambiguities={result.ambiguities}
              />

              <div className="bg-ink border border-line rounded-xl p-4">
                <ConfidenceBar
                  confidence={result.confidence}
                  threshold={threshold}
                />
              </div>

              <div className="space-y-2.5">
                <h3 className="text-xs font-semibold uppercase tracking-wider text-slate">
                  Possible interpretations
                </h3>
                {(result.interpretations || []).map((interp) => {
                  const sourceAmb = result.ambiguities?.[0];
                  const sourceText = sourceAmb
                    ? `${sourceAmb.type}: ${sourceAmb.explanation}`
                    : null;
                  const isSelected = activeResolvedId === interp.id;
                  const isOverridden = overriddenId === interp.id;

                  return (
                    <InterpretationCard
                      key={interp.id}
                      interpretation={interp}
                      isSelected={isSelected}
                      isOverridden={isOverridden}
                      sourceExplanation={sourceText}
                      onSelect={onSelectInterpretation}
                    />
                  );
                })}
              </div>
            </div>
          )
        ) : activeTab === 'why' ? (
          <WhyPanel result={result} threshold={threshold} />
        ) : (
          <MeaningMap
            points={result.semantic_map}
            resolvedId={activeResolvedId}
            interpretations={result.interpretations}
          />
        )}
      </div>
    </section>
  );
}
