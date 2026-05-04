import type { InningLog } from '../../api/simulatorApi';

interface Props {
  gameLog: InningLog[];
}

const eventToKorean = (event: string) => {
  const map: Record<string, string> = {
    '1B': '단타', '2B': '2루타', '3B': '3루타',
    'HR': '홈런', 'BB': '볼넷', 'OUT': '아웃',
  };
  return map[event] ?? event;
};

const resultColor = (event: string) => {
  if (event === 'HR')  return 'text-orange-400 font-bold';
  if (['1B','2B','3B'].includes(event)) return 'text-green-400';
  if (event === 'BB')  return 'text-blue-400';
  if (event === 'OUT') return 'text-gray-500';
  return 'text-gray-300';
};

export default function GameLogView({ gameLog }: Props) {
  // 초/말 묶어서 이닝별로 그룹화
  const innings: { top?: InningLog; bottom?: InningLog }[] = [];
  gameLog.forEach((log) => {
    const idx = log.inning - 1;
    if (!innings[idx]) innings[idx] = {};
    if (log.half === '초') innings[idx].top = log;
    else innings[idx].bottom = log;
  });

  return (
    <div className="bg-gray-800 rounded-xl p-6">
      <p className="text-gray-400 text-xs mb-4 uppercase tracking-widest">경기 로그</p>
      <div className="space-y-6 max-h-96 overflow-y-auto pr-2">
        {innings.map((inning, i) => (
          <div key={i}>

            {/* 초 */}
            {inning.top && (
              <div className="mb-3">
                <p className="text-blue-400 text-xs font-bold mb-2">
                  {i + 1}회초 — {inning.top.team_name}
                  <span className="text-orange-400 ml-2">{inning.top.runs}점</span>
                </p>
                <div className="space-y-1">
                  {inning.top.plate_appearances.map((pa, j) => (
                    <div key={j} className="flex items-center gap-3 text-sm">
                      <span className="text-gray-400 w-16 shrink-0">{pa.batter_name}</span>
                      <span className={`w-20 shrink-0 ${resultColor(pa.event)}`}>
                        {eventToKorean(pa.event)}
                      </span>
                      <span className="text-gray-600 text-xs">
                        {pa.outs_after}아웃 · {pa.bases_after}
                      </span>
                      {pa.runs_scored > 0 && (
                        <span className="text-orange-400 text-xs font-bold ml-auto">
                          +{pa.runs_scored}점 ★
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* 말 */}
            {inning.bottom && (
              <div>
                <p className="text-red-400 text-xs font-bold mb-2">
                  {i + 1}회말 — {inning.bottom.team_name}
                  <span className="text-orange-400 ml-2">{inning.bottom.runs}점</span>
                </p>
                <div className="space-y-1">
                  {inning.bottom.plate_appearances.map((pa, j) => (
                    <div key={j} className="flex items-center gap-3 text-sm">
                      <span className="text-gray-400 w-16 shrink-0">{pa.batter_name}</span>
                      <span className={`w-20 shrink-0 ${resultColor(pa.event)}`}>
                        {eventToKorean(pa.event)}
                      </span>
                      <span className="text-gray-600 text-xs">
                        {pa.outs_after}아웃 · {pa.bases_after}
                      </span>
                      {pa.runs_scored > 0 && (
                        <span className="text-orange-400 text-xs font-bold ml-auto">
                          +{pa.runs_scored}점 ★
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {i < innings.length - 1 && (
              <div className="border-b border-gray-700 mt-4" />
            )}
          </div>
        ))}
      </div>
    </div>
  );
}