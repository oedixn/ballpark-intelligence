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

export const mockLineup: Player[] = [
  { id: 1,  name: '데일',  team: 'KIA 타이거즈', position: 'SS', stats: [], radar: [] },
  { id: 2,  name: '김호령',  team: 'KIA 타이거즈', position: 'CF', stats: [], radar: [] },
  { id: 3,  name: '김선빈',  team: 'KIA 타이거즈', position: '2B', stats: [], radar: [] },
  { id: 4,  name: '김도영', team: 'KIA 타이거즈', position: '3B', stats: [], radar: [] },
  { id: 5,  name: '카스트로',  team: 'KIA 타이거즈', position: 'LF', stats: [], radar: [] },
  { id: 6,  name: '나성범',  team: 'KIA 타이거즈', position: 'DH', stats: [], radar: [] },
  { id: 7,  name: '한준수',  team: 'KIA 타이거즈', position: 'C',  stats: [], radar: [] },
  { id: 8,  name: '박상준',  team: 'KIA 타이거즈', position: '1B', stats: [], radar: [] },
  { id: 9,  name: '박재현',  team: 'KIA 타이거즈', position: 'RF', stats: [], radar: [] },
];