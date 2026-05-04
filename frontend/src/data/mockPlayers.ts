// frontend/src/data/mockPlayers.ts

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
  id: number;           // player_id
  name: string;         // player_name
  team: string;         // team_name
  position: string;     // player_defense_stats.position (한글 → 영문 변환)
  stats: PlayerStat[];
  radar: RadarStat[];
}

// 한글 포지션 → 영문 변환
export const positionMap: Record<string, string> = {
  '포수':   'C',
  '1루수':  '1B',
  '2루수':  '2B',
  '3루수':  '3B',
  '유격수': 'SS',
  '좌익수': 'LF',
  '중견수': 'CF',
  '우익수': 'RF',
  '지명타자': 'DH',
};

// 2021 시즌 실제 데이터 기반 mock
export const mockPlayers: Player[] = [
  {
    id: 66108,
    name: '홍창기',
    team: 'LG',
    position: 'LF',
    stats: [
      { label: 'wOBA',  value: 0.412, percentile: 92, unit: 'wOBA' },
      { label: 'OPS',   value: 0.864, percentile: 85, unit: 'OPS'  },
      { label: 'HR',    value: 4,     percentile: 30, unit: 'HR'   },
      { label: 'BB%',   value: 16.7,  percentile: 90, unit: '%'    },
      { label: 'K%',    value: 14.6,  percentile: 70, unit: '%'    },
    ],
    radar: [
      { stat: '컨택',   value: 90 },
      { stat: '파워',   value: 35 },
      { stat: '선구안', value: 92 },
      { stat: '스피드', value: 68 },
      { stat: '수비',   value: 75 },
      { stat: '출루',   value: 95 },
    ],
  },
  {
    id: 99999,
    name: '이정후',
    team: '키움',
    position: 'CF',
    stats: [
      { label: 'wOBA',  value: 0.429, percentile: 95, unit: 'wOBA' },
      { label: 'OPS',   value: 0.921, percentile: 92, unit: 'OPS'  },
      { label: 'HR',    value: 10,    percentile: 45, unit: 'HR'   },
      { label: 'BB%',   value: 11.4,  percentile: 78, unit: '%'    },
      { label: 'K%',    value: 6.8,   percentile: 88, unit: '%'    },
    ],
    radar: [
      { stat: '컨택',   value: 97 },
      { stat: '파워',   value: 55 },
      { stat: '선구안', value: 85 },
      { stat: '스피드', value: 72 },
      { stat: '수비',   value: 80 },
      { stat: '출루',   value: 90 },
    ],
  },
  {
    id: 79109,
    name: '오지환',
    team: 'LG',
    position: 'SS',
    stats: [
      { label: 'wOBA',  value: 0.350, percentile: 72, unit: 'wOBA' },
      { label: 'OPS',   value: 0.780, percentile: 68, unit: 'OPS'  },
      { label: 'HR',    value: 15,    percentile: 60, unit: 'HR'   },
      { label: 'BB%',   value: 10.2,  percentile: 74, unit: '%'    },
      { label: 'K%',    value: 18.3,  percentile: 55, unit: '%'    },
    ],
    radar: [
      { stat: '컨택',   value: 75 },
      { stat: '파워',   value: 65 },
      { stat: '선구안', value: 72 },
      { stat: '스피드', value: 70 },
      { stat: '수비',   value: 88 },
      { stat: '출루',   value: 74 },
    ],
  },
  {
    id: 78168,
    name: '서건창',
    team: 'LG',
    position: '2B',
    stats: [
      { label: 'wOBA',  value: 0.340, percentile: 68, unit: 'wOBA' },
      { label: 'OPS',   value: 0.750, percentile: 62, unit: 'OPS'  },
      { label: 'HR',    value: 5,     percentile: 32, unit: 'HR'   },
      { label: 'BB%',   value: 8.5,   percentile: 60, unit: '%'    },
      { label: 'K%',    value: 12.1,  percentile: 72, unit: '%'    },
    ],
    radar: [
      { stat: '컨택',   value: 82 },
      { stat: '파워',   value: 40 },
      { stat: '선구안', value: 68 },
      { stat: '스피드', value: 78 },
      { stat: '수비',   value: 85 },
      { stat: '출루',   value: 72 },
    ],
  },
];

export const mockLineup: Player[] = [
  { id: 1,  name: '데일',   team: 'KIA 타이거즈', position: 'SS', stats: [], radar: [] },
  { id: 2,  name: '김호령', team: 'KIA 타이거즈', position: 'CF', stats: [], radar: [] },
  { id: 3,  name: '김선빈', team: 'KIA 타이거즈', position: '2B', stats: [], radar: [] },
  { id: 4,  name: '김도영', team: 'KIA 타이거즈', position: '3B', stats: [], radar: [] },
  { id: 5,  name: '카스트로', team: 'KIA 타이거즈', position: 'LF', stats: [], radar: [] },
  { id: 6,  name: '나성범', team: 'KIA 타이거즈', position: 'DH', stats: [], radar: [] },
  { id: 7,  name: '한준수', team: 'KIA 타이거즈', position: 'C',  stats: [], radar: [] },
  { id: 8,  name: '박상준', team: 'KIA 타이거즈', position: '1B', stats: [], radar: [] },
  { id: 9,  name: '박재현', team: 'KIA 타이거즈', position: 'RF', stats: [], radar: [] },
];