import { useState, useCallback, useRef } from 'react';
import { analyzeStream, baseline, sendEvent } from '../api/client';

const SESSION_ID =
  typeof crypto !== 'undefined' && crypto.randomUUID
    ? crypto.randomUUID()
    : String(Date.now());

function formatStageStep(data) {
  if (!data?.step) return '';
  if (data.step === 'detecting') {
    return data.message || 'Checking ambiguity...';
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
  const [messages, setMessages] = useState([]);
  const [history, setHistory] = useState([]);
  const [threshold, setThreshold] = useState(0.7);
  const [domain, setDomain] = useState('general');
  const [latestResult, setLatestResult] = useState(null);
  const [baselineResult, setBaselineResult] = useState(null);
  const [compareMode, setCompareMode] = useState(false);
  const [loading, setLoading] = useState(false);
  const [loadingStep, setLoadingStep] = useState('');
  const [error, setError] = useState(null);
  const [overriddenId, setOverriddenId] = useState(null);
  const [feedbackByMessage, setFeedbackByMessage] = useState({});

  const lastPayloadRef = useRef(null);
  const lastSentenceRef = useRef('');

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
        assistantText = `Got it: ${resolvedInterp.meaning} (resolved by context)`;
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
          history: history.slice(-6),
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
        history: history.slice(-6),
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
        history: history.slice(-6),
        domain,
        threshold,
      },
      { fetchBaseline: compareMode }
    );
  }, [compareMode, domain, history, loading, runAnalyze, threshold]);

  const clearConversation = useCallback(() => {
    setLoadingStep('');
    lastPayloadRef.current = null;
    lastSentenceRef.current = '';
    setMessages([]);
    setHistory([]);
    setLatestResult(null);
    setBaselineResult(null);
    setOverriddenId(null);
    setFeedbackByMessage({});
    setError(null);
    setLoading(false);
  }, []);

  return {
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
  };
}
