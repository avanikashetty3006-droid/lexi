import { useState } from 'react';

export default function ChatInput({ onSend, disabled }) {
  const [text, setText] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    const trimmed = text.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setText('');
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="p-3 border-t border-line bg-ink flex items-center gap-2.5"
    >
      <label htmlFor="lexi-chat-input" className="sr-only">
        Type a sentence to analyze
      </label>
      <input
        id="lexi-chat-input"
        type="text"
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Type a sentence (e.g. I saw her duck)..."
        disabled={disabled}
        className="flex-1 bg-panel border border-line rounded-xl px-4 py-2.5 text-sm text-crisp placeholder:text-slate focus:outline-none focus:ring-2 focus:ring-[#6C5CE7] disabled:opacity-50"
      />
      <button
        type="submit"
        disabled={disabled || !text.trim()}
        className="px-4 py-2.5 rounded-xl bg-[#6C5CE7] text-crisp text-sm font-medium hover:opacity-90 focus:outline-none focus:ring-2 focus:ring-[#14B8A6] disabled:opacity-40 disabled:cursor-not-allowed transition-opacity"
      >
        Send
      </button>
    </form>
  );
}
