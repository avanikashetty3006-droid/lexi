export default function FeedbackButtons({ messageId, currentVote, onVote }) {
  return (
    <div className="flex items-center gap-2 pt-2 border-t border-line/70 text-xs text-slate">
      <span>Was this question needed?</span>
      <button
        type="button"
        aria-label="Thumbs up — question was helpful"
        aria-pressed={currentVote === 'up'}
        onClick={() => onVote(messageId, 'up')}
        className={`px-2 py-0.5 rounded border transition-colors focus:outline-none focus:ring-2 focus:ring-[#6C5CE7] ${
          currentVote === 'up'
            ? 'bg-[#14B8A6]/20 border-[#14B8A6] text-crisp'
            : 'bg-ink border-line text-silver hover:text-crisp'
        }`}
      >
        👍
      </button>
      <button
        type="button"
        aria-label="Thumbs down — question was not needed"
        aria-pressed={currentVote === 'down'}
        onClick={() => onVote(messageId, 'down')}
        className={`px-2 py-0.5 rounded border transition-colors focus:outline-none focus:ring-2 focus:ring-[#6C5CE7] ${
          currentVote === 'down'
            ? 'bg-[#F43F5E]/20 border-[#F43F5E] text-crisp'
            : 'bg-ink border-line text-silver hover:text-crisp'
        }`}
      >
        👎
      </button>
    </div>
  );
}
