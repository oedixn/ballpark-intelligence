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
  // 시뮬레이터 연동용 원본 타격 기록
  raw?: {
    ab: number;
    hits: number;
    double: number;
    triple: number;
    hr: number;
    bb: number;
    hbp: number;
  };
}

export const mockPlayers: Player[] = [
  {
    id: 66108,
    name: '홍창기',
    team: 'LG',
    position: 'LF',
    stats: [
      { label: 'wOBA', value: 0.412, percentile: 92, unit: 'wOBA' },
      { label: 'OPS',  value: 0.864, percentile: 85, unit: 'OPS'  },
      { label: 'HR',   value: 4,     percentile: 30, unit: 'HR'   },
      { label: 'BB%',  value: 16.7,  percentile: 90, unit: '%'    },
      { label: 'K%',   value: 14.6,  percentile: 70, unit: '%'    },
    ],
    radar: [
      { stat: '컨택',   value: 90 },
      { stat: '파워',   value: 35 },
      { stat: '선구안', value: 92 },
      { stat: '스피드', value: 68 },
      { stat: '수비',   value: 75 },
      { stat: '출루',   value: 95 },
    ],
    raw: { ab: 524, hits: 172, double: 26, triple: 2, hr: 4, bb: 109, hbp: 16 },
  },
];

export const mockLineup: Player[] = [
  { id: 1,  name: '데일',    team: 'KIA 타이거즈', position: 'SS', stats: [], radar: [] },
  { id: 2,  name: '김호령',  team: 'KIA 타이거즈', position: 'CF', stats: [], radar: [] },
  { id: 3,  name: '김선빈',  team: 'KIA 타이거즈', position: '2B', stats: [], radar: [] },
  { id: 4,  name: '김도영',  team: 'KIA 타이거즈', position: '3B', stats: [], radar: [] },
  { id: 5,  name: '카스트로',team: 'KIA 타이거즈', position: 'LF', stats: [], radar: [] },
  { id: 6,  name: '나성범',  team: 'KIA 타이거즈', position: 'DH', stats: [], radar: [] },
  { id: 7,  name: '한준수',  team: 'KIA 타이거즈', position: 'C',  stats: [], radar: [] },
  { id: 8,  name: '박상준',  team: 'KIA 타이거즈', position: '1B', stats: [], radar: [] },
  { id: 9,  name: '박재현',  team: 'KIA 타이거즈', position: 'RF', stats: [], radar: [] },
];