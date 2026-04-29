export interface AtBat {
  batter: string;
  result: string;
  runs: number;
  outs: number;
  bases: [number, number, number];
}

export interface HalfInning {
  team: string;
  atBats: AtBat[];
  runs: number;
}

export interface GameLog {
  innings: {
    top: HalfInning;
    bottom: HalfInning;
  }[];
}

export const mockGameLog: GameLog = {
  innings: [
    {
      top: {
        team: 'SSG 랜더스',
        runs: 3,
        atBats: [
          { batter: '박성한',  result: '볼넷',    runs: 0, outs: 0, bases: [1,0,0] },
          { batter: '에레디아', result: '안타',    runs: 0, outs: 0, bases: [1,1,0] },
          { batter: '최정',    result: '홈런',    runs: 3, outs: 0, bases: [0,0,0] },
          { batter: '김재환',  result: '뜬공아웃', runs: 0, outs: 1, bases: [0,0,0] },
          { batter: '고명준',  result: '삼진아웃', runs: 0, outs: 2, bases: [0,0,0] },
          { batter: '한유섬',  result: '땅볼아웃', runs: 0, outs: 3, bases: [0,0,0] },
        ],
      },
      bottom: {
        team: 'KIA 타이거즈',
        runs: 0,
        atBats: [
          { batter: '김호령', result: '삼진아웃', runs: 0, outs: 1, bases: [0,0,0] },
          { batter: '김선빈', result: '안타',    runs: 0, outs: 1, bases: [1,0,0] },
          { batter: '김도영', result: '땅볼아웃', runs: 0, outs: 2, bases: [0,0,0] },
          { batter: '나성범', result: '뜬공아웃', runs: 0, outs: 3, bases: [0,0,0] },
        ],
      },
    },
    {
      top: {
        team: 'KIA 타이거즈',
        runs: 0,
        atBats: [
          { batter: '김호령', result: '삼진아웃', runs: 0, outs: 1, bases: [0,0,0] },
          { batter: '김선빈', result: '2루타',   runs: 0, outs: 1, bases: [0,1,0] },
          { batter: '김도영', result: '땅볼아웃', runs: 0, outs: 2, bases: [0,0,0] },
          { batter: '나성범', result: '삼진아웃', runs: 0, outs: 3, bases: [0,0,0] },
        ],
      },
      bottom: {
        team: 'SSG 랜더스',
        runs: 1,
        atBats: [
          { batter: '한유섬',  result: '볼넷',    runs: 0, outs: 0, bases: [1,0,0] },
          { batter: '최지훈',  result: '안타',    runs: 0, outs: 0, bases: [1,1,0] },
          { batter: '조형우',  result: '안타',    runs: 1, outs: 0, bases: [1,1,0] },
          { batter: '정준재',  result: '삼진아웃', runs: 0, outs: 1, bases: [1,1,0] },
          { batter: '박성한',  result: '뜬공아웃', runs: 0, outs: 2, bases: [1,1,0] },
          { batter: '에레디아', result: '삼진아웃', runs: 0, outs: 3, bases: [1,1,0] },
        ],
      },
    },
  ],
};

export const mockScoreboard = {
  away: { team: 'KIA 타이거즈', scores: [3, 0, 1, 0, 2, 0, 0, 1, 0], total: 7 },
  home: { team: 'SSG 랜더스',   scores: [0, 1, 0, 3, 0, 0, 2, 0, 1], total: 7 },
};