import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';

const api = axios.create({ baseURL: 'http://localhost:8000' });

interface TeamRank {
  rank: number;
  team_name: string;
  games: number;
  wins: number;
  losses: number;
  draws: number;
  win_rate: number;
  last10: string;
  streak: string;
}

interface HitterStat {
  player_id: string;
  player_name: string;
  team_name: string;
  position: string;
  avg: number;
  pa: number;
  hr: number;
  rbi: number;
  obp: number;
  slg: number;
  ops: number;
  bb_rate: number;
  k_rate: number;
  woba: number;
}

interface PitcherStat {
  player_id: string;
  player_name: string;
  team_name: string;
  era: number;
  g: number;
  w: number;
  l: number;
  sv: number;
  hld: number;
  ip: string;
  so: number;
  bb: number;
  hr: number;
  whip: number;
  wpct: number;
}

type HitterSortKey  = 'woba' | 'ops' | 'hr' | 'avg' | 'rbi';
type PitcherSortKey = 'era' | 'w' | 'sv' | 'so' | 'whip';

const HITTER_SORT_OPTIONS: { key: HitterSortKey; label: string }[] = [
  { key: 'woba', label: 'wOBA' },
  { key: 'ops',  label: 'OPS'  },
  { key: 'hr',   label: 'HR'   },
  { key: 'avg',  label: '타율' },
  { key: 'rbi',  label: 'RBI'  },
];

const PITCHER_SORT_OPTIONS: { key: PitcherSortKey; label: string }[] = [
  { key: 'era',  label: 'ERA'  },
  { key: 'w',    label: '승'   },
  { key: 'sv',   label: '세이브' },
  { key: 'so',   label: '탈삼진' },
  { key: 'whip', label: 'WHIP' },
];

const MEDAL = ['🥇', '🥈', '🥉'];

export default function StatsPage() {
  const navigate = useNavigate();
  const [tab, setTab]               = useState<'team' | 'hitter' | 'pitcher'>('team');
  const [teams, setTeams]           = useState<TeamRank[]>([]);
  const [hitters, setHitters]       = useState<HitterStat[]>([]);
  const [pitchers, setPitchers]     = useState<PitcherStat[]>([]);
  const [hitterSort, setHitterSort] = useState<HitterSortKey>('woba');
  const [pitcherSort, setPitcherSort] = useState<PitcherSortKey>('era');
  const [loading, setLoading]       = useState(false);

  useEffect(() => {
    setLoading(true);
    if (tab === 'team') {
      api.get('/api/stats/team-rank')
        .then(res => setTeams(res.data.teams))
        .catch(() => {})
        .finally(() => setLoading(false));
    } else if (tab === 'hitter') {
      api.get(`/api/stats/hitters?sort=${hitterSort}&limit=50`)
        .then(res => setHitters(res.data.hitters))
        .catch(() => {})
        .finally(() => setLoading(false));
    } else {
      api.get(`/api/stats/pitchers?sort=${pitcherSort}&limit=50`)
        .then(res => setPitchers(res.data.pitchers))
        .catch(() => {})
        .finally(() => setLoading(false));
    }
  }, [tab, hitterSort, pitcherSort]);

  return (
    <div className="min-h-screen bg-gray-900 pb-20">

      {/* 헤더 */}
      <div className="bg-gradient-to-r from-gray-800 to-gray-900 border-b border-gray-700 px-10 py-10">
        <h1 className="text-white text-3xl font-black">기록실</h1>
        <p className="text-gray-400 text-sm mt-1">2026 KBO 시즌 팀/선수 기록</p>
      </div>

      {/* 탭 */}
      <div className="px-10 pt-10 pb-2 flex gap-4">
        {[
          { key: 'team',    label: '팀 순위'  },
          { key: 'hitter',  label: '타자 기록' },
          { key: 'pitcher', label: '투수 기록' },
        ].map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setTab(key as 'team' | 'hitter' | 'pitcher')}
            className={`px-6 py-2.5 rounded-xl text-sm font-bold transition-colors ${
              tab === key
                ? 'bg-orange-500 text-white'
                : 'bg-gray-800 text-gray-400 hover:text-white'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="px-10 py-10">
        {loading && (
          <div className="flex justify-center py-20">
            <p className="text-gray-400 animate-pulse">⚾ 데이터 불러오는 중...</p>
          </div>
        )}

        {/* 팀 순위 */}
        {!loading && tab === 'team' && (
          <div className="bg-gray-800 rounded-2xl overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-700 text-gray-400 text-xs uppercase tracking-widest">
                  <th className="text-left px-6 py-4 w-12">순위</th>
                  <th className="text-left px-6 py-4">팀</th>
                  <th className="text-center px-4 py-4">경기</th>
                  <th className="text-center px-4 py-4">승</th>
                  <th className="text-center px-4 py-4">패</th>
                  <th className="text-center px-4 py-4">무</th>
                  <th className="text-center px-4 py-4">승률</th>
                  <th className="text-center px-4 py-4">최근 10경기</th>
                  <th className="text-center px-4 py-4">연속</th>
                </tr>
              </thead>
              <tbody>
                {teams.map((team, i) => (
                  <tr key={team.team_name} className={`border-t border-gray-700 transition-colors hover:bg-gray-700/50 ${i === 0 ? 'bg-orange-500/5' : ''}`}>
                    <td className="px-6 py-4">
                      {i < 3
                        ? <span className="text-lg">{MEDAL[i]}</span>
                        : <span className="text-gray-400 font-bold">{team.rank}</span>
                      }
                    </td>
                    <td className="px-6 py-4">
                      <span className={`font-bold ${i === 0 ? 'text-orange-400' : 'text-white'}`}>{team.team_name}</span>
                    </td>
                    <td className="text-center px-4 py-4 text-gray-300">{team.games}</td>
                    <td className="text-center px-4 py-4 text-blue-400 font-bold">{team.wins}</td>
                    <td className="text-center px-4 py-4 text-red-400">{team.losses}</td>
                    <td className="text-center px-4 py-4 text-gray-400">{team.draws}</td>
                    <td className="text-center px-4 py-4">
                      <span className={`font-bold ${i < 3 ? 'text-orange-400' : 'text-gray-300'}`}>
                        {Number(team.win_rate).toFixed(3)}
                      </span>
                    </td>
                    <td className="text-center px-4 py-4 text-gray-400 text-xs">{team.last10 ?? '-'}</td>
                    <td className="text-center px-4 py-4">
                      <span className={`text-xs font-bold px-2 py-0.5 rounded ${
                        team.streak?.startsWith('승') ? 'bg-blue-500/20 text-blue-400'
                        : team.streak?.startsWith('패') ? 'bg-red-500/20 text-red-400'
                        : 'bg-gray-600 text-gray-400'
                      }`}>
                        {team.streak ?? '-'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* 타자 기록 */}
        {!loading && tab === 'hitter' && (
          <>
            <div className="flex gap-2 mb-8 mt-2">
              {HITTER_SORT_OPTIONS.map(({ key, label }) => (
                <button
                  key={key}
                  onClick={() => setHitterSort(key)}
                  className={`px-4 py-2 rounded-lg text-xs font-bold transition-colors ${
                    hitterSort === key ? 'bg-orange-500 text-white' : 'bg-gray-800 text-gray-400 hover:text-white'
                  }`}
                >
                  {label} 순
                </button>
              ))}
            </div>
            <div className="bg-gray-800 rounded-2xl overflow-hidden mb-10">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-700 text-gray-400 text-xs uppercase tracking-widest">
                    <th className="text-left px-6 py-4 w-8">#</th>
                    <th className="text-left px-6 py-4">선수</th>
                    <th className="text-left px-4 py-4">팀</th>
                    <th className="text-left px-4 py-4">포지션</th>
                    <th className="text-center px-4 py-4">PA</th>
                    <th className="text-center px-4 py-4">타율</th>
                    <th className="text-center px-4 py-4">HR</th>
                    <th className="text-center px-4 py-4">RBI</th>
                    <th className="text-center px-4 py-4">OBP</th>
                    <th className="text-center px-4 py-4">SLG</th>
                    <th className="text-center px-4 py-4">OPS</th>
                    <th className="text-center px-4 py-4">BB%</th>
                    <th className="text-center px-4 py-4">K%</th>
                    <th className="text-center px-4 py-4 text-orange-400">wOBA</th>
                  </tr>
                </thead>
                <tbody>
                  {hitters.map((p, i) => (
                    <tr key={`${p.player_name}-${i}`} className="border-t border-gray-700 hover:bg-gray-700/50 transition-colors">
                      <td className="px-6 py-3 text-gray-500 text-xs">{i + 1}</td>
                      <td className="px-6 py-3">
                        <button
                          onClick={() => navigate(`/player/${p.player_id}`)}
                          style={{ cursor: 'pointer' }}
                          className={`font-bold hover:text-orange-400 transition-colors text-left underline-offset-2 hover:underline ${i < 3 ? 'text-orange-400' : 'text-white'}`}
                        >
                          {i < 3 && `${MEDAL[i]} `}{p.player_name}
                        </button>
                      </td>
                      <td className="px-4 py-3 text-gray-400 text-xs">{p.team_name}</td>
                      <td className="px-4 py-3">
                        <span className="text-xs bg-gray-700 text-gray-300 px-2 py-0.5 rounded">{p.position ?? '-'}</span>
                      </td>
                      <td className="text-center px-4 py-3 text-gray-300">{p.pa}</td>
                      <td className="text-center px-4 py-3 text-gray-300">{Number(p.avg).toFixed(3)}</td>
                      <td className="text-center px-4 py-3 text-gray-300">{p.hr}</td>
                      <td className="text-center px-4 py-3 text-gray-300">{p.rbi}</td>
                      <td className="text-center px-4 py-3 text-gray-300">{Number(p.obp).toFixed(3)}</td>
                      <td className="text-center px-4 py-3 text-gray-300">{Number(p.slg).toFixed(3)}</td>
                      <td className="text-center px-4 py-3 text-gray-300">{Number(p.ops).toFixed(3)}</td>
                      <td className="text-center px-4 py-3 text-gray-300">{Number(p.bb_rate).toFixed(1)}%</td>
                      <td className="text-center px-4 py-3 text-gray-300">{Number(p.k_rate).toFixed(1)}%</td>
                      <td className="text-center px-4 py-3">
                        <span className={`font-bold ${i < 3 ? 'text-orange-400' : 'text-gray-300'}`}>
                          {Number(p.woba).toFixed(3)}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}

        {/* 투수 기록 */}
        {!loading && tab === 'pitcher' && (
          <>
            <div className="flex gap-2 mb-8 mt-2">
              {PITCHER_SORT_OPTIONS.map(({ key, label }) => (
                <button
                  key={key}
                  onClick={() => setPitcherSort(key)}
                  className={`px-4 py-2 rounded-lg text-xs font-bold transition-colors ${
                    pitcherSort === key ? 'bg-orange-500 text-white' : 'bg-gray-800 text-gray-400 hover:text-white'
                  }`}
                >
                  {label} 순
                </button>
              ))}
            </div>
            <div className="bg-gray-800 rounded-2xl overflow-hidden mb-10">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-700 text-gray-400 text-xs uppercase tracking-widest">
                    <th className="text-left px-6 py-4 w-8">#</th>
                    <th className="text-left px-6 py-4">선수</th>
                    <th className="text-left px-4 py-4">팀</th>
                    <th className="text-center px-4 py-4">경기</th>
                    <th className="text-center px-4 py-4">승</th>
                    <th className="text-center px-4 py-4">패</th>
                    <th className="text-center px-4 py-4">세이브</th>
                    <th className="text-center px-4 py-4">홀드</th>
                    <th className="text-center px-4 py-4">이닝</th>
                    <th className="text-center px-4 py-4">탈삼진</th>
                    <th className="text-center px-4 py-4">볼넷</th>
                    <th className="text-center px-4 py-4">피홈런</th>
                    <th className="text-center px-4 py-4">WHIP</th>
                    <th className="text-center px-4 py-4 text-orange-400">ERA</th>
                  </tr>
                </thead>
                <tbody>
                  {pitchers.map((p, i) => (
                    <tr key={`${p.player_name}-${i}`} className="border-t border-gray-700 hover:bg-gray-700/50 transition-colors">
                      <td className="px-6 py-3 text-gray-500 text-xs">{i + 1}</td>
                      <td className="px-6 py-3">
                        <span className={`font-bold ${i < 3 ? 'text-orange-400' : 'text-white'}`}>
                          {i < 3 && `${MEDAL[i]} `}{p.player_name}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-gray-400 text-xs">{p.team_name}</td>
                      <td className="text-center px-4 py-3 text-gray-300">{p.g}</td>
                      <td className="text-center px-4 py-3 text-blue-400 font-bold">{p.w}</td>
                      <td className="text-center px-4 py-3 text-red-400">{p.l}</td>
                      <td className="text-center px-4 py-3 text-gray-300">{p.sv}</td>
                      <td className="text-center px-4 py-3 text-gray-300">{p.hld}</td>
                      <td className="text-center px-4 py-3 text-gray-300">{p.ip}</td>
                      <td className="text-center px-4 py-3 text-gray-300">{p.so}</td>
                      <td className="text-center px-4 py-3 text-gray-300">{p.bb}</td>
                      <td className="text-center px-4 py-3 text-gray-300">{p.hr}</td>
                      <td className="text-center px-4 py-3 text-gray-300">{Number(p.whip).toFixed(2)}</td>
                      <td className="text-center px-4 py-3">
                        <span className={`font-bold ${i < 3 ? 'text-orange-400' : 'text-gray-300'}`}>
                          {Number(p.era).toFixed(2)}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </div>
  );
}