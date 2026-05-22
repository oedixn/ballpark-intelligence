import { useState, useEffect } from 'react';
import { useSearchParams, useParams, useNavigate } from 'react-router-dom';
import PercentileBar from '../components/player/PercentileBar';
import PlayerRadarChart from '../components/player/RadarChart';
import InsightBox from '../components/player/InsightBox';
import PlayerCard from '../components/player/PlayerCard';
import LoadingSpinner from '../components/common/LoadingSpinner';
import ErrorBox from '../components/common/ErrorBox';
import { fetchPlayers, fetchPlayerById, fetchPlayerSeasons } from '../api/playerApi';
import type { PlayerDB, PlayerSeasons } from '../api/playerApi';
import type { Player } from '../data/mockPlayers';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, BarChart, Bar, PieChart, Pie, Cell } from 'recharts';

const MB_COLORS = ['#f97316','#60a5fa','#4ade80','#f87171','#a78bfa'];
const API = 'http://localhost:8000';
const TS = { contentStyle:{backgroundColor:'#1f2937',border:'1px solid #374151',borderRadius:'8px'}, labelStyle:{color:'#f97316'}, itemStyle:{color:'#d1d5db'} };
const LS = { color:'#9ca3af', fontSize:'12px' };

const POS_COLORS: Record<string,string> = {
  '포수':'bg-blue-600','1루수':'bg-red-600','2루수':'bg-green-600','3루수':'bg-yellow-600',
  '유격수':'bg-purple-600','좌익수':'bg-pink-600','중견수':'bg-teal-600','우익수':'bg-orange-600',
  '지명타자':'bg-gray-600','투수':'bg-blue-700',
};

function PlayerAvatar({ position }: { position: string }) {
  return (
    <div className={`w-20 h-20 rounded-full ${POS_COLORS[position]??'bg-orange-500'} flex items-center justify-center shrink-0`}>
      <span className="text-white text-sm font-black">{position}</span>
    </div>
  );
}

function dbToPlayer(p: PlayerDB): Player {
  const ip = (p as any).era !== undefined && (p as any).era !== null && !(p as any).avg;
  return {
    id: Number(p.player_id), name: p.player_name, team: p.team_name,
    position: p.position ?? (ip ? '투수' : '-'),
    stats: ip ? [
      { label:'ERA',   value:Number((p as any).era??0),         percentile:Number((p as any).era_percentile??0),  unit:'ERA'  },
      { label:'승',    value:Number((p as any).w??0),           percentile:Number((p as any).w_percentile??0),    unit:'승'   },
      { label:'세이브', value:Number((p as any).sv??0),          percentile:Number((p as any).sv_percentile??0),   unit:'세'   },
      { label:'탈삼진', value:Number((p as any).pitcher_so??0),  percentile:Number((p as any).so_percentile??0),   unit:'K'    },
      { label:'WHIP',  value:Number((p as any).whip??0),        percentile:Number((p as any).whip_percentile??0), unit:'WHIP' },
    ] : [
      { label:'wOBA', value:Number(p.woba??0),    percentile:Number((p as any).woba_percentile??0), unit:'wOBA' },
      { label:'OPS',  value:Number(p.ops??0),     percentile:Number((p as any).ops_percentile??0),  unit:'OPS'  },
      { label:'HR',   value:Number(p.hr??0),      percentile:Number((p as any).hr_percentile??0),   unit:'HR'   },
      { label:'BB%',  value:Number(p.bb_rate??0), percentile:Number((p as any).bb_percentile??0),   unit:'%'    },
      { label:'K%',   value:Number(p.k_rate??0),  percentile:Number((p as any).k_percentile??0),    unit:'%'    },
    ],
    radar: ip ? [
      { stat:'구위',   value:Math.min(99,Math.max(1,Math.round(100-Number((p as any).era??5)*10))) },
      { stat:'제구',   value:Math.min(99,Math.max(1,Math.round(100-Number((p as any).whip??2)*30))) },
      { stat:'탈삼진', value:Math.min(99,Math.round(Number((p as any).pitcher_so??0)*1.5)) },
      { stat:'이닝', value:60 }, { stat:'수비', value:60 },
      { stat:'승리', value:Math.min(99,Math.round(Number((p as any).w??0)*8)) },
    ] : [
      { stat:'컨택',   value:Math.min(99,Math.round(Number(p.avg??0)*300)) },
      { stat:'파워',   value:Math.min(99,Math.round(Number((p as any).iso??0)*400)) },
      { stat:'선구안', value:Math.min(99,Math.round(Number(p.bb_rate??0)*5)) },
      { stat:'스피드', value:50 }, { stat:'수비', value:60 },
      { stat:'출루',   value:Math.min(99,Math.round(Number(p.obp??0)*200)) },
    ],
  };
}

export default function PlayerPage() {
  const navigate = useNavigate();
  const [player, setPlayer]       = useState<Player | null>(null);
  const [raw, setRaw]             = useState<PlayerDB | null>(null);
  const [players, setPlayers]     = useState<Player[]>([]);
  const [loading, setLoading]     = useState(false);
  const [listLoading, setLL]      = useState(false);
  const [error, setError]         = useState(false);
  const [query, setQuery]         = useState('');
  const [showList, setShowList]   = useState(true);
  const [season, setSeason]       = useState<number | null>(null);
  const [seasons, setSeasons]     = useState<PlayerSeasons | null>(null);
  const [mb, setMb]               = useState<any>(null);
  const [mbDist, setMbDist]       = useState<any[]>([]);
  const [similar, setSimilar]     = useState<any[]>([]);
  const [searchParams]            = useSearchParams();
  const { playerId }              = useParams<{ playerId: string }>();

  async function loadPlayer(id: string, s?: number) {
    setLoading(true); setError(false);
    try {
      const data = await fetchPlayerById(id, s);
      setRaw(data); setPlayer(dbToPlayer(data)); setSeason(data.current_season ?? null);
      try { setSeasons(await fetchPlayerSeasons(id)); } catch { setSeasons(null); }
      const isH = (data as any).avg !== null && (data as any).avg !== undefined;
      try {
        const urls = isH
          ? [`${API}/api/players/${id}/moneyball`, `${API}/api/moneyball/distribution`, `${API}/api/players/${id}/similar`]
          : [`${API}/api/players/${id}/similar`];
        const res = await Promise.all(urls.map(u => fetch(u)));
        if (isH) {
          if (res[0].ok) setMb(await res[0].json());
          if (res[1].ok) { const d = await res[1].json(); setMbDist(d.distribution); }
          if (res[2].ok) { const d = await res[2].json(); setSimilar(d.similar_players); }
        } else {
          if (res[0].ok) { const d = await res[0].json(); setSimilar(d.similar_players); }
        }
      } catch { setMb(null); setMbDist([]); setSimilar([]); }
    } catch { setError(true); }
    finally { setLoading(false); }
  }

  useEffect(() => { if (!playerId) return; setShowList(false); loadPlayer(playerId); }, [playerId]);
  useEffect(() => {
    if (playerId) return;
    const q = searchParams.get('search');
    if (q) { setQuery(q); setShowList(true); setPlayer(null); }
  }, [searchParams, playerId]);
  useEffect(() => {
    if (!query.trim()) { setPlayers([]); return; }
    const t = setTimeout(async () => {
      setLL(true);
      try { setPlayers((await fetchPlayers(query)).map(dbToPlayer)); }
      catch { setPlayers([]); } finally { setLL(false); }
    }, 300);
    return () => clearTimeout(t);
  }, [query]);

  function handleBack() {
    setPlayer(null); setShowList(true); setRaw(null); setSeason(null);
    setMb(null); setMbDist([]); setSimilar([]);
  }

  const avSeasons = raw?.available_seasons ?? [];
  const ip = raw && (raw as any).era !== undefined && (raw as any).era !== null && !(raw as any).avg;

  if (showList && !playerId) return (
    <div className="min-h-screen bg-gray-900 px-10 py-8">
      <h1 className="text-white text-3xl font-black mb-2">선수 프로필</h1>
      <p className="text-gray-400 text-sm mb-6">선수 이름 또는 팀명으로 검색하세요</p>
      <div className="relative max-w-lg mb-6">
        <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 text-sm">🔍</span>
        <input type="text" value={query} onChange={(e) => setQuery(e.target.value)}
          placeholder="선수 이름 또는 팀명 검색..."
          className="w-full bg-gray-800 text-white placeholder-gray-500 rounded-lg pl-9 pr-4 py-2.5 text-sm border border-gray-700 focus:outline-none focus:border-orange-400 transition-colors" />
        {query && <button onClick={() => setQuery('')} className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-600 hover:text-gray-400 text-xs">✕</button>}
      </div>
      <div className="max-w-lg space-y-2">
        {listLoading ? <p className="text-gray-500 text-sm text-center py-10 animate-pulse">검색 중...</p>
          : query && players.length===0 ? <p className="text-gray-500 text-sm text-center py-10">검색 결과가 없습니다</p>
          : !query ? <p className="text-gray-600 text-sm text-center py-10">선수 이름을 입력해서 검색하세요</p>
          : players.map((p) => <PlayerCard key={p.id} player={p} onClick={(p) => { setShowList(false); loadPlayer(String(p.id)); }} />)}
      </div>
    </div>
  );

  if (loading) return <LoadingSpinner />;
  if (error)   return <ErrorBox onRetry={handleBack} />;
  if (!player) return null;

  return (
    <div className="min-h-screen bg-gray-900">
      <div className="bg-gradient-to-r from-gray-800 to-gray-900 border-b border-gray-700 px-10 py-8">
        <div className="flex items-center gap-6">
          <button onClick={handleBack} className="text-gray-400 hover:text-white text-sm mr-2">← 목록</button>
          <PlayerAvatar position={player.position} />
          <div>
            <div className="flex items-center gap-3 mb-1">
              <h1 className="text-white text-4xl font-black">{player.name}</h1>
              <span className="bg-orange-500 text-white text-xs font-bold px-2 py-1 rounded">{player.position}</span>
            </div>
            <p className="text-gray-400 text-sm">{player.team}</p>
            {avSeasons.length > 1 && (
              <div className="flex gap-2 mt-3">
                {avSeasons.map((s) => (
                  <button key={s} onClick={() => { const id=playerId??raw?.player_id; if(id) loadPlayer(id,s); }}
                    className={`px-3 py-1 rounded-lg text-xs font-bold transition-colors ${season===s?'bg-orange-500 text-white':'bg-gray-700 text-gray-400 hover:text-white'}`}>
                    {s}
                  </button>
                ))}
              </div>
            )}
          </div>
          <div className="ml-auto flex gap-6">
            {!ip ? (
              <>
                {[['AVG',Number(raw?.avg??0).toFixed(3)],['OBP',Number(raw?.obp??0).toFixed(3)],['SLG',Number(raw?.slg??0).toFixed(3)],['OPS',Number(raw?.ops??0).toFixed(3)],['wOBA',Number(raw?.woba??0).toFixed(3)]].map(([l,v]) => (
                  <div key={l} className="text-center"><p className="text-orange-400 text-xl font-black">{v}</p><p className="text-gray-400 text-xs mt-1">{l}</p></div>
                ))}
                {(raw as any)?.wrc_plus != null && (
                  <div className="text-center border-l border-gray-700 pl-6">
                    <p className={`text-xl font-black ${Number((raw as any).wrc_plus)>=130?'text-orange-400':Number((raw as any).wrc_plus)>=100?'text-green-400':'text-gray-400'}`}>{Number((raw as any).wrc_plus)}</p>
                    <p className="text-gray-400 text-xs mt-1">wRC+</p>
                  </div>
                )}
              </>
            ) : (
              [['ERA',Number((raw as any)?.era??0).toFixed(2)],['W-L',`${(raw as any)?.w??0}-${(raw as any)?.l??0}`],['IP',(raw as any)?.ip??'0'],['SO',String((raw as any)?.pitcher_so??0)],['WHIP',Number((raw as any)?.whip??0).toFixed(2)]].map(([l,v]) => (
                <div key={l} className="text-center"><p className="text-orange-400 text-xl font-black">{v}</p><p className="text-gray-400 text-xs mt-1">{l}</p></div>
              ))
            )}
          </div>
        </div>
      </div>

      <div className="px-10 py-8">
        <div className="flex gap-6 mb-6">
          <div className="bg-gray-800 rounded-xl p-6 w-96">
            <p className="text-gray-400 text-xs mb-4 uppercase tracking-widest">
              주요 지표 {season && <span className="ml-2 text-orange-400">{season} 시즌</span>}
            </p>
            {player.stats.map((s) => <PercentileBar key={s.label} label={s.label} value={s.value} percentile={s.percentile} unit={s.unit} />)}
          </div>
          <div className="bg-gray-800 rounded-xl p-6 w-80">
            <p className="text-gray-400 text-xs mb-2 uppercase tracking-widest text-center">능력치 레이더</p>
            <PlayerRadarChart data={player.radar} />
          </div>
        </div>

        <div className="max-w-xl"><InsightBox name={player.name} stats={player.stats} /></div>

        {/* 머니볼 */}
        {mb && (
          <div className="bg-gradient-to-br from-gray-800 to-gray-900 border border-orange-500/20 rounded-xl p-6 mt-6 max-w-xl">
            <p className="text-orange-400 text-xs mb-4 uppercase tracking-widest font-bold">⚾ 머니볼 엔진 분석</p>
            <div className="grid grid-cols-3 gap-3 mb-5">
              <div className="bg-gray-900 rounded-lg p-3 text-center"><p className="text-gray-500 text-xs mb-1">선수 유형</p><p className="text-white text-sm font-black">{mb.cluster_type}</p></div>
              <div className="bg-gray-900 rounded-lg p-3 text-center"><p className="text-gray-500 text-xs mb-1">UV Score</p>
                <p className={`text-sm font-black ${mb.uv_score>=20?'text-green-400':mb.uv_score>=5?'text-blue-400':mb.uv_score>=-5?'text-gray-300':mb.uv_score>=-20?'text-yellow-400':'text-red-400'}`}>
                  {mb.uv_score>0?'+':''}{mb.uv_score}</p></div>
              <div className="bg-gray-900 rounded-lg p-3 text-center"><p className="text-gray-500 text-xs mb-1">평가</p>
                <p className={`text-sm font-black ${mb.uv_label==='매우 저평가'?'text-green-400':mb.uv_label==='저평가'?'text-blue-400':mb.uv_label==='적정 평가'?'text-gray-300':mb.uv_label==='고평가'?'text-yellow-400':'text-red-400'}`}>
                  {mb.uv_label}</p></div>
            </div>
            <p className="text-gray-400 text-xs mb-3 leading-relaxed">{mb.cluster_desc}</p>
            <p className="text-gray-500 text-xs mb-5 leading-relaxed">
              wOBA 백분위 <span className="text-orange-400 font-bold">{mb.woba_pct}%</span> — PA 백분위 <span className="text-blue-400 font-bold">{mb.pa_pct}%</span> = UV Score <span className="font-bold text-white">{mb.uv_score}</span>
            </p>
            {mbDist.length > 0 && (
              <div className="mb-5">
                <p className="text-gray-500 text-xs mb-3">리그 전체 유형 분포</p>
                <div className="flex items-center gap-4">
                  <PieChart width={120} height={120}>
                    <Pie data={mbDist} cx={55} cy={55} innerRadius={35} outerRadius={55} dataKey="count" nameKey="type">
                      {mbDist.map((e,i) => <Cell key={e.type} fill={MB_COLORS[i%MB_COLORS.length]} opacity={e.type===mb.cluster_type?1:0.4} stroke={e.type===mb.cluster_type?'#fff':'none'} strokeWidth={e.type===mb.cluster_type?2:0} />)}
                    </Pie>
                  </PieChart>
                  <div className="flex flex-col gap-1.5">
                    {mbDist.map((e,i) => (
                      <div key={e.type} className={`flex items-center gap-2 text-xs ${e.type===mb.cluster_type?'text-white font-bold':'text-gray-500'}`}>
                        <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{backgroundColor:MB_COLORS[i%MB_COLORS.length],opacity:e.type===mb.cluster_type?1:0.4}} />
                        {e.type} {e.pct}% {e.type===mb.cluster_type&&<span className="text-orange-400">← 현재</span>}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}
            {mb.same_cluster_players?.length > 0 && (
              <div><p className="text-gray-500 text-xs mb-2">같은 유형 선수</p>
                <div className="flex gap-2 flex-wrap">
                  {mb.same_cluster_players.map((n: string) => <span key={n} className="bg-gray-700 text-gray-300 text-xs px-2 py-1 rounded-lg">{n}</span>)}
                </div>
              </div>
            )}
          </div>
        )}

        {/* 유사 선수 */}
        {similar.length > 0 && (
          <div className="bg-gray-800 rounded-xl p-6 mt-6 max-w-xl">
            <p className="text-gray-400 text-xs mb-4 uppercase tracking-widest">🔍 유사 선수 추천</p>
            <div className="space-y-3">
              {similar.map((p, i) => (
                <div key={`${p.player_id}-${i}`}
                  className="flex items-center gap-4 bg-gray-900 rounded-lg px-4 py-3 hover:bg-gray-700 transition-colors cursor-pointer"
                  onClick={() => { setSimilar([]); setMb(null); setMbDist([]); navigate(`/player/${p.player_id}`); }}>
                  <div className="w-8 h-8 rounded-full bg-orange-500/20 flex items-center justify-center shrink-0">
                    <span className="text-orange-400 text-xs font-black">{i+1}</span>
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-white text-sm font-bold">{p.player_name}
                      <span className="text-gray-500 text-xs ml-2">{p.team_name} · {p.season_year}</span>
                    </p>
                    <p className="text-gray-500 text-xs mt-0.5">
                      {p.era !== undefined
                        ? `ERA ${Number(p.era).toFixed(2)} · WHIP ${Number(p.whip).toFixed(2)} · K/G ${Number(p.so_per_g).toFixed(1)}`
                        : `AVG ${Number(p.avg).toFixed(3)} · OPS ${Number(p.ops).toFixed(3)} · wOBA ${Number(p.woba).toFixed(3)}`}
                    </p>
                  </div>
                  <div className="text-right shrink-0">
                    <p className={`text-sm font-black ${p.similarity>=99?'text-orange-400':p.similarity>=95?'text-green-400':'text-gray-400'}`}>{p.similarity}%</p>
                    <p className="text-gray-600 text-xs">유사도</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 연도별 차트 */}
        {seasons && seasons.seasons.length >= 2 && (
          <div className="bg-gray-800 rounded-xl p-6 mt-6 max-w-3xl">
            <p className="text-gray-400 text-xs mb-6 uppercase tracking-widest">연도별 성적 추이</p>
            {seasons.type === 'hitter' ? (
              <>
                {[
                  { title:'wOBA / OPS', lines:[{key:'woba',color:'#f97316'},{key:'ops',color:'#60a5fa'}], domain:[0,1.2] as [number,number] },
                  { title:'BB% / K%',  lines:[{key:'bb_rate',color:'#4ade80'},{key:'k_rate',color:'#f87171'}] },
                ].map(({title,lines,domain}) => (
                  <div key={title} className="mb-8">
                    <p className="text-gray-500 text-xs mb-3">{title}</p>
                    <ResponsiveContainer width="100%" height={200}>
                      <LineChart data={seasons.seasons}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                        <XAxis dataKey="season_year" stroke="#9ca3af" tick={{fontSize:12}} />
                        <YAxis stroke="#9ca3af" tick={{fontSize:12}} {...(domain?{domain}:{})} />
                        <Tooltip {...TS} /><Legend wrapperStyle={LS} />
                        {lines.map(l => <Line key={l.key} type="monotone" dataKey={l.key} stroke={l.color} strokeWidth={2} dot={{fill:l.color,r:4}} name={l.key} />)}
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                ))}
                <div>
                  <p className="text-gray-500 text-xs mb-3">홈런 / 타율</p>
                  <ResponsiveContainer width="100%" height={200}>
                    <BarChart data={seasons.seasons}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                      <XAxis dataKey="season_year" stroke="#9ca3af" tick={{fontSize:12}} />
                      <YAxis yAxisId="left" stroke="#9ca3af" tick={{fontSize:12}} />
                      <YAxis yAxisId="right" orientation="right" stroke="#9ca3af" tick={{fontSize:12}} domain={[0,0.5]} />
                      <Tooltip {...TS} /><Legend wrapperStyle={LS} />
                      <Bar yAxisId="left"  dataKey="hr"  fill="#f97316" name="홈런" radius={[4,4,0,0]} />
                      <Bar yAxisId="right" dataKey="avg" fill="#60a5fa" name="타율" radius={[4,4,0,0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </>
            ) : (
              <>
                <div className="mb-8">
                  <p className="text-gray-500 text-xs mb-3">ERA / WHIP</p>
                  <ResponsiveContainer width="100%" height={200}>
                    <LineChart data={seasons.seasons}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                      <XAxis dataKey="season_year" stroke="#9ca3af" tick={{fontSize:12}} />
                      <YAxis stroke="#9ca3af" tick={{fontSize:12}} />
                      <Tooltip {...TS} /><Legend wrapperStyle={LS} />
                      <Line type="monotone" dataKey="era"  stroke="#f97316" strokeWidth={2} dot={{fill:'#f97316',r:4}} name="ERA" />
                      <Line type="monotone" dataKey="whip" stroke="#60a5fa" strokeWidth={2} dot={{fill:'#60a5fa',r:4}} name="WHIP" />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
                <div>
                  <p className="text-gray-500 text-xs mb-3">승 / 탈삼진</p>
                  <ResponsiveContainer width="100%" height={200}>
                    <BarChart data={seasons.seasons}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                      <XAxis dataKey="season_year" stroke="#9ca3af" tick={{fontSize:12}} />
                      <YAxis stroke="#9ca3af" tick={{fontSize:12}} />
                      <Tooltip {...TS} /><Legend wrapperStyle={LS} />
                      <Bar dataKey="w"          fill="#f97316" name="승"    radius={[4,4,0,0]} />
                      <Bar dataKey="pitcher_so" fill="#60a5fa" name="탈삼진" radius={[4,4,0,0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}