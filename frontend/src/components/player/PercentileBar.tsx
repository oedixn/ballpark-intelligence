interface Props {
  label: string;
  value: number;      // 실제 수치 (예: 0.380)
  percentile: number; // 0 ~ 100
  unit?: string;      // 표시 단위 (예: "wOBA")
}

export default function PercentileBar({ label, value, percentile, unit }: Props) {
  const getColor = (p: number) => {
    if (p >= 80) return 'bg-orange-500';
    if (p >= 60) return 'bg-yellow-400';
    if (p >= 40) return 'bg-green-400';
    if (p >= 20) return 'bg-blue-400';
    return 'bg-gray-400';
  };

  return (
    <div className="flex items-center gap-3 py-2">
      {/* 라벨 */}
      <span className="w-20 text-sm text-gray-400 text-right shrink-0">{label}</span>

      {/* 바 */}
      <div className="flex-1 h-4 bg-gray-700 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${getColor(percentile)}`}
          style={{ width: `${percentile}%` }}
        />
      </div>

      {/* 수치 + 백분위 */}
      <div className="w-24 text-right shrink-0">
        <span className="text-white text-sm font-bold">{value}</span>
        {unit && <span className="text-gray-400 text-xs ml-1">{unit}</span>}
        <span className="text-gray-500 text-xs ml-2">{percentile}%ile</span>
      </div>
    </div>
  );
}