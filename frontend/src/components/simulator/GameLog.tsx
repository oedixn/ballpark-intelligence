import type { GameLog } from '../../data/mockGame';

interface Props {
  gameLog: GameLog;
}

const resultColor = (result: string) => {
  if (result.includes('홈런')) return 'text-orange-400 font-bold';
  if (result.includes('안타') || result.includes('2루타') || result.includes('3루타')) return 'text-green-400';
  if (result.includes('볼넷') || result.includes('사구')) return 'text-blue-400';
  if (result.includes('아웃')) return 'text-gray-500';
  return 'text-gray-300';
};

const basesToString = (bases: [number, number, number]) => {
  const labels = ['1루', '2루', '3루'];
  const on = bases.map((b, i) => b ? labels[i] : null).filter(Boolean);
  return on.length === 0 ? '주자없음' : on.join('·');
};

export default function GameLogView({ gameLog }: Props) {
  return (
    <div className="bg-gray-800 rounded-xl p-6">
      <p className="text-gray-400 text-xs mb-4 uppercase tracking-widest">경기 로그</p>
      <div className="space-y-6 max-h-96 overflow-y-auto pr-2">
        {gameLog.innings.map((inning, i) => (
          <div key={i}>
            {/* 초 */}
            <div className="mb-3">
              <p className="text-blue-400 text-xs font-bold mb-2">
                {i + 1}회초 — {inning.top.team}
                <span className="text-orange-400 ml-2">{inning.top.runs}점</span>
              </p>
              <div className="space-y-1">
                {inning.top.atBats.map((ab, j) => (
                  <div key={j} className="flex items-center gap-3 text-sm">
                    <span className="text-gray-400 w-16 shrink-0">{ab.batter}</span>
                    <span className={`w-20 shrink-0 ${resultColor(ab.result)}`}>
                      {ab.result}
                    </span>
                    <span className="text-gray-600 text-xs">
                      {ab.outs}아웃 · {basesToString(ab.bases)}
                    </span>
                    {ab.runs > 0 && (
                      <span className="text-orange-400 text-xs font-bold ml-auto">
                        +{ab.runs}점 ★
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </div>

            {/* 말 */}
            <div>
              <p className="text-red-400 text-xs font-bold mb-2">
                {i + 1}회말 — {inning.bottom.team}
                <span className="text-orange-400 ml-2">{inning.bottom.runs}점</span>
              </p>
              <div className="space-y-1">
                {inning.bottom.atBats.map((ab, j) => (
                  <div key={j} className="flex items-center gap-3 text-sm">
                    <span className="text-gray-400 w-16 shrink-0">{ab.batter}</span>
                    <span className={`w-20 shrink-0 ${resultColor(ab.result)}`}>
                      {ab.result}
                    </span>
                    <span className="text-gray-600 text-xs">
                      {ab.outs}아웃 · {basesToString(ab.bases)}
                    </span>
                    {ab.runs > 0 && (
                      <span className="text-orange-400 text-xs font-bold ml-auto">
                        +{ab.runs}점 ★
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </div>

            {/* 이닝 구분선 */}
            {i < gameLog.innings.length - 1 && (
              <div className="border-b border-gray-700 mt-4" />
            )}
          </div>
        ))}
      </div>
    </div>
  );
}