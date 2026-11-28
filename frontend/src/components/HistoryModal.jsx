import { useEffect } from 'react';

function formatTime(ts) {
  if (!ts) return '';
  try {
    return new Date(ts).toLocaleTimeString([], {
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return '';
  }
}

export default function HistoryModal({
  open,
  onClose,
  conversations = [],
  activeId,
  onSelect,
  onDelete,
  onNewConversation,
}) {
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
      aria-labelledby="lexi-history-title"
      onClick={onClose}
      className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4"
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-lg bg-panel border border-line rounded-2xl p-6 space-y-4 max-h-[82vh] flex flex-col"
      >
        <div className="flex items-center justify-between gap-3">
          <h2
            id="lexi-history-title"
            className="text-lg font-semibold text-crisp"
          >
            Previous conversations
          </h2>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => {
                onNewConversation?.();
                onClose();
              }}
              className="px-3 py-1 rounded-lg text-xs font-medium bg-[#6C5CE7] text-crisp hover:opacity-90 focus:outline-none focus:ring-2 focus:ring-[#14B8A6]"
            >
              + New conversation
            </button>
            <button
              type="button"
              onClick={onClose}
              aria-label="Close history modal"
              className="text-sm text-silver hover:text-crisp px-2 py-1 rounded focus:outline-none focus:ring-2 focus:ring-[#6C5CE7]"
            >
              Close
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto space-y-2 pr-1">
          {conversations.length === 0 ? (
            <p className="text-sm text-slate py-8 text-center">
              No saved conversations yet. Start chatting and your sessions will
              be saved automatically here.
            </p>
          ) : (
            conversations.map((conv) => {
              const isActive = conv.id === activeId;
              const msgCount = conv.messages?.length || 0;
              return (
                <div
                  key={conv.id}
                  className={`rounded-xl border p-3 flex items-center justify-between gap-3 transition-colors ${
                    isActive
                      ? 'bg-ink border-[#6C5CE7]'
                      : 'bg-ink/70 border-line hover:border-slate'
                  }`}
                >
                  <button
                    type="button"
                    onClick={() => {
                      onSelect?.(conv.id);
                      onClose();
                    }}
                    className="flex-1 text-left focus:outline-none"
                  >
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-crisp truncate max-w-[300px]">
                        {conv.title || 'Untitled conversation'}
                      </span>
                      {isActive && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-[#6C5CE7]/25 text-crisp font-medium">
                          Current
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-slate mt-0.5">
                      {msgCount} {msgCount === 1 ? 'message' : 'messages'} ·{' '}
                      {conv.domain || 'general'}
                      {conv.updatedAt ? ` · ${formatTime(conv.updatedAt)}` : ''}
                    </p>
                  </button>

                  <button
                    type="button"
                    onClick={() => onDelete?.(conv.id)}
                    aria-label={`Delete conversation ${conv.title || ''}`}
                    className="text-xs text-slate hover:text-[#F43F5E] px-2 py-1 rounded focus:outline-none focus:ring-2 focus:ring-[#F43F5E]"
                  >
                    Delete
                  </button>
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}
