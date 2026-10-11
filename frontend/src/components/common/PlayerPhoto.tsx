import { useEffect, useState } from 'react';

export default function PlayerPhoto({ playerId, fallback, size = 48, className = '', fallbackClass = 'bg-gray-700' }: {
  playerId?: string | number; fallback: string; size?: number; className?: string; fallbackClass?: string;
}) {
  const [broken, setBroken] = useState(false);
  useEffect(() => { setBroken(false); }, [playerId]);
  const box = { width: size, height: size };
  if (playerId && !broken) {
    return <img src={`/players/${playerId}.jpg`} alt="" style={box} onError={() => setBroken(true)}
      className={`rounded-full object-cover object-top shrink-0 border border-gray-700 ${className}`} />;
  }
  return (
    <div style={box} className={`rounded-full ${fallbackClass} flex items-center justify-center text-white font-bold shrink-0 ${className}`}>
      <span style={{ fontSize: size * 0.38 }}>{fallback}</span>
    </div>
  );
}
