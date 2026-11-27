import { useEffect } from 'react';

export default function AboutModal({ open, onClose }) {
  useEffect(() => {
    if (!open) return;
    const handleKey = (e) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="about-lexi-title"
      onClick={onClose}
      className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4"
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-lg bg-panel border border-line rounded-2xl p-6 space-y-5"
      >
        <div className="flex items-center justify-between">
          <h2 id="about-lexi-title" className="text-lg font-semibold text-crisp">
            How Lexi works
          </h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close modal"
            className="text-sm text-silver hover:text-crisp px-2 py-1 rounded focus:outline-none focus:ring-2 focus:ring-[#6C5CE7]"
          >
            Close
          </button>
        </div>

        <ol className="space-y-2 text-sm text-silver list-decimal list-inside">
          <li>
            <strong className="text-crisp">Detect:</strong> checks if your
            sentence has lexical, syntactic, semantic, contextual, or anaphoric
            ambiguity.
          </li>
          <li>
            <strong className="text-crisp">Vote:</strong> samples 5 independent
            runs to measure agreement and confidence.
          </li>
          <li>
            <strong className="text-crisp">Embed:</strong> projects candidate
            meanings into a 2D map and computes semantic entropy.
          </li>
          <li>
            <strong className="text-crisp">Decide:</strong> if confidence is
            below your threshold slider, Lexi asks a clarifying question instead
            of guessing.
          </li>
          <li>
            <strong className="text-crisp">Resolve:</strong> your answer or
            override updates the selected meaning.
          </li>
        </ol>

        <div className="space-y-2.5 pt-3 border-t border-line text-xs text-silver">
          <p>
            <strong className="text-crisp">Ambiguous:</strong> a reasonable
            reader, given the context, could pick two or more different
            meanings.
          </p>
          <p>
            <strong className="text-crisp">Correct resolution:</strong> the
            system&apos;s final meaning matches the meaning the speaker
            intended, after any clarification.
          </p>
        </div>
      </div>
    </div>
  );
}
