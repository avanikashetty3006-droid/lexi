import { useState, useCallback, useRef, useEffect } from 'react';
import { analyzeStream, baseline, sendEvent } from '../api/client';

const SESSION_ID =
  typeof crypto !== 'undefined' && crypto.randomUUID
    ? crypto.randomUUID()
    : String(Date.now());

const STORAGE_KEY = 'lexi_conversations_v1';
const ACTIVE_KEY = 'lexi_active_conv_v1';
const MAX_SAVED_CONVERSATIONS = 25;

function makeConversationId() {
  return `conv-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
}

function loadSavedConversations() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function loadInitialActive(saved) {
  try {
    const storedId = localStorage.getItem(ACTIVE_KEY);
    if (storedId) {
      const found = saved.find((c) => c.id === storedId);
      if (found) return found;
    }
  } catch {
    // Ignore storage errors in restricted environments
  }
  return null;
}

function deriveTitle(msgs) {
  const firstUser = msgs.find((m) => m.role === 'user' && m.content?.trim());
  if (!firstUser) return 'New conversation';
  const text = firstUser.content.trim();
  return text.length > 48 ? `${text.slice(0, 48)}...` : text;
}

function formatStageStep(data) {
  if (!data?.step) return '';
  if (data.step === 'detecting') {
    return data.message || 'Checking ambiguity...';
  }
  if (data.step === 'resolving_anaphora') {
    return data.message || 'Running Resolver A (syntax) & Resolver B (semantics)...';
  }
  if (data.step === 'detected') {
    return data.ambiguous
      ? 'Ambiguity found — checking confidence...'
      : 'Writing reply...';
  }
  if (data.step === 'voting') {
    return data.total_samples
      ? `Voting 0/${data.total_samples}...`
      : 'Voting...';
  }
  return '';
}

export function useConversation() {
  const initialRef = useRef(null);
  if (initialRef.current === null) {
    const saved = loadSavedConversations();
    const active = loadInitialActive(saved);
    initialRef.current = {
      saved,
      active,
      activeId: active?.id || makeConversationId(),
    };
  }

  const [conversations, setConversations] = useState(
    () => initialRef.current.saved
  );
  const [activeConversationId, setActiveConversationId] = useState(
    () => initialRef.current.activeId
  );
  const [messages, setMessages] = useState(
    () => initialRef.current.active?.messages || []
  );
  const [history, setHistory] = useState(
    () => initialRef.current.active?.history || []
  );
  const [threshold, setThreshold] = useState(
    () => initialRef.current.active?.threshold ?? 0.7
  );
  const [domain, setDomain] = useState(
    () => initialRef.current.active?.domain || 'general'
  );
  const [latestResult, setLatestResult] = useState(
    () => initialRef.current.active?.latestResult || null
  );
  const [baselineResult, setBaselineResult] = useState(
    () => initialRef.current.active?.baselineResult || null
  );
  const [compareMode, setCompareMode] = useState(false);
  const [loading, setLoading] = useState(false);
  const [loadingStep, setLoadingStep] = useState('');
  const [error, setError] = useState(null);
  const [overriddenId, setOverriddenId] = useState(
    () => initialRef.current.active?.overriddenId || null
  );
  const [feedbackByMessage, setFeedbackByMessage] = useState(
    () => initialRef.current.active?.feedbackByMessage || {}
  );

  const lastPayloadRef = useRef(null);
  const lastSentenceRef = useRef(
    initialRef.current.active?.latestResult?.sentence || ''
  );

  const runAnalyze = useCallback(async (payload, { fetchBaseline = false } = {}) => {
    lastPayloadRef.current = payload;
    setLoading(true);
    setError(null);
    setLoadingStep('Checking ambiguity...');

    const msgId = `a-${Date.now()}`;
    let streamedText = '';
    let hasStreamBubble = false;

    try {
      const [result, baseRes] = await Promise.all([
        analyzeStream(payload, {
          onStage: (data) => {
            const label = formatStageStep(data);
            if (label) {
              setLoadingStep(label);
            }
          },
          onResolver: (data) => {
            const first = data?.resolutions?.[0];
            const detail = first
              ? `${first.pronoun} -> ${first.antecedent}`
              : 'done';
            if (data?.label) {
              setLoadingStep(`${data.label}: ${detail}`);
            }
          },
          onVote: (data) => {
            if (data?.completed != null && data?.total != null) {
              setLoadingStep(`Voting ${data.completed}/${data.total}...`);
            }
          },
          onToken: (data) => {
            const chunk = data?.text || '';
            if (!chunk) return;
            streamedText += chunk;
            const snapshot = streamedText;
            const creating = !hasStreamBubble;
            hasStreamBubble = true;
            setMessages((prev) =>
              creating && !prev.some((m) => m.id === msgId)
                ? [
                    ...prev,
                    { id: msgId, role: 'assistant', content: snapshot, result: null },
                  ]
                : prev.map((m) =>
                    m.id === msgId ? { ...m, content: snapshot } : m
                  )
            );
          },
        }),
        fetchBaseline ? baseline(payload.sentence) : Promise.resolve(null),
      ]);

      setLatestResult(result);
      setOverriddenId(null);
      if (baseRes) {
        setBaselineResult(baseRes);
      }

      const resolvedInterp = result.interpretations?.find(
        (i) => i.id === result.resolved_interpretation_id
      );

      let assistantText =
        resolvedInterp?.meaning ||
        result.interpretations?.[0]?.meaning ||
        streamedText ||
        'Got it.';
      if (result.needs_clarification && result.clarification_question) {
        assistantText = result.clarification_question;
      } else if (result.resolution_basis === 'clarification' && resolvedInterp) {
        assistantText = `Got it: ${resolvedInterp.meaning} (resolved by your answer)`;
      } else if (result.resolution_basis === 'context' && resolvedInterp) {
        assistantText = `Got it: ${resolvedInterp.meaning} (based on earlier in this chat)`;
      } else if (result.ambiguous && resolvedInterp) {
        assistantText = resolvedInterp.meaning;
      }

      setMessages((prev) =>
        prev.some((m) => m.id === msgId)
          ? prev.map((m) =>
              m.id === msgId ? { ...m, content: assistantText, result } : m
            )
          : [...prev, { id: msgId, role: 'assistant', content: assistantText, result }]
      );

      setHistory((prev) => [
        ...prev,
        { role: 'user', content: payload.sentence },
        { role: 'assistant', content: assistantText },
      ]);

      return result;
    } catch (err) {
      if (hasStreamBubble) {
        setMessages((prev) => prev.filter((m) => m.id !== msgId));
      }
      setError(
        err?.message || 'Could not reach the analysis service. Please try again.'
      );
      return null;
    } finally {
      setLoadingStep('');
      setLoading(false);
    }
  }, []);

  const sendSentence = useCallback(
    async (rawText) => {
      const sentence = rawText.trim();
      if (!sentence || loading) return;

      lastSentenceRef.current = sentence;
      setBaselineResult(null);

      setMessages((prev) => [
        ...prev,
        { id: `u-${Date.now()}`, role: 'user', content: sentence },
      ]);

      await runAnalyze(
        {
          sentence,
          history: history.slice(-12),
          domain,
          threshold,
        },
        { fetchBaseline: compareMode }
      );
    },
    [compareMode, domain, history, loading, runAnalyze, threshold]
  );

  const submitClarification = useCallback(
    async (question, answer) => {
      const trimmed = answer.trim();
      if (!trimmed || loading || !lastSentenceRef.current) return;

      setMessages((prev) => [
        ...prev,
        { id: `u-${Date.now()}`, role: 'user', content: trimmed },
      ]);

      await runAnalyze({
        sentence: lastSentenceRef.current,
        history: history.slice(-12),
        domain,
        threshold,
        clarification: { question, answer: trimmed },
      });
    },
    [domain, history, loading, runAnalyze, threshold]
  );

  const toggleCompareMode = useCallback(async () => {
    const next = !compareMode;
    setCompareMode(next);
    if (next && lastSentenceRef.current && !baselineResult) {
      try {
        const res = await baseline(lastSentenceRef.current);
        setBaselineResult(res);
      } catch {
        // Non-fatal if baseline fails
      }
    }
  }, [baselineResult, compareMode]);

  const overrideInterpretation = useCallback(
    (interpretationId) => {
      if (!latestResult) return;
      setOverriddenId(interpretationId);
      const chosen = latestResult.interpretations?.find(
        (i) => i.id === interpretationId
      );
      console.table([
        {
          event: 'user_override',
          sentence: latestResult.sentence,
          original_id: latestResult.resolved_interpretation_id,
          chosen_id: interpretationId,
          chosen_meaning: chosen?.meaning || '',
        },
      ]);
      sendEvent({
        event: 'override',
        session_id: SESSION_ID,
        sentence: latestResult.sentence,
        original_id: latestResult.resolved_interpretation_id,
        chosen_id: interpretationId,
        chosen_meaning: chosen?.meaning || '',
        threshold,
      });
    },
    [latestResult, threshold]
  );

  const recordFeedback = useCallback((messageId, vote) => {
    setFeedbackByMessage((prev) => ({ ...prev, [messageId]: vote }));
    console.log('[Lexi feedback]', { messageId, vote });
    sendEvent({
      event: 'feedback',
      session_id: SESSION_ID,
      message_id: String(messageId),
      vote,
      sentence: latestResult?.sentence ?? null,
      threshold,
    });
  }, [latestResult, threshold]);

  const retry = useCallback(async () => {
    if (!lastPayloadRef.current || loading) return;
    await runAnalyze(lastPayloadRef.current);
  }, [loading, runAnalyze]);

  const reanalyzeWithThreshold = useCallback(async () => {
    if (!lastSentenceRef.current || loading) return;
    sendEvent({
      event: 'slider',
      session_id: SESSION_ID,
      sentence: lastSentenceRef.current,
      threshold,
    });
    await runAnalyze(
      {
        sentence: lastSentenceRef.current,
        history: history.slice(-12),
        domain,
        threshold,
      },
      { fetchBaseline: compareMode }
    );
  }, [compareMode, domain, history, loading, runAnalyze, threshold]);

  useEffect(() => {
    try {
      localStorage.setItem(ACTIVE_KEY, activeConversationId);
    } catch {
      // Ignore storage quota or privacy-mode errors
    }
  }, [activeConversationId]);

  useEffect(() => {
    if (loading || messages.length === 0) return;
    const entry = {
      id: activeConversationId,
      title: deriveTitle(messages),
      updatedAt: Date.now(),
      messages,
      history,
      latestResult,
      baselineResult,
      overriddenId,
      feedbackByMessage,
      domain,
      threshold,
    };
    setConversations((prev) => {
      const next = [
        entry,
        ...prev.filter((c) => c.id !== activeConversationId),
      ].slice(0, MAX_SAVED_CONVERSATIONS);
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
      } catch {
        // Ignore storage quota or privacy-mode errors
      }
      return next;
    });
  }, [
    activeConversationId,
    baselineResult,
    domain,
    feedbackByMessage,
    history,
    latestResult,
    loading,
    messages,
    overriddenId,
    threshold,
  ]);

  const clearConversation = useCallback(() => {
    if (loading) return;
    setLoadingStep('');
    lastPayloadRef.current = null;
    lastSentenceRef.current = '';
    setActiveConversationId(makeConversationId());
    setMessages([]);
    setHistory([]);
    setLatestResult(null);
    setBaselineResult(null);
    setOverriddenId(null);
    setFeedbackByMessage({});
    setError(null);
    setLoading(false);
  }, [loading]);

  const selectConversation = useCallback(
    (convId) => {
      if (loading) return;
      const target = conversations.find((c) => c.id === convId);
      if (!target) return;
      setLoadingStep('');
      lastPayloadRef.current = null;
      const userMsgs = (target.messages || []).filter((m) => m.role === 'user');
      lastSentenceRef.current =
        target.latestResult?.sentence ||
        userMsgs[userMsgs.length - 1]?.content ||
        '';
      setActiveConversationId(target.id);
      setMessages(target.messages || []);
      setHistory(target.history || []);
      setLatestResult(target.latestResult || null);
      setBaselineResult(target.baselineResult || null);
      setOverriddenId(target.overriddenId || null);
      setFeedbackByMessage(target.feedbackByMessage || {});
      setDomain(target.domain || 'general');
      setThreshold(target.threshold ?? 0.7);
      setError(null);
    },
    [conversations, loading]
  );

  const deleteConversation = useCallback(
    (convId) => {
      setConversations((prev) => {
        const next = prev.filter((c) => c.id !== convId);
        try {
          localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
        } catch {
          // Ignore storage quota or privacy-mode errors
        }
        return next;
      });
      if (convId === activeConversationId) {
        setLoadingStep('');
        lastPayloadRef.current = null;
        lastSentenceRef.current = '';
        setActiveConversationId(makeConversationId());
        setMessages([]);
        setHistory([]);
        setLatestResult(null);
        setBaselineResult(null);
        setOverriddenId(null);
        setFeedbackByMessage({});
        setError(null);
        setLoading(false);
      }
    },
    [activeConversationId]
  );

  return {
    conversations,
    activeConversationId,
    messages,
    history,
    threshold,
    setThreshold,
    domain,
    setDomain,
    latestResult,
    baselineResult,
    compareMode,
    toggleCompareMode,
    loading,
    loadingStep,
    error,
    overriddenId,
    feedbackByMessage,
    sendSentence,
    submitClarification,
    overrideInterpretation,
    recordFeedback,
    retry,
    reanalyzeWithThreshold,
    clearConversation,
    selectConversation,
    deleteConversation,
  };
}
