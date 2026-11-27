import { useState, useCallback, useRef } from 'react';
import { analyze, baseline } from '../api/client';

const LOADING_STEPS = ['Detecting...', 'Voting...', 'Mapping...'];

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
  const stepTimerRef = useRef(null);

  const startLoadingSteps = useCallback(() => {
    let idx = 0;
    setLoadingStep(LOADING_STEPS[0]);
    stepTimerRef.current = setInterval(() => {
      idx = (idx + 1) % LOADING_STEPS.length;
      setLoadingStep(LOADING_STEPS[idx]);
    }, 900);
  }, []);

  const stopLoadingSteps = useCallback(() => {
    if (stepTimerRef.current) {
      clearInterval(stepTimerRef.current);
      stepTimerRef.current = null;
    }
    setLoadingStep('');
  }, []);

  const runAnalyze = useCallback(
    async (payload, { fetchBaseline = false } = {}) => {
      lastPayloadRef.current = payload;
      setLoading(true);
      setError(null);
      startLoadingSteps();

      try {
        const [result, baseRes] = await Promise.all([
          analyze(payload),
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

        let assistantText = 'No ambiguity found.';
        if (result.needs_clarification && result.clarification_question) {
          assistantText = result.clarification_question;
        } else if (result.resolution_basis === 'clarification' && resolvedInterp) {
          assistantText = `Got it: ${resolvedInterp.meaning} (resolved by your answer)`;
        } else if (result.resolution_basis === 'context' && resolvedInterp) {
          assistantText = `Got it: ${resolvedInterp.meaning} (resolved by context)`;
        } else if (result.ambiguous && resolvedInterp) {
          assistantText = resolvedInterp.meaning;
        }

        const msgId = `a-${Date.now()}`;
        setMessages((prev) => [
          ...prev,
          {
            id: msgId,
            role: 'assistant',
            content: assistantText,
            result,
          },
        ]);

        setHistory((prev) => [
          ...prev,
          { role: 'user', content: payload.sentence },
          { role: 'assistant', content: assistantText },
        ]);

        return result;
      } catch (err) {
        setError(
          err?.message || 'Could not reach the analysis service. Please try again.'
        );
        return null;
      } finally {
        stopLoadingSteps();
        setLoading(false);
      }
    },
    [startLoadingSteps, stopLoadingSteps]
  );

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
    },
    [latestResult]
  );

  const recordFeedback = useCallback((messageId, vote) => {
    setFeedbackByMessage((prev) => ({ ...prev, [messageId]: vote }));
    console.log('[Lexi feedback]', { messageId, vote });
  }, []);

  const retry = useCallback(async () => {
    if (!lastPayloadRef.current || loading) return;
    await runAnalyze(lastPayloadRef.current);
  }, [loading, runAnalyze]);

  const clearConversation = useCallback(() => {
    stopLoadingSteps();
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
  }, [stopLoadingSteps]);

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
    clearConversation,
  };
}
