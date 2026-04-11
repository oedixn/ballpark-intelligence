export interface PlayerStat {
  label: string;
  value: number;
  percentile: number;
  unit: string;
}

export interface RadarStat {
  stat: string;
  value: number;
}

export interface Player {
  id: number;
  name: string;
  team: string;
  position: string;
  stats: PlayerStat[];
  radar: RadarStat[];
}

export const mockPlayers: Player[] = [
  {
    id: 1,
    name: '김도영',
    team: 'KIA 타이거즈',
    position: '3B',
    stats: [
      { label: 'wOBA',  value: 0.412, percentile: 92, unit: 'wOBA' },
      { label: 'OPS',   value: 0.981, percentile: 88, unit: 'OPS'  },
      { label: 'HR',    value: 38,    percentile: 95, unit: 'HR'   },
      { label: 'BB%',   value: 10.2,  percentile: 74, unit: '%'    },
      { label: 'K%',    value: 18.3,  percentile: 45, unit: '%'    },
    ],
    radar: [
      { stat: '컨택',   value: 88 },
      { stat: '파워',   value: 95 },
      { stat: '선구안', value: 74 },
      { stat: '스피드', value: 62 },
      { stat: '수비',   value: 70 },
      { stat: '출루',   value: 92 },
    ],
  },
];