import { useState } from 'react';
import FeedbackButtons from './FeedbackButtons';

export default function ClarifyPrompt({
  messageId,
  question,
  options = [],
  disabled,
  currentVote,
  onSubmitAnswer,
  onVote,
}) {
  const [showCustom, setShowCustom] = useState(false);
  const [customText, setCustomText] = useState('');

  const handleCustomSubmit = (e) => {
    e.preventDefault();
    const trimmed = customText.trim();
    if (!trimmed || disabled) return;
    onSubmitAnswer(question, trimmed);
    setCustomText('');
    setShowCustom(false);
  };

  return (
    <div className="mt-2.5 space-y-2.5">
      <div className="flex flex-wrap gap-2">
        {options.map((opt) => (
          <button
            key={opt}
            type="button"
            disabled={disabled}
            onClick={() => onSubmitAnswer(question, opt)}
            className="text-left text-xs px-3 py-1.5 rounded-lg bg-ink border border-line text-crisp hover:border-[#6C5CE7] focus:outline-none focus:ring-2 focus:ring-[#6C5CE7] disabled:opacity-50"
          >
            {opt}
          </button>
        ))}

        <button
          type="button"
          disabled={disabled}
          onClick={() => setShowCustom((prev) => !prev)}
          className="text-xs px-3 py-1.5 rounded-lg bg-ink border border-line text-silver hover:text-crisp hover:border-[#14B8A6] focus:outline-none focus:ring-2 focus:ring-[#14B8A6] disabled:opacity-50"
        >
          None of these
        </button>
      </div>

      {showCustom && (
        <form onSubmit={handleCustomSubmit} className="flex gap-2">
          <label htmlFor={`clarify-custom-${messageId}`} className="sr-only">
            Describe what you meant
          </label>
          <input
            id={`clarify-custom-${messageId}`}
            type="text"
            value={customText}
            onChange={(e) => setCustomText(e.target.value)}
            placeholder="Type what you meant..."
            disabled={disabled}
            className="flex-1 bg-ink border border-line rounded-lg px-3 py-1.5 text-xs text-crisp placeholder:text-slate focus:outline-none focus:ring-2 focus:ring-[#6C5CE7]"
          />
          <button
            type="submit"
            disabled={disabled || !customText.trim()}
            className="px-3 py-1.5 rounded-lg bg-[#6C5CE7] text-crisp text-xs font-medium hover:opacity-90 focus:outline-none focus:ring-2 focus:ring-[#14B8A6] disabled:opacity-40"
          >
            Submit
          </button>
        </form>
      )}

      <FeedbackButtons
        messageId={messageId}
        currentVote={currentVote}
        onVote={onVote}
      />
    </div>
  );
}
