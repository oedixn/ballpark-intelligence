const ANGLES = Array.from({ length: 14 }, (_, i) => i * 360 / 14);
const COLORS = ['#fdba74', '#f97316', '#fde68a', '#fff'];
const BURSTS = [
  { left: '25%', top: '35%' },
  { left: '50%', top: '55%' },
  { left: '72%', top: '38%' },
];

export default function Fireworks() {
  return (
    <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none', overflow: 'hidden' }}>
      <style>{`
        .firework-particle { position:absolute; width:5px; height:5px; border-radius:50%; animation: fireworkBurst 0.9s ease-out forwards; }
        @keyframes fireworkBurst {
          0%   { transform: translate(0,0) scale(1); opacity:1; }
          100% { transform: translate(var(--dx), var(--dy)) scale(0.2); opacity:0; }
        }
      `}</style>
      {BURSTS.map((pos, burstIdx) => (
        <div key={burstIdx} style={{ position: 'absolute', left: pos.left, top: pos.top }}>
          {ANGLES.map((deg, i) => {
            const rad = deg * Math.PI / 180;
            const radius = 60 + (i % 3) * 18;
            const dx = Math.cos(rad) * radius;
            const dy = Math.sin(rad) * radius;
            return (
              <span
                key={i}
                className="firework-particle"
                style={{
                  '--dx': `${dx}px`,
                  '--dy': `${dy}px`,
                  background: COLORS[i % COLORS.length],
                  animationDelay: `${burstIdx * 0.15}s`,
                } as React.CSSProperties}
              />
            );
          })}
        </div>
      ))}
    </div>
  );
}