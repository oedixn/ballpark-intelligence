import {
  Radar, RadarChart, PolarGrid,
  PolarAngleAxis, ResponsiveContainer
} from 'recharts';

interface Props {
  data: { stat: string; value: number }[]; // value: 0 ~ 100 (백분위)
}

export default function PlayerRadarChart({ data }: Props) {
  return (
    <div className="w-full h-72">
      <ResponsiveContainer width="100%" height="100%">
        <RadarChart data={data} cx="50%" cy="50%" outerRadius="70%">
          <PolarGrid stroke="#374151" />
          <PolarAngleAxis
            dataKey="stat"
            tick={{ fill: '#9CA3AF', fontSize: 12 }}
          />
          <Radar
            name="선수"
            dataKey="value"
            stroke="#F97316"
            fill="#F97316"
            fillOpacity={0.3}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}