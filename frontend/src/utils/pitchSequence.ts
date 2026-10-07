export type Kind = 'ball' | 'strike' | 'swing' | 'foul' | 'hit';
export interface Pitch { x: number; y: number; kind: Kind }

export const KIND: Record<Kind, { label: string; color: string }> = {
  ball:   { label: '볼',        color: '#60a5fa' },
  strike: { label: '스트라이크', color: '#f87171' },
  swing:  { label: '헛스윙',    color: '#c4b5fd' },
  foul:   { label: '파울',      color: '#facc15' },
  hit:    { label: '타격',      color: '#4ade80' },
};
export const RESULT: Record<string, string> = { '1B': '안타', '2B': '2루타', '3B': '3루타', 'HR': '홈런', 'OUT': '아웃', 'K': '삼진', 'BB': '볼넷' };

const ZX = 92, ZY = 62, ZW = 60, ZH = 80;

function makeRng(seed: string) {
  let h = 2166136261;
  for (let i = 0; i < seed.length; i++) { h ^= seed.charCodeAt(i); h = Math.imul(h, 16777619); }
  return () => {
    h = (h + 0x6d2b79f5) | 0;
    let t = Math.imul(h ^ (h >>> 15), 1 | h);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function buildSequence(event: string, seed: string): Pitch[] {
  const r = makeRng(seed);
  const at = <T,>(arr: T[]) => arr[Math.floor(r() * arr.length)];
  const inZone = () => ({ x: ZX + 5 + r() * (ZW - 10), y: ZY + 5 + r() * (ZH - 10) });
  const outZone = () => {
    const side = Math.floor(r() * 4);
    if (side === 0) return { x: 68 + r() * 18, y: 54 + r() * 96 };
    if (side === 1) return { x: 158 + r() * 18, y: 54 + r() * 96 };
    if (side === 2) return { x: 72 + r() * 100, y: 30 + r() * 22 };
    return { x: 72 + r() * 100, y: 148 + r() * 18 };
  };

  const kinds: Kind[] = [];
  let b = 0, s = 0;
  const step = (pBall: number) => {
    if (r() < pBall && b < 3) { kinds.push('ball'); b++; return; }
    if (s < 2) { kinds.push(at<Kind>(['strike', 'swing', 'foul'])); s++; return; }
    kinds.push('foul');
  };

  if (event === 'K') {
    let ended = false;
    while (kinds.length < 10) {
      if (s === 2 && r() < 0.6) { kinds.push(at<Kind>(['swing', 'strike'])); ended = true; break; }
      step(0.4);
    }
    if (!ended) kinds.push('swing');
  } else if (event === 'BB') {
    let ended = false;
    while (kinds.length < 10) {
      if (b === 3 && r() < 0.6) { kinds.push('ball'); ended = true; break; }
      step(0.55);
    }
    if (!ended) kinds.push('ball');
  } else {
    const n = Math.floor(r() * 4);
    for (let i = 0; i < n; i++) step(0.45);
    kinds.push('hit');
  }

  return kinds.map(kind => ({ kind, ...(kind === 'ball' ? outZone() : inZone()) }));
}