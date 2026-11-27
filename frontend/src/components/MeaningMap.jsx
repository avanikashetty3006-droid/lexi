import { useState } from 'react';
import { INTERPRETATION_COLORS } from '../theme';

export default function MeaningMap({
  points = [],
  resolvedId,
  interpretations = [],
  onSelectInterpretation,
}) {
  const [hoveredId, setHoveredId] = useState(null);
  const [clickedId, setClickedId] = useState(null);
  const size = 340;
  const pad = 48;
  const inner = size - pad * 2;

  const toPx = (val) => {
    const clamped = Math.max(-1, Math.min(1, Number(val) || 0));
    return pad + ((clamped + 1) / 2) * inner;
  };

  const toPy = (val) => {
    const clamped = Math.max(-1, Math.min(1, Number(val) || 0));
    return pad + ((1 - clamped) / 2) * inner;
  };

  const selectedId =
    resolvedId ||
    (clickedId && points.some((p) => p.id === clickedId) ? clickedId : null);
  const activeId = hoveredId || selectedId;
  const activePoint = points.find((p) => p.id === activeId) || null;
  const activeInterp = activePoint
    ? interpretations.find((i) => i.id === activePoint.id)
    : null;

  const handleSelectVertex = (id) => {
    setClickedId(id);
    onSelectInterpretation?.(id);
  };

  return (
    <div className="space-y-3">
      <div className="bg-ink border border-line rounded-xl p-4 flex flex-col items-center space-y-3">
        {points.length === 0 ? (
          <p className="text-sm text-slate py-12">
            No meaning map coordinates returned for this sentence.
          </p>
        ) : (
          <>
            <svg
              viewBox={`0 0 ${size} ${size}`}
              className="w-full max-w-[360px] h-auto"
              role="img"
              aria-label="2D Meaning Map scatter plot with X (PCA 1) and Y (PCA 2) axes"
            >
              <line
                x1={pad}
                y1={size / 2}
                x2={size - pad}
                y2={size / 2}
                stroke="#2C2C2F"
                strokeDasharray="4 4"
              />
              <line
                x1={size / 2}
                y1={pad}
                x2={size / 2}
                y2={size - pad}
                stroke="#2C2C2F"
                strokeDasharray="4 4"
              />
              <rect
                x={pad}
                y={pad}
                width={inner}
                height={inner}
                fill="none"
                stroke="#2C2C2F"
                rx="8"
              />

              {/* X-axis ticks (-1, 0, +1) */}
              {[
                { val: -1, label: '-1.0' },
                { val: 0, label: '0' },
                { val: 1, label: '+1.0' },
              ].map((tick) => (
                <text
                  key={`x-${tick.val}`}
                  x={toPx(tick.val)}
                  y={size - pad + 14}
                  textAnchor="middle"
                  fill="#708090"
                  fontSize="9"
                >
                  {tick.label}
                </text>
              ))}

              {/* Y-axis ticks (+1, 0, -1) */}
              {[
                { val: 1, label: '+1.0' },
                { val: 0, label: '0' },
                { val: -1, label: '-1.0' },
              ].map((tick) => (
                <text
                  key={`y-${tick.val}`}
                  x={pad - 7}
                  y={toPy(tick.val) + 3}
                  textAnchor="end"
                  fill="#708090"
                  fontSize="9"
                >
                  {tick.label}
                </text>
              ))}

              {/* Axis titles */}
              <text
                x={size / 2}
                y={size - 10}
                textAnchor="middle"
                fill="#A1A1AA"
                fontSize="10"
                fontWeight="500"
              >
                X: Semantic Axis 1 (PCA 1)
              </text>
              <text
                x={14}
                y={size / 2}
                textAnchor="middle"
                fill="#A1A1AA"
                fontSize="10"
                fontWeight="500"
                transform={`rotate(-90 14 ${size / 2})`}
              >
                Y: Semantic Axis 2 (PCA 2)
              </text>

              {points.map((pt, idx) => {
                const cx = toPx(pt.x);
                const cy = toPy(pt.y);
                const color =
                  INTERPRETATION_COLORS[idx % INTERPRETATION_COLORS.length];
                const isSelected = pt.id === selectedId;
                const isHovered = pt.id === hoveredId;
                const isDimmed = Boolean(activeId) && !isSelected && !isHovered;
                const interp = interpretations.find((i) => i.id === pt.id);

                return (
                  <g
                    key={pt.id}
                    tabIndex={0}
                    role="button"
                    aria-pressed={isSelected}
                    aria-label={`${pt.label || pt.id}: ${interp?.meaning || ''}`}
                    onMouseEnter={() => setHoveredId(pt.id)}
                    onMouseLeave={() => setHoveredId(null)}
                    onFocus={() => setHoveredId(pt.id)}
                    onBlur={() => setHoveredId(null)}
                    onClick={() => handleSelectVertex(pt.id)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        handleSelectVertex(pt.id);
                      }
                    }}
                    style={{ opacity: isDimmed ? 0.35 : 1, transition: 'opacity 150ms ease' }}
                    className="cursor-pointer focus:outline-none"
                  >
                    <title>{interp?.meaning || pt.label}</title>
                    {(isSelected || isHovered) && (
                      <circle
                        cx={cx}
                        cy={cy}
                        r={14}
                        fill={color}
                        fillOpacity={0.22}
                        stroke={isSelected ? '#FFFFFF' : '#14B8A6'}
                        strokeWidth={isSelected ? '2' : '1.5'}
                        strokeDasharray={isSelected ? undefined : '3 2'}
                      />
                    )}
                    <circle
                      cx={cx}
                      cy={cy}
                      r={isSelected ? 9 : 7.5}
                      fill={color}
                      stroke={isSelected ? '#FFFFFF' : '#000000'}
                      strokeWidth={isSelected ? '2' : '1.5'}
                    />
                    {isSelected && (
                      <circle cx={cx} cy={cy} r={3} fill="#000000" />
                    )}
                    <text
                      x={cx}
                      y={cy - 17}
                      textAnchor="middle"
                      fill={isSelected ? '#FFFFFF' : '#C0C0C0'}
                      fontSize="11"
                      fontWeight={isSelected ? '700' : '400'}
                    >
                      {pt.label || pt.id}
                    </text>
                  </g>
                );
              })}
            </svg>

            {activePoint && (
              <div className="w-full bg-panel border border-[#6C5CE7]/60 rounded-lg px-3 py-2 text-xs text-silver flex items-center justify-between gap-2">
                <div>
                  <span className="font-mono text-crisp uppercase mr-1.5">
                    {activePoint.id}
                  </span>
                  {activeInterp?.meaning || activePoint.label}
                  {typeof activeInterp?.probability === 'number' && (
                    <span className="ml-2 font-mono text-[11px] text-[#14B8A6]">
                      ({Math.round(activeInterp.probability * 100)}%)
                    </span>
                  )}
                </div>
                <span className="font-mono text-[11px] text-slate shrink-0">
                  ({Number(activePoint.x ?? 0).toFixed(2)},{' '}
                  {Number(activePoint.y ?? 0).toFixed(2)})
                </span>
              </div>
            )}
          </>
        )}
      </div>

      <p className="text-xs text-slate leading-relaxed">
        2D PCA projection of sentence embeddings (MiniLM): X (PCA 1) shows the
        primary semantic difference across meanings, Y (PCA 2) shows secondary
        variation, and distance reflects how different they are.
      </p>
    </div>
  );
}
