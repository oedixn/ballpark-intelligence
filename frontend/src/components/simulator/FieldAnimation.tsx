const HOME = { x: 110, y: 195 };
const BASES = {
  '1루': { x: 165, y: 140 },
  '2루': { x: 110, y: 85 },
  '3루': { x: 55, y: 140 },
};

const BALL_TARGET: Record<string, { x: number; y: number } | null> = {
  '1B': { x: 150, y: 110 },
  '2B': { x: 180, y: 70 },
  '3B': { x: 40, y: 70 },
  'HR': { x: 110, y: -40 },
  'OUT': { x: 110, y: 165 },
  'BB': null,
};

const RUNNER_ANIM: Record<string, string> = {
  '1B': 'runTo1B',
  '2B': 'runTo2B',
  '3B': 'runTo3B',
  'HR': 'runHomeRun',
  'BB': 'runWalk',
  'OUT': 'runOutFade',
  'K': 'runStrike',
};

interface Props { event: string; }

export default function FieldAnimation({ event }: Props) {
  const ballTarget = BALL_TARGET[event] ?? null;
  const dx = ballTarget ? ballTarget.x - HOME.x : 0;
  const dy = ballTarget ? ballTarget.y - HOME.y : 0;
  const isHR  = event === 'HR';
  const isOut = event === 'OUT';
  const runnerAnim = RUNNER_ANIM[event] ?? 'runStrike';
  const runnerDuration = isHR ? '1.6s' : isOut ? '0.5s' : event === 'BB' ? '0.9s' : '0.8s';
  const runnerEasing = event === 'BB' ? 'linear' : 'ease-out';

  const d1 = { x: BASES['1루'].x - HOME.x, y: BASES['1루'].y - HOME.y };
  const d2 = { x: BASES['2루'].x - HOME.x, y: BASES['2루'].y - HOME.y };
  const d3 = { x: BASES['3루'].x - HOME.x, y: BASES['3루'].y - HOME.y };

  return (
    <div style={{ transform: 'scale(0.62)', transformOrigin: 'top left', width: 220, height: 220 }}>
      <style>{`
        @keyframes ballFly {
          0%   { transform: translate(0,0) scale(1); opacity:1; }
          45%  { transform: translate(${dx * 0.45}px, ${dy * 0.45 - 20}px) scale(1.3); opacity:1; }
          100% { transform: translate(${dx}px, ${dy}px) scale(${isOut ? 0.9 : isHR ? 0.3 : 0.7}); opacity: ${isHR ? 0 : isOut ? 0.9 : 1}; }
        }
        @keyframes runTo1B    { 0%{transform:translate(0,0)} 100%{transform:translate(${d1.x}px, ${d1.y}px)} }
        @keyframes runTo2B    { 0%{transform:translate(0,0)} 50%{transform:translate(${d1.x}px, ${d1.y}px)} 100%{transform:translate(${d2.x}px, ${d2.y}px)} }
        @keyframes runTo3B    { 0%{transform:translate(0,0)} 33%{transform:translate(${d1.x}px, ${d1.y}px)} 66%{transform:translate(${d2.x}px, ${d2.y}px)} 100%{transform:translate(${d3.x}px, ${d3.y}px)} }
        @keyframes runHomeRun { 0%{transform:translate(0,0)} 25%{transform:translate(${d1.x}px, ${d1.y}px)} 50%{transform:translate(${d2.x}px, ${d2.y}px)} 75%{transform:translate(${d3.x}px, ${d3.y}px)} 100%{transform:translate(0,0) scale(1.4)} }
        @keyframes runWalk    { 0%{transform:translate(0,0)} 100%{transform:translate(${d1.x}px, ${d1.y}px)} }
        @keyframes runOutFade { 0%{transform:translate(0,0);opacity:1} 60%{transform:translate(${d1.x * 0.55}px, ${d1.y * 0.55}px);opacity:1} 100%{opacity:0} }
        @keyframes runStrike  { 0%,100%{transform:translate(0,0) rotate(0deg)} 25%{transform:translate(-3px,0) rotate(-10deg)} 50%{transform:translate(3px,0) rotate(10deg)} 75%{transform:translate(-2px,0) rotate(-5deg)} }
        .field-ball   { animation: ballFly 0.9s ease-out forwards; transform-box: fill-box; transform-origin: center; }
        .field-runner { animation: ${runnerAnim} ${runnerDuration} ${runnerEasing} forwards; transform-box: fill-box; transform-origin: center; }
      `}</style>
      <svg viewBox="0 0 220 220" width={220} height={220}>
        <path d="M10,140 Q110,-30 210,140" fill="none" stroke="#374151" strokeWidth="2" strokeDasharray="4 4" />
        <polygon
          points={`${HOME.x},${HOME.y} ${BASES['1루'].x},${BASES['1루'].y} ${BASES['2루'].x},${BASES['2루'].y} ${BASES['3루'].x},${BASES['3루'].y}`}
          fill="none" stroke="#4b5563" strokeWidth="1.5"
        />
        <rect x={BASES['1루'].x - 6} y={BASES['1루'].y - 6} width="12" height="12" fill="#1f2937" stroke="#f97316" strokeWidth="1.2" />
        <rect x={BASES['2루'].x - 6} y={BASES['2루'].y - 6} width="12" height="12" fill="#1f2937" stroke="#f97316" strokeWidth="1.2" />
        <rect x={BASES['3루'].x - 6} y={BASES['3루'].y - 6} width="12" height="12" fill="#1f2937" stroke="#f97316" strokeWidth="1.2" />
        <rect x={HOME.x - 6} y={HOME.y - 6} width="12" height="12" fill="#000" stroke="#fff" strokeWidth="1.2" />
        <circle cx={HOME.x} cy={HOME.y} r="6" fill="#f97316" className="field-runner" />
        {ballTarget && (
          <circle cx={HOME.x} cy={HOME.y} r="5" fill="#fff" stroke="#000" strokeWidth="1" className="field-ball" />
        )}
      </svg>
    </div>
  );
}