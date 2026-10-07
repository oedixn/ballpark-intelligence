import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { DndContext, closestCenter, KeyboardSensor, PointerSensor, useSensor, useSensors } from '@dnd-kit/core';
import { SortableContext, sortableKeyboardCoordinates, verticalListSortingStrategy, arrayMove } from '@dnd-kit/sortable';
import LineupCard from '../components/lineup/LineupCard';
import type { Player } from '../data/mockPlayers';
import { fetchPlayers, optimizeLineup } from '../api/playerApi';
import type { PlayerDB } from '../api/playerApi';
import { fetchRecords, deleteRecord } from '../api/recordApi';
import type { GameRecord } from '../api/recordApi';
import { getTeamLogo } from '../utils/teamLogo';

const KBO_TEAMS = ['LG', 'KIA', 'SSG', '한화', 'NC', 'KT', '삼성', '롯데', '두산', '키움'];
const ROLES = ['중계', '셋업', '롱릴리프', '마무리'];
const SLOT_KEYS = ['sp-0', 'sp-1', 'sp-2', 'sp-3', 'sp-4', ...ROLES];
const slotLabel = (k: string) => (k.startsWith('sp-') ? `선발 ${Number(k.slice(3)) + 1}` : k);

interface PitcherPick { name: string; team: string; era: number | null; sv: number; hld: number }
type Bullpen = Record<string, PitcherPick | null>;
const EMPTY_BULLPEN: Bullpen = { 중계: null, 셋업: null, 롱릴리프: null, 마무리: null };

const isPitcher = (p: any) => p.position === '투수' || (p.era != null && p.avg == null);
const dbToPitcher = (p: any): PitcherPick => ({
  name: p.player_name, team: p.team_name, era: p.era != null ? Number(p.era) : null, sv: Number(p.sv ?? 0), hld: Number(p.hld ?? 0),
});
const findPitcher = async (name: string): Promise<PitcherPick | null> => {
  try {
    const d: any[] = await fetchPlayers(name);
    const m = d.find(p => p.player_name === name && isPitcher(p));
    return m ? dbToPitcher(m) : null;
  } catch { return null; }
};

function TeamLogoLabel({ name }: { name: string }) {
  const logo = getTeamLogo(name);
  return (
    <span className="inline-flex items-center gap-1.5">
      {logo && <img src={logo} alt={name} className="w-4 h-4 object-contain" />}
      {name}
    </span>
  );
}

function dbToPlayer(p: PlayerDB): Player {
  return {
    id: Number(p.player_id), name: p.player_name, team: p.team_name, position: p.position ?? '-',
    stats: [
      { label: 'wOBA', value: p.woba ?? 0, percentile: 0, unit: 'wOBA' },
      { label: 'OPS', value: p.ops ?? 0, percentile: 0, unit: 'OPS' },
      { label: 'HR', value: p.hr ?? 0, percentile: 0, unit: 'HR' },
      { label: 'BB%', value: p.bb_rate ?? 0, percentile: 0, unit: '%' },
      { label: 'K%', value: p.k_rate ?? 0, percentile: 0, unit: '%' },
    ],
    radar: [
      { stat: '컨택', value: Math.min(99, Math.round(Number(p.avg ?? 0) * 300)) },
      { stat: '파워', value: Math.min(99, Math.round(Number(p.iso ?? 0) * 400)) },
      { stat: '선구안', value: Math.min(99, Math.round(Number(p.bb_rate ?? 0) * 5)) },
      { stat: '스피드', value: Math.min(99, Math.round(Number(p.spd ?? 0) * 10)) },
      { stat: '수비', value: 60 },
      { stat: '출루', value: Math.min(99, Math.round(Number(p.obp ?? 0) * 200)) },
    ],
    raw: {
      ab: Number(p.ab ?? 300), hits: Number(p.h ?? 80), double: Number(p.double_hit ?? 15),
      triple: Number(p.triple_hit ?? 2), hr: Number(p.hr ?? 5), bb: Number(p.bb ?? 30), hbp: Number(p.hbp ?? 3),
    },
  };
}

const toLineupData = (ps: Player[], withPosition = false) => ps.map((p) => ({
  name: p.name, ...(withPosition ? { position: p.position } : {}),
  ab: p.raw?.ab ?? 300, hits: p.raw?.hits ?? 80, double: p.raw?.double ?? 15,
  triple: p.raw?.triple ?? 2, hr: p.raw?.hr ?? 5, bb: p.raw?.bb ?? 30, hbp: p.raw?.hbp ?? 3,
}));

interface SavedTeam {
  id: number; team_name: string; opponent: string; lineup: { name: string; position: string }[]; created_at: string;
  pitching?: { starters: string[]; bullpen: Record<string, string> };
}

const readJson = <T,>(key: string, fallback: T): T => {
  try { return JSON.parse(localStorage.getItem(key) || '') as T; } catch { return fallback; }
};

const btn = 'text-sm font-semibold px-4 py-2 rounded-lg border transition-colors';
const btnOn = 'border-gray-600 text-gray-200 hover:border-orange-400 hover:text-orange-400';
const btnOff = 'border-gray-800 text-gray-600 cursor-not-allowed';
const sectionTitle = 'text-white font-semibold mb-3';

export default function MyTeamPage() {
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<Player[]>([]);
  const [showDropdown, setShowDropdown] = useState(false);
  const [lineup, setLineup] = useState<(Player | null)[]>(Array(9).fill(null));
  const [starters, setStarters] = useState<(PitcherPick | null)[]>(Array(5).fill(null));
  const [bullpen, setBullpen] = useState<Bullpen>(EMPTY_BULLPEN);
  const [slot, setSlot] = useState('sp-0');
  const [pQuery, setPQuery] = useState('');
  const [pResults, setPResults] = useState<PitcherPick[]>([]);
  const [records, setRecords] = useState<GameRecord[]>([]);
  const [teamName, setTeamName] = useState('나만의 팀');
  const [opponent, setOpponent] = useState('롯데');
  const [optimizing, setOptimizing] = useState(false);
  const [searchHistory, setSearchHistory] = useState<string[]>(() => readJson('search_history', []));
  const [savedTeams, setSavedTeams] = useState<SavedTeam[]>(() => readJson('saved_teams', []));
  const [showSavedTeams, setShowSavedTeams] = useState(false);
  const searchRef = useRef<HTMLDivElement>(null);

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
  );

  useEffect(() => { fetchRecords(teamName).then(setRecords).catch(() => {}); }, [teamName]);

  useEffect(() => {
    if (!query.trim()) { setResults([]); return; }
    const timer = setTimeout(async () => {
      try {
        const data: any[] = await fetchPlayers(query);
        setResults(data.filter(p => !isPitcher(p)).map(dbToPlayer));
        setShowDropdown(true);
      } catch { setResults([]); }
    }, 300);
    return () => clearTimeout(timer);
  }, [query]);

  useEffect(() => {
    if (!pQuery.trim()) { setPResults([]); return; }
    const timer = setTimeout(async () => {
      try { const d: any[] = await fetchPlayers(pQuery); setPResults(d.filter(isPitcher).map(dbToPitcher).slice(0, 8)); }
      catch { setPResults([]); }
    }, 300);
    return () => clearTimeout(timer);
  }, [pQuery]);

  useEffect(() => {
    const onDown = (e: MouseEvent) => {
      if (searchRef.current && !searchRef.current.contains(e.target as Node)) setShowDropdown(false);
    };
    document.addEventListener('mousedown', onDown);
    return () => document.removeEventListener('mousedown', onDown);
  }, []);

  const filledPlayers = lineup.filter((p): p is Player => p !== null);
  const filledCount = filledPlayers.length;
  const complete = filledCount === 9;
  const avgOPS = filledCount > 0
    ? (filledPlayers.reduce((sum, p) => sum + (p?.stats?.find(s => s.label === 'OPS')?.value ?? 0), 0) / filledCount).toFixed(3)
    : '-';
  const wins = records.filter(r => r.result === '승').length;
  const losses = records.filter(r => r.result === '패').length;
  const draws = records.filter(r => r.result === '무').length;

  const getPick = (k: string) => (k.startsWith('sp-') ? starters[Number(k.slice(3))] : bullpen[k]);
  const pitchCount = SLOT_KEYS.filter(k => getPick(k)).length;

  function pickPitcher(pk: PitcherPick) {
    if (SLOT_KEYS.some(k => getPick(k)?.name === pk.name)) { alert('이미 선택된 투수입니다.'); return; }
    const sp = [...starters]; const rp = { ...bullpen };
    if (slot.startsWith('sp-')) sp[Number(slot.slice(3))] = pk; else rp[slot] = pk;
    setStarters(sp); setBullpen(rp);
    const next = SLOT_KEYS.find(k => !(k.startsWith('sp-') ? sp[Number(k.slice(3))] : rp[k]));
    setSlot(next ?? slot); setPQuery('');
  }

  function clearPitcher(k: string) {
    if (k.startsWith('sp-')) setStarters(prev => prev.map((x, i) => (i === Number(k.slice(3)) ? null : x)));
    else setBullpen(prev => ({ ...prev, [k]: null }));
  }

  const pitchingNames = () => ({
    starters: starters.filter((x): x is PitcherPick => !!x).map(x => x.name),
    bullpen: Object.fromEntries(ROLES.filter(r => bullpen[r]).map(r => [r, bullpen[r]!.name])) as Record<string, string>,
  });

  function handleSelect(player: Player) {
    if (lineup.some((p) => p?.id === player.id)) { alert('이미 추가된 선수입니다.'); return; }
    const emptyIdx = lineup.findIndex((p) => p === null);
    if (emptyIdx === -1) { alert('타순이 모두 찼습니다.'); return; }
    const next = [...lineup]; next[emptyIdx] = player; setLineup(next);
    setQuery(''); setShowDropdown(false);
    const history = [player.name, ...searchHistory.filter(h => h !== player.name)].slice(0, 5);
    setSearchHistory(history); localStorage.setItem('search_history', JSON.stringify(history));
  }

  function handleRemove(idx: number) { const next = [...lineup]; next[idx] = null; setLineup(next); }

  function handleDragEnd(event: any) {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const oldIndex = lineup.findIndex((_, i) => i === Number(active.id));
    const newIndex = lineup.findIndex((_, i) => i === Number(over.id));
    if (oldIndex !== -1 && newIndex !== -1) setLineup((prev) => arrayMove(prev, oldIndex, newIndex));
  }

  async function handleDeleteRecord(id: number) {
    try { await deleteRecord(id); setRecords((prev) => prev.filter((r) => r.id !== id)); }
    catch { alert('삭제에 실패했습니다.'); }
  }

  function handleSimulate() {
    if (!complete) return;
    navigate('/simulator', {
      state: { lineup: toLineupData(filledPlayers, true), teamName: teamName.trim() || '나만의 팀', opponent, pitchers: pitchingNames() },
    });
  }

  async function handleOptimize() {
    if (!complete) return;
    setOptimizing(true);
    try {
      const res = await optimizeLineup(toLineupData(filledPlayers));
      setLineup(res.optimized_order.map((name: string) => filledPlayers.find((p) => p.name === name) ?? null));
    } catch { alert('최적화 중 오류가 발생했습니다.'); }
    finally { setOptimizing(false); }
  }

  function handleSaveTeam() {
    if (!complete) { alert('선수 9명을 모두 추가해야 저장할 수 있습니다.'); return; }
    const team: SavedTeam = {
      id: Date.now(), team_name: teamName.trim() || '나만의 팀', opponent,
      lineup: filledPlayers.map((p) => ({ name: p.name, position: p.position })),
      created_at: new Date().toISOString(), pitching: pitchingNames(),
    };
    const updated = [team, ...savedTeams].slice(0, 10);
    setSavedTeams(updated); localStorage.setItem('saved_teams', JSON.stringify(updated));
    alert(`"${team.team_name}" 저장 완료`);
  }

  async function handleLoadTeam(saved: SavedTeam) {
    setTeamName(saved.team_name); setOpponent(saved.opponent); setLineup(Array(9).fill(null));
    setStarters(Array(5).fill(null)); setBullpen(EMPTY_BULLPEN); setSlot('sp-0');
    const restored: (Player | null)[] = Array(9).fill(null);
    for (let i = 0; i < saved.lineup.length; i++) {
      try {
        const data = await fetchPlayers(saved.lineup[i].name);
        const matched = data.find(p => p.player_name === saved.lineup[i].name);
        if (matched) restored[i] = dbToPlayer(matched);
      } catch { /* 해당 선수만 비워둠 */ }
    }
    setLineup(restored); setShowSavedTeams(false);

    const spNames = saved.pitching?.starters ?? [];
    const sp = await Promise.all(Array.from({ length: 5 }, (_, i) => (spNames[i] ? findPitcher(spNames[i]) : Promise.resolve(null))));
    const rpEntries = await Promise.all(ROLES.map(async r => [r, saved.pitching?.bullpen?.[r] ? await findPitcher(saved.pitching.bullpen[r]) : null] as const));
    setStarters(sp); setBullpen(Object.fromEntries(rpEntries) as Bullpen);
  }

  function handleDeleteSavedTeam(id: number) {
    const updated = savedTeams.filter(t => t.id !== id);
    setSavedTeams(updated); localStorage.setItem('saved_teams', JSON.stringify(updated));
  }

  const resultStyle = (r: string) => r === '승' ? 'text-blue-400' : r === '패' ? 'text-red-400' : 'text-gray-400';

  return (
    <div className="min-h-screen bg-gray-900 pb-20">

      {showSavedTeams && (
        <div className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center" onClick={() => setShowSavedTeams(false)}>
          <div className="bg-gray-900 border border-gray-700 rounded-lg p-6 w-[480px] max-h-[80vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-5">
              <h2 className="text-white font-semibold text-lg">저장된 팀</h2>
              <button onClick={() => setShowSavedTeams(false)} className="text-sm text-gray-400 hover:text-orange-400 transition-colors">닫기</button>
            </div>
            {savedTeams.length === 0 ? (
              <p className="text-gray-500 text-sm text-center py-8">저장된 팀이 없습니다.</p>
            ) : (
              <div className="space-y-3">
                {savedTeams.map((team) => (
                  <div key={team.id} className="border border-gray-800 rounded-lg p-4">
                    <div className="flex items-center justify-between mb-3">
                      <div>
                        <p className="text-white font-semibold">{team.team_name}</p>
                        <p className="text-gray-400 text-xs mt-0.5 flex items-center gap-1">
                          vs <TeamLogoLabel name={team.opponent} /> · {new Date(team.created_at).toLocaleDateString('ko-KR')}
                        </p>
                      </div>
                      <div className="flex gap-2">
                        <button onClick={() => handleLoadTeam(team)} className="text-xs font-semibold border border-orange-500 text-orange-400 hover:bg-orange-500 hover:text-white px-3 py-1.5 rounded-md transition-colors">불러오기</button>
                        <button onClick={() => handleDeleteSavedTeam(team.id)} className="text-xs border border-gray-700 text-gray-400 hover:border-red-500 hover:text-red-400 px-3 py-1.5 rounded-md transition-colors">삭제</button>
                      </div>
                    </div>
                    <div className="flex flex-wrap gap-1">
                      {team.lineup.map((p, i) => <span key={i} className="text-xs text-gray-400 border border-gray-800 px-2 py-0.5 rounded">{i + 1}. {p.name}</span>)}
                    </div>
                    {team.pitching && team.pitching.starters.length > 0 && (
                      <p className="text-xs text-gray-500 mt-2">선발: {team.pitching.starters.join(', ')}</p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      <header className="px-10 pt-10 pb-6 border-b border-gray-800">
        <div className="flex items-start justify-between gap-6 flex-wrap">
          <div>
            <h1 className="text-white text-3xl font-bold">나만의 팀 만들기</h1>
            <p className="text-gray-400 mt-1">KBO 선수로 타순과 투수진을 구성하고 시뮬레이션을 돌려보세요.</p>
            <div className="flex items-center gap-6 mt-5 flex-wrap">
              <label className="flex items-center gap-2 text-sm text-gray-400">
                팀 이름
                <input type="text" value={teamName} onChange={(e) => setTeamName(e.target.value)} placeholder="나만의 팀"
                  className="bg-gray-800 text-white border border-gray-700 rounded-lg px-3 py-2 w-40 font-semibold focus:outline-none focus:border-orange-400 transition-colors" />
              </label>
              <label className="flex items-center gap-2 text-sm text-gray-400">
                상대팀
                {getTeamLogo(opponent) && <img src={getTeamLogo(opponent)} alt={opponent} className="w-5 h-5 object-contain" />}
                <select value={opponent} onChange={(e) => setOpponent(e.target.value)}
                  className="bg-gray-800 text-white border border-gray-700 rounded-lg px-3 py-2 w-28 focus:outline-none focus:border-orange-400 transition-colors">
                  {KBO_TEAMS.map(t => <option key={t} value={t}>{t}</option>)}
                </select>
              </label>
            </div>
          </div>

          <div className="flex gap-2 flex-wrap justify-end">
            <button onClick={() => setShowSavedTeams(true)} className={`${btn} ${btnOn}`}>저장된 팀</button>
            <button onClick={handleSaveTeam} disabled={!complete} className={`${btn} ${complete ? btnOn : btnOff}`}>팀 저장</button>
            <button onClick={handleOptimize} disabled={!complete || optimizing} className={`${btn} ${complete && !optimizing ? btnOn : btnOff}`}>
              {optimizing ? '계산 중' : '최적 타순'}
            </button>
            <button onClick={handleSimulate} disabled={!complete}
              className={`${btn} ${complete ? 'bg-orange-500 border-orange-500 text-white hover:bg-orange-400' : btnOff}`}>시뮬레이션</button>
          </div>
        </div>

        <div className="mt-6 flex items-center gap-4">
          <div className="flex-1 max-w-md h-1.5 bg-gray-800 rounded-full overflow-hidden">
            <div className="h-full bg-orange-500 rounded-full transition-all duration-500" style={{ width: `${(filledCount / 9) * 100}%` }} />
          </div>
          <span className="text-sm text-gray-400"><span className="text-orange-400 font-semibold">{filledCount}</span> / 9명</span>
          {complete && <span className="text-green-400 text-sm">라인업 완성</span>}
        </div>
      </header>

      <main className="px-10 py-8 grid grid-cols-[1fr_300px] gap-8 items-start">

        <div className="space-y-8 min-w-0">
          <section>
            <h2 className={sectionTitle}>타자 검색</h2>
            <div ref={searchRef} className="relative">
              <input type="text" value={query} onChange={(e) => setQuery(e.target.value)}
                onFocus={() => { if (query || searchHistory.length > 0) setShowDropdown(true); }}
                placeholder="타자 이름 또는 팀명으로 검색"
                className="w-full bg-gray-800 text-white placeholder-gray-500 rounded-lg px-4 py-3 border border-gray-700 focus:outline-none focus:border-orange-400 transition-colors" />

              {showDropdown && query && results.length > 0 && (
                <div className="absolute top-full left-0 right-0 mt-1 bg-gray-900 border border-gray-700 rounded-lg shadow-2xl overflow-hidden z-50 max-h-64 overflow-y-auto">
                  {results.map((player) => {
                    const added = lineup.some(p => p?.id === player.id);
                    const ops = player?.stats?.find(s => s.label === 'OPS');
                    return (
                      <button key={player.id} onClick={() => !added && handleSelect(player)} disabled={added}
                        className={`w-full flex items-center justify-between px-4 py-3 text-left border-b border-gray-800 last:border-0 transition-colors ${added ? 'opacity-40 cursor-not-allowed' : 'hover:bg-gray-800'}`}>
                        <div className="flex items-center gap-3">
                          <span className="text-xs text-gray-300 border border-gray-700 px-2 py-0.5 rounded w-16 text-center">{player.position}</span>
                          <div>
                            <p className="text-white font-semibold text-sm">{player.name}{added && <span className="ml-2 text-xs text-gray-500">추가됨</span>}</p>
                            <p className="text-gray-400 text-xs"><TeamLogoLabel name={player.team} /></p>
                          </div>
                        </div>
                        {ops && <div className="text-xs text-right"><p className="text-gray-500">OPS</p><p className="text-orange-400 font-semibold">{ops.value.toFixed(3)}</p></div>}
                      </button>
                    );
                  })}
                </div>
              )}
              {showDropdown && query && results.length === 0 && (
                <div className="absolute top-full left-0 right-0 mt-1 bg-gray-900 border border-gray-700 rounded-lg px-4 py-3 text-gray-500 text-sm z-50">검색 결과가 없습니다.</div>
              )}
              {showDropdown && !query && searchHistory.length > 0 && (
                <div className="absolute top-full left-0 right-0 mt-1 bg-gray-900 border border-gray-700 rounded-lg shadow-xl overflow-hidden z-50">
                  <div className="px-4 py-2 text-gray-500 text-xs border-b border-gray-800 flex justify-between items-center">
                    <span>최근 추가한 선수</span>
                    <button onClick={() => { setSearchHistory([]); localStorage.removeItem('search_history'); }} className="text-gray-500 hover:text-orange-400 transition-colors">전체 삭제</button>
                  </div>
                  {searchHistory.map((name, i) => (
                    <button key={i} onClick={() => setQuery(name)} className="w-full px-4 py-2.5 text-left text-gray-300 text-sm hover:bg-gray-800 border-b border-gray-800 last:border-0 transition-colors">{name}</button>
                  ))}
                </div>
              )}
            </div>
          </section>

          <section>
            <h2 className={sectionTitle}>타순 배치</h2>
            <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
              <SortableContext items={lineup.map((_, i) => i).filter(i => lineup[i] !== null)} strategy={verticalListSortingStrategy}>
                <div className="space-y-2">
                  {lineup.map((player, idx) =>
                    player ? (
                      <div key={idx} className="flex items-center gap-3">
                        <span className={`w-8 text-center font-bold ${idx < 3 ? 'text-orange-400' : 'text-gray-500'}`}>{idx + 1}</span>
                        <div className="flex-1"><LineupCard player={player} order={idx + 1} /></div>
                        <button onClick={() => handleRemove(idx)} className="text-sm text-gray-500 hover:text-red-400 transition-colors px-2">제거</button>
                      </div>
                    ) : (
                      <div key={idx} className="flex items-center gap-3">
                        <span className="w-8 text-center text-gray-600 font-bold">{idx + 1}</span>
                        <div className="flex-1 h-14 border border-dashed border-gray-700 rounded-lg flex items-center px-4 text-gray-600 text-sm">
                          {idx + 1}번 타자를 검색해서 추가하세요
                        </div>
                        <span className="w-[42px]" />
                      </div>
                    )
                  )}
                </div>
              </SortableContext>
            </DndContext>
          </section>

          <section>
            <div className="flex items-baseline justify-between mb-3">
              <h2 className="text-white font-semibold">투수진</h2>
              <span className="text-xs text-gray-500">선발 1번이 시뮬레이션에 반영됩니다 · {pitchCount}/9</span>
            </div>

            <div className="grid grid-cols-[1fr_1fr] gap-6">
              <div className="space-y-1.5">
                {SLOT_KEYS.map(k => {
                  const pk = getPick(k); const active = slot === k;
                  return (
                    <div key={k} onClick={() => setSlot(k)}
                      className={`flex items-center gap-3 px-3 py-2 rounded-lg border cursor-pointer transition-colors ${active ? 'border-orange-500 bg-orange-500/5' : 'border-gray-800 hover:border-gray-600'}`}>
                      <span className={`text-xs w-16 shrink-0 ${active ? 'text-orange-400 font-semibold' : 'text-gray-500'}`}>{slotLabel(k)}</span>
                      {pk ? (
                        <>
                          <span className="text-white text-sm font-semibold flex-1 truncate">{pk.name}</span>
                          <span className="text-xs text-gray-500 shrink-0"><TeamLogoLabel name={pk.team} /></span>
                          <button onClick={(e) => { e.stopPropagation(); clearPitcher(k); setSlot(k); }} className="text-xs text-gray-500 hover:text-red-400 transition-colors">제거</button>
                        </>
                      ) : <span className="text-gray-600 text-sm flex-1">선택되지 않음</span>}
                    </div>
                  );
                })}
              </div>

              <div>
                <input type="text" value={pQuery} onChange={(e) => setPQuery(e.target.value)}
                  placeholder={`${slotLabel(slot)} 투수 검색`}
                  className="w-full bg-gray-800 text-white placeholder-gray-500 rounded-lg px-4 py-2.5 border border-gray-700 focus:outline-none focus:border-orange-400 transition-colors" />
                <div className="mt-2 space-y-1">
                  {pResults.map(pk => (
                    <button key={`${pk.name}-${pk.team}`} onClick={() => pickPitcher(pk)}
                      className="w-full flex items-center justify-between px-3 py-2 border border-gray-800 hover:border-orange-400 rounded-lg text-left transition-colors">
                      <span>
                        <span className="text-white text-sm font-semibold">{pk.name}</span>
                        <span className="text-gray-400 text-xs ml-2"><TeamLogoLabel name={pk.team} /></span>
                      </span>
                      <span className="text-xs text-gray-400">ERA {pk.era ?? '-'} · SV {pk.sv} · HLD {pk.hld}</span>
                    </button>
                  ))}
                  {pQuery.trim() && pResults.length === 0 && <p className="text-gray-500 text-sm px-1 py-2">검색 결과가 없습니다.</p>}
                  {!pQuery.trim() && <p className="text-gray-600 text-xs px-1 py-2">왼쪽에서 칸을 고른 뒤 투수를 검색하세요. 어느 구단 투수든 선택할 수 있습니다.</p>}
                </div>
              </div>
            </div>
          </section>
        </div>

        <aside className="space-y-6">
          <section>
            <h2 className={sectionTitle}>팀 요약</h2>
            <dl className="border border-gray-800 rounded-lg divide-y divide-gray-800 text-sm">
              <div className="px-4 py-3 flex justify-between"><dt className="text-gray-400">타자 구성</dt><dd className="text-white font-semibold">{filledCount} / 9</dd></div>
              <div className="px-4 py-3 flex justify-between"><dt className="text-gray-400">투수진</dt><dd className="text-white font-semibold">{pitchCount} / 9</dd></div>
              <div className="px-4 py-3 flex justify-between"><dt className="text-gray-400">평균 OPS</dt><dd className={`font-semibold ${avgOPS !== '-' ? 'text-orange-400' : 'text-gray-600'}`}>{avgOPS}</dd></div>
              <div className="px-4 py-3 flex justify-between">
                <dt className="text-gray-400">전적</dt>
                <dd className="font-semibold"><span className="text-blue-400">{wins}승</span> <span className="text-red-400">{losses}패</span>{draws > 0 && <span className="text-gray-400"> {draws}무</span>}</dd>
              </div>
            </dl>
          </section>

          <section>
            <h2 className={sectionTitle}>현재 타순</h2>
            <div className="border border-gray-800 rounded-lg overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-gray-800/60 text-gray-400 text-xs">
                  <tr><th className="text-left px-4 py-2 w-10">순번</th><th className="text-left px-2 py-2">포지션</th><th className="text-left px-2 py-2">선수명</th></tr>
                </thead>
                <tbody>
                  {lineup.map((player, idx) => (
                    <tr key={idx} className="border-t border-gray-800">
                      <td className={`px-4 py-2 font-semibold ${idx < 3 ? 'text-orange-400' : 'text-gray-500'}`}>{idx + 1}</td>
                      <td className="px-2 py-2 text-gray-400">{player?.position ?? '-'}</td>
                      <td className="px-2 py-2 text-white">{player?.name ?? '-'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section>
            <h2 className={sectionTitle}>전적 기록</h2>
            {records.length === 0 ? (
              <div className="border border-gray-800 rounded-lg p-5 text-center">
                <p className="text-gray-500 text-sm">아직 경기 기록이 없습니다.</p>
                <p className="text-gray-600 text-xs mt-1">시뮬레이션을 돌려보세요.</p>
              </div>
            ) : (
              <div className="space-y-2">
                {records.map((rec) => (
                  <div key={rec.id} className="border border-gray-800 hover:border-gray-700 rounded-lg px-4 py-3 flex items-center justify-between transition-colors">
                    <div>
                      <p className="text-white text-sm font-semibold flex items-center gap-1.5">vs <TeamLogoLabel name={rec.opponent_name} /></p>
                      <p className="text-gray-500 text-xs mt-0.5">{new Date(rec.played_at).toLocaleDateString('ko-KR')}</p>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-gray-300 text-sm font-semibold">{rec.my_score} : {rec.opp_score}</span>
                      <span className={`text-sm font-semibold ${resultStyle(rec.result)}`}>{rec.result}</span>
                      <button onClick={() => handleDeleteRecord(rec.id)} className="text-xs text-gray-500 hover:text-red-400 transition-colors">삭제</button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>
        </aside>
      </main>
    </div>
  );
}