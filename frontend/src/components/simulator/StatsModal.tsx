import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine,
} from 'recharts';
import type { MultiSimulateResponse } from '../../api/simulatorApi';

interface Props {
  onClose: () => void;
  stats: MultiSimulateResponse;
}

export default function StatsModal({ onClose, stats }: Props) {
  const { team_a, team_b, n_games } = stats;

  // 득점 분포 히스토그램용 데이터 (정규분포 근사)
  const generateDist = (mean: number, variance: number) => {
    const std = Math.sqrt(variance);
    if (!std) return Array.from({length:15},(_,i)=>({runs:i+1,count:i+1===Math.round(mean)?n_games:0}));
    return Array.from({ length: 15 }, (_, i) => {
      const x = i + 1;
      const count = Math.round(
        n_games * (1 / (std * Math.sqrt(2 * Math.PI))) *
        Math.exp(-0.5 * Math.pow((x - mean) / std, 2))
      );
      return { runs: x, count: Math.max(count, 0) };
    });
  };

  const distA = stats.score_distribution
    ? Object.entries(stats.score_distribution.reduce<Record<number,number>>((counts,r)=>{
        counts[r.team_a_score]=(counts[r.team_a_score]??0)+r.count; return counts;
      },{})).map(([runs,count])=>({runs:Number(runs),count})).sort((a,b)=>a.runs-b.runs)
    : generateDist(team_a.mean_runs, team_a.variance);

  return (
    <div className="fixed inset-0 bg-black bg-opacity-70 flex items-center justify-center z-50 px-6">
      <div className="bg-gray-900 rounded-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto p-8 border border-gray-700">

        {/* 헤더 */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-white text-2xl font-black">{n_games}경기 시뮬레이션 통계</h2>
            <p className="text-gray-400 text-sm mt-1">
              {team_a.name} vs {team_b.name}
            </p>
            {stats.metadata && <p className="text-blue-400 text-xs mt-2">
              {stats.metadata.season}년 · {stats.metadata.as_of} 이전 기록 · 마지막 경기 {stats.metadata.last_game_date} · seed {stats.metadata.seed}
            </p>}
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white text-2xl transition-colors"
          >
            ✕
          </button>
        </div>

        {stats.bullpen?.enabled && <p className="text-orange-300 text-xs mb-4">
          중계·마무리 자동 교체 켬 · 기본 운용 규칙 · 마르코프 수치는 선발 고정 기준
        </p>}

        {stats.matchup && <div className="grid grid-cols-3 gap-3 mb-5 text-center text-sm">
          <div>{team_a.name} 승률<br/><strong className="text-green-400">{stats.matchup.team_a_win_rate===null?'-':`${(stats.matchup.team_a_win_rate*100).toFixed(1)}%`}</strong></div>
          <div>무승부<br/><strong className="text-yellow-400">{(stats.matchup.draw_probability*100).toFixed(1)}%</strong></div>
          <div>{team_b.name} 승률<br/><strong className="text-green-400">{stats.matchup.team_b_win_rate===null?'-':`${(stats.matchup.team_b_win_rate*100).toFixed(1)}%`}</strong></div>
          <p className="col-span-3 text-gray-500 text-xs">승률은 무승부 제외 · 그래프는 실제 반복 결과</p>
        </div>}

        {/* 팀별 요약 */}
        <div className="grid grid-cols-2 gap-4 mb-6">
          {[team_a, team_b].map((team) => (
            <div key={team.name} className="bg-gray-800 rounded-xl p-4">
              <p className="text-white font-bold text-sm mb-3">{team.name}</p>
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span className="text-gray-400">{stats.bullpen?.enabled ? '선발 고정 기대득점' : '마르코프 기대득점'}</span>
                  <span className="text-orange-400 font-bold">
                    {team.markov_expected.toFixed(2)}
                  </span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-400">몬테카를로 평균</span>
                  <span className="text-orange-400 font-bold">
                    {team.mean_runs.toFixed(2)}
                  </span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-400">5점 이상 확률</span>
                  <span className="text-blue-400 font-bold">
                    {(team.prob_5_or_more * 100).toFixed(1)}%
                  </span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-400">0점 확률</span>
                  <span className="text-red-400 font-bold">
                    {(team.prob_0_runs * 100).toFixed(1)}%
                  </span>
                </div>
              </div>
              {stats.bullpen?.usage?.[team.name] && <p className="text-blue-300 text-xs mt-3">
                경기당 투수 {stats.bullpen.usage[team.name].mean_pitchers.toFixed(1)}명 · 선발 평균 {stats.bullpen.usage[team.name].mean_starter_innings.toFixed(2)}이닝
              </p>}
            </div>
          ))}
        </div>

        {/* 요약 수치 */}
        <div className="grid grid-cols-3 gap-4 mb-6">
          <div className="bg-gray-800 rounded-xl p-4 text-center">
            <p className="text-orange-400 text-3xl font-black">
              {team_a.mean_runs.toFixed(1)}
            </p>
            <p className="text-gray-400 text-xs mt-1">{team_a.name} 평균 득점</p>
          </div>
          <div className="bg-gray-800 rounded-xl p-4 text-center">
            <p className="text-orange-400 text-3xl font-black">
              {(team_a.prob_5_or_more * 100).toFixed(1)}%
            </p>
            <p className="text-gray-400 text-xs mt-1">5점 이상 득점 확률</p>
          </div>
          <div className="bg-gray-800 rounded-xl p-4 text-center">
            <p className="text-orange-400 text-3xl font-black">{n_games}</p>
            <p className="text-gray-400 text-xs mt-1">시뮬레이션 횟수</p>
          </div>
        </div>

        {/* 히스토그램 */}
        <div>
          <p className="text-gray-400 text-xs mb-4 uppercase tracking-widest">
            {team_a.name} 득점 분포
          </p>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={distA} margin={{ top: 0, right: 0, bottom: 0, left: -20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis
                dataKey="runs"
                tick={{ fill: '#9CA3AF', fontSize: 11 }}
                label={{ value: '득점', position: 'insideBottom', offset: -2, fill: '#6B7280', fontSize: 11 }}
              />
              <YAxis tick={{ fill: '#9CA3AF', fontSize: 11 }} />
              <Tooltip
                contentStyle={{ backgroundColor: '#1F2937', border: '1px solid #374151', borderRadius: '8px' }}
                labelStyle={{ color: '#F97316' }}
                labelFormatter={(v) => `${v}점`}
                formatter={(v) => [`${v}회`, '경기 수']}
              />
              <ReferenceLine
                x={Math.round(team_a.mean_runs)}
                stroke="#F97316"
                strokeDasharray="4 4"
                label={{ value: '평균', fill: '#F97316', fontSize: 11 }}
              />
              <Bar dataKey="count" fill="#F97316" fillOpacity={0.8} radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

      </div>
    </div>
  );
}
