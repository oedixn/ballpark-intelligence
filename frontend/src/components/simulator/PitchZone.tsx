import { KIND, RESULT } from '../../utils/pitchSequence';
import type { Kind, Pitch } from '../../utils/pitchSequence';

const ZX = 92, ZY = 62, ZW = 60, ZH = 80;
const FLIGHT = 200;

export default function PitchZone({ event, pitches, stepMs }: { event: string; pitches: Pitch[]; stepMs: number }) {
  const n = pitches.length;
  const last = pitches[n - 1];
  const swings = last.kind === 'hit' || last.kind === 'swing';
  const at = (i: number) => i * stepMs;
  const landMs = (i: number) => at(i) + FLIGHT;

  let b = 0, s = 0;
  const rows = pitches.map((p, i) => {
    if (p.kind === 'ball') b++;
    else if (p.kind === 'strike' || p.kind === 'swing') s++;
    else if (p.kind === 'foul' && s < 2) s++;
    return { i, kind: p.kind, b, s };
  });

  return (
    <div style={{ display: 'flex', gap: '14px', alignItems: 'flex-start' }}>
      <style>{`
        @keyframes pitchIn { from { opacity:0; transform:scale(2.2); } to { opacity:1; transform:scale(1); } }
        .pitch-dot { opacity:0; transform-box:fill-box; transform-origin:center; animation: pitchIn 0.18s ease-out forwards; }
        .pitch-row { opacity:0; animation: pitchIn 0.2s ease-out forwards; transform-origin:left center; }
      `}</style>

      <div>
        <svg viewBox="0 0 190 200" width={190} height={200} role="img" aria-label="투구 위치">
          <rect x={ZX} y={ZY} width={ZW} height={ZH} fill="rgba(249,115,22,0.07)" stroke="#f97316" strokeWidth="1.5" />
          <g stroke="#f97316" strokeWidth="0.6" opacity="0.45">
            <line x1={ZX + ZW / 3} y1={ZY} x2={ZX + ZW / 3} y2={ZY + ZH} />
            <line x1={ZX + (2 * ZW) / 3} y1={ZY} x2={ZX + (2 * ZW) / 3} y2={ZY + ZH} />
            <line x1={ZX} y1={ZY + ZH / 3} x2={ZX + ZW} y2={ZY + ZH / 3} />
            <line x1={ZX} y1={ZY + (2 * ZH) / 3} x2={ZX + ZW} y2={ZY + (2 * ZH) / 3} />
          </g>
          <polygon points="107,170 137,170 137,177 122,185 107,177" fill="#e5e7eb" stroke="#6b7280" strokeWidth="1" />

          <g fill="#4b5563" stroke="#374151" strokeWidth="1">
            <circle cx="30" cy="66" r="7" />
            <rect x="23" y="75" width="15" height="32" rx="5" />
            <rect x="24" y="107" width="5" height="38" rx="2" /><rect x="32" y="107" width="5" height="38" rx="2" />
            <line x1="38" y1="84" x2="50" y2="92" strokeWidth="4" strokeLinecap="round" />
          </g>
          <line x1="50" y1="92" x2="50" y2="52" stroke="#d6a86a" strokeWidth="3.5" strokeLinecap="round">
            {swings && <animateTransform attributeName="transform" type="rotate" from="0 50 92" to="105 50 92"
              begin={`${(at(n - 1) + FLIGHT - 40) / 1000}s`} dur="0.15s" fill="freeze" />}
          </line>

          {pitches.map((p, i) => (
            <g key={i}>
              <circle r="3" fill="#fff" stroke="#111" strokeWidth="0.8" opacity="0">
                <animate attributeName="opacity" values="0;1;1;0" keyTimes="0;0.05;0.9;1" begin={`${at(i) / 1000}s`} dur={`${FLIGHT / 1000}s`} fill="freeze" />
                <animate attributeName="cx" from="122" to={p.x} begin={`${at(i) / 1000}s`} dur={`${FLIGHT / 1000}s`} fill="freeze" />
                <animate attributeName="cy" from="14" to={p.y} begin={`${at(i) / 1000}s`} dur={`${FLIGHT / 1000}s`} fill="freeze" />
                <animate attributeName="r" from="3" to="8" begin={`${at(i) / 1000}s`} dur={`${FLIGHT / 1000}s`} fill="freeze" />
              </circle>
              <g className="pitch-dot" style={{ animationDelay: `${landMs(i)}ms` }}>
                <circle cx={p.x} cy={p.y} r="9" fill={KIND[p.kind as Kind].color} stroke={i === n - 1 ? '#fff' : '#111'} strokeWidth={i === n - 1 ? 2 : 1} />
                <text x={p.x} y={p.y + 3.5} textAnchor="middle" fontSize="10" fontWeight="700" fill="#111">{i + 1}</text>
              </g>
            </g>
          ))}
        </svg>

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px 10px', maxWidth: 190, marginTop: '4px' }}>
          {(Object.keys(KIND) as Kind[]).map(k => (
            <span key={k} style={{ fontSize: '10px', color: '#9ca3af', display: 'inline-flex', alignItems: 'center', gap: '4px', fontFamily: 'inherit' }}>
              <span style={{ width: 8, height: 8, borderRadius: '50%', background: KIND[k].color, display: 'inline-block' }} />{KIND[k].label}
            </span>
          ))}
        </div>
      </div>

      <div style={{ minWidth: 150 }}>
        <p style={{ color: '#9ca3af', fontSize: '11px', marginBottom: '8px', fontFamily: 'inherit' }}>
          투구 기록
          <span className="pitch-row" style={{ animationDelay: `${landMs(n - 1) + 250}ms`, color: '#f97316', marginLeft: '8px' }}>
            {n}구 · {RESULT[event] ?? event}
          </span>
        </p>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
          {rows.map(r => (
            <div key={r.i} className="pitch-row" style={{ animationDelay: `${landMs(r.i)}ms`, display: 'flex', alignItems: 'center', gap: '8px', fontFamily: 'inherit' }}>
              <span style={{ width: 18, height: 18, borderRadius: '50%', background: KIND[r.kind].color, color: '#111', fontSize: '10px', fontWeight: 700, display: 'inline-flex', alignItems: 'center', justifyContent: 'center' }}>{r.i + 1}</span>
              <span style={{ color: '#e5e7eb', fontSize: '12px', flex: 1 }}>{KIND[r.kind].label}</span>
              <span style={{ color: '#6b7280', fontSize: '11px' }}>{r.b}-{r.s}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}