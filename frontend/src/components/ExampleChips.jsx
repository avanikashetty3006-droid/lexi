const GENERAL_EXAMPLES = [
  'I saw her duck',
  'The cat sat on the mat',
  'She told her sister she was late',
  'Visit the bank',
];

const REQUIREMENTS_EXAMPLES = [
  'The system shall respond quickly',
  'Users can delete their own records and logs',
  'The API must return a 200 status within 500 ms',
  'It must notify admins when it fails',
];

export default function ExampleChips({ domain = 'general', onSelect, disabled }) {
  const examples =
    domain === 'requirements' ? REQUIREMENTS_EXAMPLES : GENERAL_EXAMPLES;

  return (
    <div className="flex flex-wrap justify-center gap-2.5 max-w-lg mx-auto">
      {examples.map((sentence) => (
        <button
          key={sentence}
          type="button"
          disabled={disabled}
          onClick={() => onSelect(sentence)}
          className="px-3.5 py-2 rounded-full bg-panel border border-line text-sm text-silver hover:text-crisp hover:border-[#6C5CE7] focus:outline-none focus:ring-2 focus:ring-[#6C5CE7] transition-colors disabled:opacity-50"
        >
          {sentence}
        </button>
      ))}
    </div>
  );
}
