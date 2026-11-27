import { INTERPRETATION_COLORS } from '../theme';

export default function MeaningMap({
  points = [],
  resolvedId,
  interpretations = [],
}) {
  const size = 320;
  const pad = 36;
  const inner = size - pad * 2;

  const toPx = (val) => {
    const clamped = Math.max(-1, Math.min(1, Number(val) || 0));
    return pad + ((clamped + 1) / 2) * inner;
  };

  const toPy = (val) => {
    const clamped = Math.max(-1, Math.min(1, Number(val) || 0));
    return pad + ((1 - clamped) / 2) * inner;
  };

  return (
    <div className="space-y-3">
      <div className="bg-ink border border-line rounded-xl p-4 flex flex-col items-center">
        {points.length === 0 ? (
          <p className="text-sm text-slate py-12">
            No meaning map coordinates returned for this sentence.
          </p>
        ) : (
          <svg
            viewBox={`0 0 ${size} ${size}`}
            className="w-full max-w-[340px] h-auto"
            role="img"
            aria-label="2D Meaning Map scatter plot"
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

            {points.map((pt, idx) => {
              const cx = toPx(pt.x);
              const cy = toPy(pt.y);
              const color =
                INTERPRETATION_COLORS[idx % INTERPRETATION_COLORS.length];
              const isResolved = pt.id === resolvedId;
              const interp = interpretations.find((i) => i.id === pt.id);

              return (
                <g key={pt.id}>
                  <title>{interp?.meaning || pt.label}</title>
                  {isResolved && (
                    <circle
                      cx={cx}
                      cy={cy}
                      r={13}
                      fill="none"
                      stroke="#FFFFFF"
                      strokeWidth="2"
                      strokeDasharray="3 2"
                    />
                  )}
                  <circle
                    cx={cx}
                    cy={cy}
                    r={7}
                    fill={color}
                    stroke="#000000"
                    strokeWidth="1.5"
                  />
                  <text
                    x={cx}
                    y={cy - 14}
                    textAnchor="middle"
                    fill="#FFFFFF"
                    fontSize="11"
                    fontWeight={isResolved ? '600' : '400'}
                  >
                    {pt.label || pt.id}
                  </text>
                </g>
              );
            })}
          </svg>
        )}
      </div>

      <p className="text-xs text-slate leading-relaxed">
        Illustrative projection. Each dot is one possible meaning; distance
        suggests how different they are; axes are arbitrary.
      </p>
    </div>
  );
}
