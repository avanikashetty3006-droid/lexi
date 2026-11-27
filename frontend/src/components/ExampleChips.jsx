const EXAMPLES = [
  'I saw her duck',
  'The cat sat on the mat',
  'She told her sister she was late',
  'Visit the bank',
];

export default function ExampleChips({ onSelect, disabled }) {
  return (
    <div className="flex flex-wrap justify-center gap-2.5 max-w-lg mx-auto">
      {EXAMPLES.map((sentence) => (
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
