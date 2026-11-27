import { useEffect, useRef } from 'react';
import LexiLogo from './LexiLogo';
import ExampleChips from './ExampleChips';
import ClarifyPrompt from './ClarifyPrompt';

export default function MessageList({
  messages,
  domain,
  loading,
  loadingStep,
  error,
  feedbackByMessage,
  onRetry,
  onSelectExample,
  onSubmitClarification,
  onFeedback,
}) {
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading, error]);

  if (messages.length === 0 && !loading && !error) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center p-6 text-center">
        <div className="mb-4">
          <LexiLogo size={72} animated />
        </div>
        <h2 className="text-xl font-semibold text-crisp mb-1">
          Test a sentence with Lexi
        </h2>
        <p className="text-sm text-silver max-w-md mb-6">
          Type any sentence below or pick an example. Lexi checks for ambiguity
          and asks instead of guessing.
        </p>
        <ExampleChips domain={domain} onSelect={onSelectExample} disabled={loading} />
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-3">
      {messages.map((msg, idx) => {
        const isUser = msg.role === 'user';
        const isLatest = idx === messages.length - 1;
        const needsClarify =
          !isUser && msg.result?.needs_clarification && isLatest;

        return (
          <div
            key={msg.id}
            className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-[88%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
                isUser
                  ? 'bg-[#6C5CE7] text-crisp rounded-br-sm'
                  : 'bg-panel border border-line text-silver rounded-bl-sm'
              }`}
            >
              <p>{msg.content}</p>

              {needsClarify && (
                <ClarifyPrompt
                  messageId={msg.id}
                  question={msg.result.clarification_question}
                  options={msg.result.options}
                  disabled={loading}
                  currentVote={feedbackByMessage?.[msg.id]}
                  onSubmitAnswer={onSubmitClarification}
                  onVote={onFeedback}
                />
              )}
            </div>
          </div>
        );
      })}

      {loading && (
        <div className="flex justify-start" role="status" aria-live="polite">
          <div className="flex items-center gap-2.5 bg-panel border border-line rounded-2xl rounded-bl-sm px-4 py-2.5 text-sm text-silver">
            <span className="inline-block w-2 h-2 rounded-full bg-[#14B8A6] animate-pulse" />
            <span>{loadingStep || 'Detecting... voting... mapping...'}</span>
          </div>
        </div>
      )}

      {error && (
        <div
          role="alert"
          className="bg-panel border border-[#F43F5E]/60 rounded-xl p-3.5 text-sm text-silver flex items-center justify-between gap-3"
        >
          <span>{error}</span>
          <button
            type="button"
            onClick={onRetry}
            className="shrink-0 px-3 py-1.5 rounded-lg bg-[#6C5CE7] text-crisp text-xs font-medium hover:opacity-90 focus:outline-none focus:ring-2 focus:ring-[#14B8A6]"
          >
            Retry
          </button>
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  );
}
