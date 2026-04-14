import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine
} from 'recharts';

interface Props {
  onClose: () => void;
}

// 100경기 득점 분포 mock 데이터
const generateDistribution = () => {
  const data: { runs: number; count: number }[] = [];
  const dist = [1, 2, 3, 5, 8, 12, 15, 18, 16, 12, 8, 5, 3, 2, 1];
  dist.forEach((count, i) => {
    data.push({ runs: i + 1, count });
  });
  return data;
};

const data = generateDistribution();
const totalGames = data.reduce((a, b) => a + b.count, 0);
const avgRuns = (
  data.reduce((a, b) => a + b.runs * b.count, 0) / totalGames
).toFixed(1);
const wins = data.filter((d) => d.runs >= 5).reduce((a, b) => a + b.count, 0);
const winRate = ((wins / totalGames) * 100).toFixed(1);

export default function StatsModal({ onClose }: Props) {
  return (
    <div className="fixed inset-0 bg-black bg-opacity-70 flex items-center justify-center z-50 px-6">
      <div className="bg-gray-900 rounded-2xl w-full max-w-2xl p-8 border border-gray-700">

        {/* 헤더 */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-white text-2xl font-black">100경기 시뮬레이션 통계</h2>
            <p className="text-gray-400 text-sm mt-1">KIA 타이거즈 vs SSG 랜더스</p>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white text-2xl transition-colors"
          >
            ✕
          </button>
        </div>

        {/* 요약 수치 */}
        <div className="grid grid-cols-3 gap-4 mb-8">
          <div className="bg-gray-800 rounded-xl p-4 text-center">
            <p className="text-orange-400 text-3xl font-black">{avgRuns}</p>
            <p className="text-gray-400 text-xs mt-1">경기당 평균 득점</p>
          </div>
          <div className="bg-gray-800 rounded-xl p-4 text-center">
            <p className="text-orange-400 text-3xl font-black">{winRate}%</p>
            <p className="text-gray-400 text-xs mt-1">승률 (5점 이상)</p>
          </div>
          <div className="bg-gray-800 rounded-xl p-4 text-center">
            <p className="text-orange-400 text-3xl font-black">{totalGames}</p>
            <p className="text-gray-400 text-xs mt-1">시뮬레이션 횟수</p>
          </div>
        </div>

        {/* 히스토그램 */}
        <div>
          <p className="text-gray-400 text-xs mb-4 uppercase tracking-widest">득점 분포</p>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={data} margin={{ top: 0, right: 0, bottom: 0, left: -20 }}>
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
                x={Math.round(Number(avgRuns))}
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