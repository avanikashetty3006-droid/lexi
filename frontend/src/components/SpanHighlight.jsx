import { useState } from 'react';
import { TYPE_STYLES } from '../theme';

function getTypeMeta(type) {
  return (
    TYPE_STYLES[type] || {
      color: '#C0C0C0',
      style: 'solid',
      label: type,
    }
  );
}

function buildSegments(sentence, ambiguities = []) {
  if (!sentence || ambiguities.length === 0) {
    return [{ text: sentence, ambiguity: null }];
  }

  const normalized = ambiguities
    .map((amb) => {
      let start = amb.start;
      let end = amb.end;
      if (
        typeof start !== 'number' ||
        typeof end !== 'number' ||
        start < 0 ||
        end <= start ||
        end > sentence.length
      ) {
        const idx = amb.span ? sentence.indexOf(amb.span) : -1;
        if (idx === -1) return null;
        start = idx;
        end = idx + amb.span.length;
      }
      return { ...amb, start, end };
    })
    .filter(Boolean)
    .sort((a, b) => a.start - b.start);

  const segments = [];
  let cursor = 0;

  for (const amb of normalized) {
    if (amb.start < cursor) continue;
    if (amb.start > cursor) {
      segments.push({ text: sentence.slice(cursor, amb.start), ambiguity: null });
    }
    segments.push({ text: sentence.slice(amb.start, amb.end), ambiguity: amb });
    cursor = amb.end;
  }

  if (cursor < sentence.length) {
    segments.push({ text: sentence.slice(cursor), ambiguity: null });
  }

  return segments;
}

export default function SpanHighlight({ sentence, ambiguities = [] }) {
  const [activeAmb, setActiveAmb] = useState(null);
  const segments = buildSegments(sentence, ambiguities);

  return (
    <div className="bg-ink border border-line rounded-xl p-4 space-y-3">
      <p className="text-base text-crisp leading-relaxed">
        {segments.map((seg, i) => {
          if (!seg.ambiguity) {
            return <span key={i}>{seg.text}</span>;
          }
          const meta = getTypeMeta(seg.ambiguity.type);
          return (
            <button
              key={i}
              type="button"
              title={seg.ambiguity.explanation}
              onMouseEnter={() => setActiveAmb(seg.ambiguity)}
              onMouseLeave={() => setActiveAmb(null)}
              onFocus={() => setActiveAmb(seg.ambiguity)}
              onBlur={() => setActiveAmb(null)}
              style={{
                textDecorationLine: 'underline',
                textDecorationColor: meta.color,
                textDecorationStyle: meta.style,
                textDecorationThickness: '2px',
                textUnderlineOffset: '5px',
              }}
              className="inline font-medium text-crisp rounded px-0.5 hover:bg-panel focus:outline-none focus:ring-2 focus:ring-[#6C5CE7]"
            >
              {seg.text}
            </button>
          );
        })}
      </p>

      {activeAmb && (
        <div
          role="status"
          className="text-xs text-silver bg-panel border border-line rounded-lg px-3 py-2"
        >
          <span className="font-semibold text-crisp capitalize">
            {activeAmb.type}:
          </span>{' '}
          {activeAmb.explanation}
        </div>
      )}

      <div
        aria-label="Ambiguity type legend"
        className="flex flex-wrap gap-x-4 gap-y-1.5 pt-2 border-t border-line"
      >
        {Object.keys(TYPE_STYLES).map((type) => {
          const meta = getTypeMeta(type);
          return (
            <span
              key={type}
              className="inline-flex items-center gap-1.5 text-xs text-silver"
            >
              <span
                aria-hidden="true"
                style={{
                  textDecorationLine: 'underline',
                  textDecorationColor: meta.color,
                  textDecorationStyle: meta.style,
                  textDecorationThickness: '2px',
                  textUnderlineOffset: '3px',
                }}
                className="font-semibold text-crisp"
              >
                Aa
              </span>
              <span>{meta.label}</span>
            </span>
          );
        })}
      </div>
    </div>
  );
}
