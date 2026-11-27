const MOCK_ENTRIES = {
  'i saw her duck': {
    ambiguous: true,
    confidence: 0.6,
    ambiguities: [
      {
        type: 'syntactic',
        span: 'her duck',
        start: 6,
        end: 14,
        explanation:
          '"her" can be a possessive determiner + noun ("her pet duck") or an object pronoun + verb ("her lower her head").',
      },
      {
        type: 'lexical',
        span: 'duck',
        start: 10,
        end: 14,
        explanation: '"duck" can be a waterbird (noun) or the action of crouching (verb).',
      },
    ],
    interpretations: [
      {
        id: 'i1',
        meaning: 'I saw the waterbird (duck) that belongs to her.',
        probability: 0.6,
      },
      {
        id: 'i2',
        meaning: 'I watched her crouch down quickly to avoid something.',
        probability: 0.4,
      },
    ],
    uncertainty: {
      vote_split: { i1: 0.6, i2: 0.4 },
      semantic_entropy: 0.67,
    },
    semantic_map: [
      { id: 'i1', x: -0.62, y: 0.48, label: 'Pet bird (noun)' },
      { id: 'i2', x: 0.64, y: -0.45, label: 'Crouch down (verb)' },
    ],
    clarification_question: 'Did you mean a bird she owns, or that she crouched down?',
    options: [
      'I saw the waterbird (duck) that belongs to her.',
      'I watched her crouch down quickly to avoid something.',
    ],
    baseline: {
      ambiguous: false,
      chosen_meaning: 'I saw the waterbird (duck) that belongs to her.',
    },
  },
  'the cat sat on the mat': {
    ambiguous: false,
    confidence: 1.0,
    ambiguities: [],
    interpretations: [
      {
        id: 'i1',
        meaning: 'A cat was seated on a mat.',
        probability: 1.0,
      },
    ],
    uncertainty: {
      vote_split: { i1: 1.0 },
      semantic_entropy: 0.0,
    },
    semantic_map: [{ id: 'i1', x: 0.0, y: 0.0, label: 'Cat on mat' }],
    clarification_question: null,
    options: [],
    baseline: {
      ambiguous: false,
      chosen_meaning: 'A cat was seated on a mat.',
    },
  },
  'she told her sister she was late': {
    ambiguous: true,
    confidence: 0.6,
    ambiguities: [
      {
        type: 'anaphoric',
        span: 'she',
        start: 20,
        end: 23,
        explanation: 'The second "she" could refer to the speaker or to her sister.',
      },
    ],
    interpretations: [
      {
        id: 'i1',
        meaning: 'The speaker told her sister that the speaker herself was late.',
        probability: 0.6,
      },
      {
        id: 'i2',
        meaning: 'The speaker told her sister that the sister was late.',
        probability: 0.4,
      },
    ],
    uncertainty: {
      vote_split: { i1: 0.6, i2: 0.4 },
      semantic_entropy: 0.67,
    },
    semantic_map: [
      { id: 'i1', x: -0.55, y: 0.35, label: 'Speaker was late' },
      { id: 'i2', x: 0.58, y: -0.31, label: 'Sister was late' },
    ],
    clarification_question: 'Who was late?',
    options: ['The speaker was late', 'Her sister was late'],
    baseline: {
      ambiguous: false,
      chosen_meaning: 'The speaker told her sister that the sister was late.',
    },
  },
  'visit the bank': {
    ambiguous: true,
    confidence: 0.5,
    ambiguities: [
      {
        type: 'lexical',
        span: 'bank',
        start: 10,
        end: 14,
        explanation: '"bank" can mean a financial institution or the edge of a river.',
      },
    ],
    interpretations: [
      {
        id: 'i1',
        meaning: 'Go to a financial bank (e.g., to deposit or withdraw money).',
        probability: 0.6,
      },
      {
        id: 'i2',
        meaning: 'Go to the riverbank by the water.',
        probability: 0.4,
      },
    ],
    uncertainty: {
      vote_split: { i1: 0.6, i2: 0.4 },
      semantic_entropy: 0.67,
    },
    semantic_map: [
      { id: 'i1', x: -0.7, y: 0.52, label: 'Financial bank' },
      { id: 'i2', x: 0.68, y: -0.5, label: 'Riverbank' },
    ],
    clarification_question: 'Do you mean a financial institution or a riverbank?',
    options: [
      'Go to a financial bank (e.g., to deposit or withdraw money).',
      'Go to the riverbank by the water.',
    ],
    baseline: {
      ambiguous: false,
      chosen_meaning: 'Go to a financial bank (e.g., to deposit or withdraw money).',
    },
  },
  'the system shall respond quickly': {
    ambiguous: true,
    confidence: 0.55,
    ambiguities: [
      {
        type: 'semantic',
        span: 'quickly',
        start: 25,
        end: 32,
        explanation:
          '"quickly" has no measurable latency target (e.g., <200ms vs <2s) or percentile.',
      },
    ],
    interpretations: [
      {
        id: 'i1',
        meaning: 'Respond in under 200 ms at p95 for interactive UI requests.',
        probability: 0.55,
      },
      {
        id: 'i2',
        meaning: 'Respond in under 2 seconds for background/report queries.',
        probability: 0.45,
      },
    ],
    uncertainty: {
      vote_split: { i1: 0.55, i2: 0.45 },
      semantic_entropy: 0.69,
    },
    semantic_map: [
      { id: 'i1', x: -0.58, y: 0.41, label: '<200ms p95' },
      { id: 'i2', x: 0.61, y: -0.37, label: '<2s query' },
    ],
    clarification_question: 'What latency SLA defines "quickly" here?',
    options: [
      'Respond in under 200 ms at p95 for interactive UI requests.',
      'Respond in under 2 seconds for background/report queries.',
    ],
    baseline: {
      ambiguous: false,
      chosen_meaning: 'Respond in under 200 ms at p95 for interactive UI requests.',
    },
  },
  'users can delete their own records and logs': {
    ambiguous: true,
    confidence: 0.6,
    ambiguities: [
      {
        type: 'syntactic',
        span: 'their own records and logs',
        start: 17,
        end: 43,
        explanation:
          '"their own" could scope over both records and logs, or only records (allowing deletion of all logs).',
      },
    ],
    interpretations: [
      {
        id: 'i1',
        meaning: 'Users can delete only their own records and their own logs.',
        probability: 0.6,
      },
      {
        id: 'i2',
        meaning: 'Users can delete their own records, plus system audit logs.',
        probability: 0.4,
      },
    ],
    uncertainty: {
      vote_split: { i1: 0.6, i2: 0.4 },
      semantic_entropy: 0.67,
    },
    semantic_map: [
      { id: 'i1', x: -0.64, y: 0.3, label: 'Own records + own logs' },
      { id: 'i2', x: 0.62, y: -0.44, label: 'Own records + all logs' },
    ],
    clarification_question: 'Does "their own" apply to logs as well as records?',
    options: [
      'Users can delete only their own records and their own logs.',
      'Users can delete their own records, plus system audit logs.',
    ],
    baseline: {
      ambiguous: false,
      chosen_meaning:
        'Users can delete only their own records and their own logs.',
    },
  },
  'the api must return a 200 status within 500 ms': {
    ambiguous: false,
    confidence: 1.0,
    ambiguities: [],
    interpretations: [
      {
        id: 'i1',
        meaning: 'The API endpoint must return HTTP 200 in 500 ms or less.',
        probability: 1.0,
      },
    ],
    uncertainty: {
      vote_split: { i1: 1.0 },
      semantic_entropy: 0.0,
    },
    semantic_map: [{ id: 'i1', x: 0.0, y: 0.0, label: 'HTTP 200 <= 500ms' }],
    clarification_question: null,
    options: [],
    baseline: {
      ambiguous: false,
      chosen_meaning: 'The API endpoint must return HTTP 200 in 500 ms or less.',
    },
  },
  'it must notify admins when it fails': {
    ambiguous: true,
    confidence: 0.5,
    ambiguities: [
      {
        type: 'anaphoric',
        span: 'it',
        start: 27,
        end: 29,
        explanation:
          'The second "it" could refer to the background job, the API gateway, or the notification service.',
      },
    ],
    interpretations: [
      {
        id: 'i1',
        meaning: 'Notify admins when the scheduled job fails.',
        probability: 0.5,
      },
      {
        id: 'i2',
        meaning: 'Notify admins when the payment/API request fails.',
        probability: 0.5,
      },
    ],
    uncertainty: {
      vote_split: { i1: 0.5, i2: 0.5 },
      semantic_entropy: 0.69,
    },
    semantic_map: [
      { id: 'i1', x: -0.52, y: 0.5, label: 'Scheduled job fails' },
      { id: 'i2', x: 0.54, y: -0.48, label: 'API request fails' },
    ],
    clarification_question: 'Which component does "when it fails" refer to?',
    options: [
      'Notify admins when the scheduled job fails.',
      'Notify admins when the payment/API request fails.',
    ],
    baseline: {
      ambiguous: false,
      chosen_meaning: 'Notify admins when the scheduled job fails.',
    },
  },
};

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

const CHITCHAT_REPLIES = {
  hi: "Hi! I'm Lexi. Send me any sentence or requirement and I'll check if it could mean more than one thing.",
  hello: "Hello! I'm Lexi. Type any sentence to see how I detect and clarify ambiguity.",
  hey: "Hey! Drop a sentence below and let's test it together.",
  yo: "Hey! Send a sentence whenever you're ready.",
  'good morning': 'Good morning! What sentence would you like to check?',
  'good afternoon': 'Good afternoon! What sentence would you like to check?',
  'good evening': 'Good evening! What sentence would you like to check?',
  'how are you': 'Doing great! Ready whenever you have a sentence to test.',
  thanks: "You're welcome! Send another sentence anytime.",
  'thank you': "You're welcome! Send another sentence anytime.",
  thx: "You're welcome!",
  ok: 'Sounds good—send a sentence whenever you are ready.',
  okay: 'Sounds good—send a sentence whenever you are ready.',
  yes: 'Got it! Type the next sentence whenever you are ready.',
  no: 'No problem—let me know what you would like to test next.',
  bye: 'Bye! Click "New conversation" anytime to start fresh.',
  goodbye: 'Goodbye! Click "New conversation" anytime to start fresh.',
};

function buildCleanMock(sentence, meaning) {
  return {
    ambiguous: false,
    confidence: 1.0,
    ambiguities: [],
    interpretations: [{ id: 'i1', meaning, probability: 1.0 }],
    uncertainty: { vote_split: { i1: 1.0 }, semantic_entropy: 0.0 },
    semantic_map: [{ id: 'i1', x: 0.0, y: 0.0, label: 'Clear meaning' }],
    clarification_question: null,
    options: [],
    baseline: { ambiguous: false, chosen_meaning: meaning },
  };
}

function buildGenericMock(sentence, domain) {
  const normalized = sentence.trim().toLowerCase().replace(/[.!?]+$/, '');
  if (CHITCHAT_REPLIES[normalized]) {
    return buildCleanMock(sentence, CHITCHAT_REPLIES[normalized]);
  }
  const words = sentence.trim().split(/\s+/);
  const target = words[words.length - 1]?.replace(/[.,!?]+$/, '') || sentence;
  const start = Math.max(0, sentence.lastIndexOf(target));
  const end = start + target.length;

  return {
    ambiguous: true,
    confidence: 0.6,
    ambiguities: [
      {
        type: domain === 'requirements' ? 'semantic' : 'contextual',
        span: target,
        start,
        end,
        explanation:
          domain === 'requirements'
            ? `"${target}" lacks a measurable acceptance criterion in this requirement.`
            : `"${target}" can be interpreted differently depending on context.`,
      },
    ],
    interpretations: [
      {
        id: 'i1',
        meaning: `Primary literal reading of "${sentence}".`,
        probability: 0.6,
      },
      {
        id: 'i2',
        meaning: `Alternative contextual reading of "${sentence}".`,
        probability: 0.4,
      },
    ],
    uncertainty: {
      vote_split: { i1: 0.6, i2: 0.4 },
      semantic_entropy: 0.67,
    },
    semantic_map: [
      { id: 'i1', x: -0.45, y: 0.42, label: 'Literal reading' },
      { id: 'i2', x: 0.51, y: -0.39, label: 'Contextual reading' },
    ],
    clarification_question: `Could you clarify what you mean by "${target}"?`,
    options: [
      `Primary literal reading of "${sentence}".`,
      `Alternative contextual reading of "${sentence}".`,
    ],
    baseline: {
      ambiguous: false,
      chosen_meaning: `Primary literal reading of "${sentence}".`,
    },
  };
}

export async function mockAnalyze({
  sentence,
  domain = 'general',
  threshold = 0.7,
  clarification = null,
}) {
  await delay(650);

  const key = sentence.trim().toLowerCase();
  const base = MOCK_ENTRIES[key] || buildGenericMock(sentence, domain);

  if (!base.ambiguous) {
    return {
      sentence,
      ambiguous: false,
      confidence: base.confidence,
      ambiguities: [],
      interpretations: base.interpretations,
      uncertainty: base.uncertainty,
      semantic_map: base.semantic_map,
      needs_clarification: false,
      clarification_question: null,
      options: [],
      resolved_interpretation_id: base.interpretations[0]?.id || 'i1',
      resolution_basis: 'none',
      threshold_used: threshold,
      latency_ms: 420,
    };
  }

  if (clarification?.answer) {
    const answerLower = clarification.answer.trim().toLowerCase();
    const matched = base.interpretations.find(
      (i) =>
        i.meaning.toLowerCase() === answerLower ||
        answerLower.includes(i.id.toLowerCase()) ||
        (base.options.indexOf(clarification.answer) !== -1 &&
          base.interpretations[base.options.indexOf(clarification.answer)]?.id ===
            i.id)
    );

    const interpretations = matched
      ? base.interpretations.map((i) => ({
          ...i,
          probability: i.id === matched.id ? 0.95 : 0.05,
        }))
      : [
          {
            id: 'i_custom',
            meaning: clarification.answer.trim(),
            probability: 1.0,
          },
          ...base.interpretations.map((i) => ({ ...i, probability: 0.0 })),
        ];

    const resolvedId = matched ? matched.id : 'i_custom';

    const semanticMap = matched
      ? base.semantic_map
      : [
          { id: 'i_custom', x: 0.0, y: 0.75, label: 'Your answer' },
          ...base.semantic_map,
        ];

    return {
      sentence,
      ambiguous: true,
      confidence: 0.95,
      ambiguities: base.ambiguities,
      interpretations,
      uncertainty: {
        vote_split: { [resolvedId]: 1.0 },
        semantic_entropy: 0.0,
      },
      semantic_map: semanticMap,
      needs_clarification: false,
      clarification_question: null,
      options: [],
      resolved_interpretation_id: resolvedId,
      resolution_basis: 'clarification',
      threshold_used: threshold,
      latency_ms: 510,
    };
  }

  const needsClarification = base.confidence < threshold;

  return {
    sentence,
    ambiguous: base.ambiguous,
    confidence: base.confidence,
    ambiguities: base.ambiguities,
    interpretations: base.interpretations,
    uncertainty: base.uncertainty,
    semantic_map: base.semantic_map,
    needs_clarification: needsClarification,
    clarification_question: needsClarification ? base.clarification_question : null,
    options: needsClarification ? base.options : [],
    resolved_interpretation_id: needsClarification
      ? null
      : base.interpretations[0]?.id || null,
    resolution_basis: needsClarification ? 'none' : 'context',
    threshold_used: threshold,
    latency_ms: 650,
  };
}

export async function mockBaseline(sentence) {
  await delay(250);
  const key = sentence.trim().toLowerCase();
  const base = MOCK_ENTRIES[key] || buildGenericMock(sentence, 'general');
  return base.baseline;
}
