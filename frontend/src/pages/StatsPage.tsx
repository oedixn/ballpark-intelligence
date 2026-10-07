import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { getTeamLogo } from '../utils/teamLogo';

const api = axios.create({ baseURL: import.meta.env.VITE_API_URL });

interface TeamRank { rank: number; team_name: string; games: number; wins: number; losses: number; draws: number; win_rate: number }
interface RecentGame { date: string; opponent: string; score: string; result: 'W' | 'L' | 'D' }
type Tab = 'team' | 'hitter' | 'pitcher';
type Col = { h: string; k: string; d?: number; s?: string; c?: string; hi?: boolean };

const TABS: { key: Tab; label: string }[] = [{ key: 'team', label: '팀 순위' }, { key: 'hitter', label: '타자 기록' }, { key: 'pitcher', label: '투수 기록' }];
const HITTER_SORT = [['woba', 'wOBA'], ['ops', 'OPS'], ['hr', 'HR'], ['avg', '타율'], ['rbi', 'RBI']];
const PITCHER_SORT = [['era', 'ERA'], ['w', '승'], ['sv', '세이브'], ['hld', '홀드'], ['so', '탈삼진'], ['whip', 'WHIP']];

const HITTER_COLS: Col[] = [
  { h: 'PA', k: 'pa' }, { h: '타율', k: 'avg', d: 3 }, { h: 'HR', k: 'hr' }, { h: 'RBI', k: 'rbi' },
  { h: 'OBP', k: 'obp', d: 3 }, { h: 'SLG', k: 'slg', d: 3 }, { h: 'OPS', k: 'ops', d: 3 },
  { h: 'BB%', k: 'bb_rate', d: 1, s: '%' }, { h: 'K%', k: 'k_rate', d: 1, s: '%' },
  { h: 'wOBA', k: 'woba', d: 3, hi: true }, { h: 'wRC+', k: 'wrc_plus', d: 0 },
];
const PITCHER_COLS: Col[] = [
  { h: '경기', k: 'g' }, { h: '승', k: 'w', c: 'text-blue-400 font-semibold' }, { h: '패', k: 'l', c: 'text-red-400' },
  { h: '세이브', k: 'sv' }, { h: '홀드', k: 'hld' }, { h: '이닝', k: 'ip' }, { h: '탈삼진', k: 'so' },
  { h: '볼넷', k: 'bb' }, { h: '피홈런', k: 'hr' }, { h: 'WHIP', k: 'whip', d: 2 }, { h: 'ERA', k: 'era', d: 2, hi: true },
];

const FORM: Record<string, string> = { W: 'bg-blue-500 text-white', L: 'bg-red-500/80 text-white', D: 'bg-gray-600 text-white' };
const FORM_LABEL: Record<string, string> = { W: '승', L: '패', D: '무' };

function TeamName({ name, className = '' }: { name: string; className?: string }) {
  const logo = getTeamLogo(name);
  return (
    <span className="inline-flex items-center gap-2">
      {logo && <img src={logo} alt={name} className="w-5 h-5 object-contain" />}
      <span className={className}>{name}</span>
    </span>
  );
}

const cell = (c: Col, p: Record<string, any>) => {
  const v = p[c.k];
  if (v === null || v === undefined) return '-';
  return c.d === undefined ? v : `${Number(v).toFixed(c.d)}${c.s ?? ''}`;
};

export default function StatsPage() {
  const navigate = useNavigate();
  const [tab, setTab] = useState<Tab>('team');
  const [teams, setTeams] = useState<TeamRank[]>([]);
  const [recent, setRecent] = useState<Record<string, RecentGame[]>>({});
  const [hitters, setHitters] = useState<Record<string, any>[]>([]);
  const [pitchers, setPitchers] = useState<Record<string, any>[]>([]);
  const [hSort, setHSort] = useState('woba');
  const [pSort, setPSort] = useState('era');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    const done = () => setLoading(false);
    if (tab === 'team') {
      api.get('/api/stats/team-rank').then(res => {
        setTeams(res.data.teams);
        res.data.teams.forEach((t: TeamRank) =>
          api.get(`/api/teams/${encodeURIComponent(t.team_name)}/recent`)
            .then(r => setRecent(prev => ({ ...prev, [t.team_name]: r.data.recent }))).catch(() => {}));
      }).catch(() => {}).finally(done);
    } else if (tab === 'hitter') {
      const load = () => api.get(`/api/stats/hitters?sort=${hSort}&limit=50`).then(r => setHitters(r.data.hitters)).catch(() => {}).finally(done);
      load();
      const t = setInterval(load, 60000);
      return () => clearInterval(t);
    } else {
      api.get(`/api/stats/pitchers?sort=${pSort}&limit=50`).then(r => setPitchers(r.data.pitchers)).catch(() => {}).finally(done);
    }
  }, [tab, hSort, pSort]);

  const rankCell = (i: number) => <span className={i < 3 ? 'text-orange-400 font-bold' : 'text-gray-500'}>{i + 1}</span>;
  const th = 'px-4 py-3 text-center font-medium whitespace-nowrap';

  const sortBar = (opts: string[][], cur: string, set: (v: string) => void) => (
    <div className="flex gap-2 mb-5">
      {opts.map(([k, label]) => (
        <button key={k} onClick={() => set(k)}
          className={`text-sm px-3 py-1.5 rounded-md border transition-colors ${cur === k ? 'border-orange-500 text-orange-400' : 'border-gray-700 text-gray-400 hover:text-orange-400 hover:border-gray-500'}`}>
          {label} 순
        </button>
      ))}
    </div>
  );

  const playerTable = (rows: Record<string, any>[], cols: Col[], withPos: boolean) => (
    <div className="border border-gray-800 rounded-lg overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="bg-gray-800/60 text-gray-400">
          <tr>
            <th className={`${th} text-left w-10`}>#</th>
            <th className={`${th} text-left`}>선수</th>
            <th className={`${th} text-left`}>팀</th>
            {withPos && <th className={`${th} text-left`}>포지션</th>}
            {cols.map(c => <th key={c.h} className={`${th} ${c.hi ? 'text-orange-400' : ''}`}>{c.h}</th>)}
          </tr>
        </thead>
        <tbody>
          {rows.map((p, i) => (
            <tr key={`${p.player_id}-${i}`} className="border-t border-gray-800 hover:bg-gray-800/50 transition-colors">
              <td className="px-4 py-3">{rankCell(i)}</td>
              <td className="px-4 py-3">
                <button onClick={() => navigate(`/player/${p.player_id}`)} className="text-white font-semibold hover:text-orange-400 transition-colors text-left">{p.player_name}</button>
              </td>
              <td className="px-4 py-3"><TeamName name={p.team_name} className="text-gray-300" /></td>
              {withPos && <td className="px-4 py-3 text-gray-400">{p.position ?? '-'}</td>}
              {cols.map(c => {
                const wrc = c.k === 'wrc_plus' ? (Number(p.wrc_plus) >= 130 ? 'text-orange-400 font-semibold' : Number(p.wrc_plus) >= 100 ? 'text-green-400' : 'text-gray-400') : '';
                return <td key={c.h} className={`px-4 py-3 text-center ${wrc || c.c || (c.hi ? (i < 3 ? 'text-orange-400 font-semibold' : 'text-white font-semibold') : 'text-gray-300')}`}>{cell(c, p)}</td>;
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );

  return (
    <div className="min-h-screen bg-gray-900 pb-20">
      <header className="px-10 pt-10 pb-6 border-b border-gray-800">
        <h1 className="text-white text-3xl font-bold">기록실</h1>
        <p className="text-gray-400 mt-1">2026 KBO 시즌 팀 · 선수 기록</p>
      </header>

      <nav className="px-10 flex gap-6 border-b border-gray-800">
        {TABS.map(({ key, label }) => (
          <button key={key} onClick={() => setTab(key)}
            className={`py-3 -mb-px border-b-2 font-semibold transition-colors ${tab === key ? 'border-orange-500 text-white' : 'border-transparent text-gray-400 hover:text-orange-400'}`}>
            {label}
          </button>
        ))}
      </nav>

      <main className="px-10 py-8">
        {loading && <p className="text-gray-500 py-16 text-center animate-pulse">데이터를 불러오는 중입니다.</p>}

        {!loading && tab === 'team' && (
          <div className="border border-gray-800 rounded-lg overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-800/60 text-gray-400">
                <tr>
                  <th className={`${th} text-left w-16`}>순위</th>
                  <th className={`${th} text-left`}>팀</th>
                  {['경기', '승', '패', '무', '승률', '최근 5경기'].map(h => <th key={h} className={th}>{h}</th>)}
                </tr>
              </thead>
              <tbody>
                {teams.map((t, i) => (
                  <tr key={t.team_name} className="border-t border-gray-800 hover:bg-gray-800/50 transition-colors">
                    <td className="px-4 py-3.5">{rankCell(i)}</td>
                    <td className="px-4 py-3.5"><TeamName name={t.team_name} className={`font-semibold ${i === 0 ? 'text-orange-400' : 'text-white'}`} /></td>
                    <td className="px-4 py-3.5 text-center text-gray-300">{t.games}</td>
                    <td className="px-4 py-3.5 text-center text-blue-400 font-semibold">{t.wins}</td>
                    <td className="px-4 py-3.5 text-center text-red-400">{t.losses}</td>
                    <td className="px-4 py-3.5 text-center text-gray-400">{t.draws}</td>
                    <td className={`px-4 py-3.5 text-center font-semibold ${i < 3 ? 'text-orange-400' : 'text-gray-300'}`}>{Number(t.win_rate).toFixed(3)}</td>
                    <td className="px-4 py-3.5">
                      <div className="flex items-center justify-center gap-1">
                        {(recent[t.team_name] ?? []).map((g, gi) => (
                          <span key={gi} title={`${g.date} vs ${g.opponent} ${g.score}`}
                            className={`w-6 h-6 rounded-md text-xs font-bold flex items-center justify-center cursor-default ${FORM[g.result]}`}>{FORM_LABEL[g.result]}</span>
                        ))}
                        {!(recent[t.team_name] ?? []).length && <span className="text-gray-600 text-xs animate-pulse">불러오는 중</span>}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {!loading && tab === 'hitter' && (<>{sortBar(HITTER_SORT, hSort, setHSort)}{playerTable(hitters, HITTER_COLS, true)}</>)}
        {!loading && tab === 'pitcher' && (<>{sortBar(PITCHER_SORT, pSort, setPSort)}{playerTable(pitchers, PITCHER_COLS, false)}</>)}
      </main>
    </div>
  );
}