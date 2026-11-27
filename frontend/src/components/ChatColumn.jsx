import MessageList from './MessageList';
import ChatInput from './ChatInput';

export default function ChatColumn({
  messages,
  domain,
  loading,
  loadingStep,
  error,
  feedbackByMessage,
  onSend,
  onRetry,
  onSubmitClarification,
  onFeedback,
}) {
  return (
    <section
      aria-label="Chat"
      className="flex flex-col h-full bg-ink border border-line rounded-2xl overflow-hidden"
    >
      <MessageList
        messages={messages}
        domain={domain}
        loading={loading}
        loadingStep={loadingStep}
        error={error}
        feedbackByMessage={feedbackByMessage}
        onRetry={onRetry}
        onSelectExample={onSend}
        onSubmitClarification={onSubmitClarification}
        onFeedback={onFeedback}
      />
      <ChatInput onSend={onSend} disabled={loading} />
    </section>
  );
}
