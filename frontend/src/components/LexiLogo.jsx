export default function LexiLogo({
  size = 40,
  animated = true,
  showWordmark = false,
}) {
  return (
    <div className="inline-flex items-center gap-2.5 select-none">
      <svg
        width={size}
        height={size}
        viewBox="0 0 120 120"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        aria-label="Lexi mascot"
        className={animated ? 'overflow-visible shrink-0' : 'shrink-0'}
      >
        <style>{`
          @keyframes lexi-float {
            0%, 100% { transform: translateY(0px); }
            50% { transform: translateY(-4px); }
          }
          @keyframes lexi-twinkle {
            0%, 100% { opacity: 0.35; transform: scale(0.85); }
            50% { opacity: 1; transform: scale(1.12); }
          }
          @keyframes lexi-orbit {
            0%, 100% { stroke-dashoffset: 0; }
            50% { stroke-dashoffset: 16; }
          }
          .lexi-head {
            animation: lexi-float 3.2s ease-in-out infinite;
            transform-origin: center;
          }
          .lexi-star-1 {
            animation: lexi-twinkle 2.4s ease-in-out infinite;
            transform-origin: 94px 20px;
          }
          .lexi-star-2 {
            animation: lexi-twinkle 2.4s ease-in-out 0.9s infinite;
            transform-origin: 105px 34px;
          }
          .lexi-ring {
            stroke-dasharray: 180 14;
            animation: lexi-orbit 4s linear infinite;
          }
        `}</style>

        <defs>
          <linearGradient
            id="lexiOrbitGrad"
            x1="12"
            y1="84"
            x2="108"
            y2="48"
            gradientUnits="userSpaceOnUse"
          >
            <stop offset="0%" stopColor="#6C5CE7" />
            <stop offset="100%" stopColor="#14B8A6" />
          </linearGradient>
        </defs>

        <path
          className={animated ? 'lexi-star-1' : ''}
          d="M94 11L96.2 17.8L103 20L96.2 22.2L94 29L91.8 22.2L85 20L91.8 17.8L94 11Z"
          fill="#FFFFFF"
        />
        <path
          className={animated ? 'lexi-star-2' : ''}
          d="M105 28L106.4 32.6L111 34L106.4 35.4L105 40L103.6 35.4L99 34L103.6 32.6L105 28Z"
          fill="#FFFFFF"
        />

        <g className={animated ? 'lexi-head' : ''}>
          <line
            x1="60"
            y1="26"
            x2="60"
            y2="36"
            stroke="#6C5CE7"
            strokeWidth="4.5"
            strokeLinecap="round"
          />
          <circle cx="60" cy="21" r="6" fill="#6C5CE7" />

          <path
            d="M24 62C12 67 10 76 18 81"
            stroke="url(#lexiOrbitGrad)"
            strokeWidth="5"
            strokeLinecap="round"
          />

          <path
            d="M42 36H78C89 36 96 43 96 54V66C96 77 89 84 78 84H56L41 96V84C31 83 24 76 24 66V54C24 43 31 36 42 36Z"
            fill="#000000"
            stroke="#FFFFFF"
            strokeWidth="6"
            strokeLinejoin="round"
          />

          <path
            d="M42 61C42 56.5 49 56.5 49 61"
            stroke="#FFFFFF"
            strokeWidth="4.5"
            strokeLinecap="round"
          />
          <path
            d="M67 61C67 56.5 74 56.5 74 61"
            stroke="#FFFFFF"
            strokeWidth="4.5"
            strokeLinecap="round"
          />

          <path
            className={animated ? 'lexi-ring' : ''}
            d="M18 81C32 89 72 80 96 63C108 55 107 47 97 45"
            stroke="url(#lexiOrbitGrad)"
            strokeWidth="5.5"
            strokeLinecap="round"
          />
        </g>
      </svg>

      {showWordmark && (
        <span className="text-crisp font-bold text-xl tracking-tight leading-none inline-flex items-baseline">
          Lex
          <span className="relative inline-block">
            ı
            <span
              aria-hidden="true"
              className="absolute left-1/2 -translate-x-1/2 -top-0.5 w-1.5 h-1.5 rounded-full bg-[#6C5CE7]"
            />
          </span>
        </span>
      )}
    </div>
  );
}
