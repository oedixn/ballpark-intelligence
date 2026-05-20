import { useState, useEffect } from 'react';
import { useSearchParams, useParams } from 'react-router-dom';
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

function PlayerAvatar({ position }: { position: string }) {
  const positionColors: Record<string, string> = {
    '포수': 'bg-blue-600', '1루수': 'bg-red-600', '2루수': 'bg-green-600',
    '3루수': 'bg-yellow-600', '유격수': 'bg-purple-600', '좌익수': 'bg-pink-600',
    '중견수': 'bg-teal-600', '우익수': 'bg-orange-600', '지명타자': 'bg-gray-600', '투수': 'bg-blue-700',
  };
  const color = positionColors[position] ?? 'bg-orange-500';
  return (
    <div className={`w-20 h-20 rounded-full ${color} flex items-center justify-center shrink-0`}>
      <span className="text-white text-sm font-black">{position}</span>
    </div>
  );
}

function dbToPlayer(p: PlayerDB): Player {
  const isPitcher = (p as any).era !== undefined && (p as any).era !== null && !(p as any).avg;
  return {
    id: Number(p.player_id),
    name: p.player_name,
    team: p.team_name,
    position: p.position ?? (isPitcher ? '투수' : '-'),
    stats: isPitcher ? [
      { label: 'ERA',   value: Number((p as any).era  ?? 0), percentile: Number((p as any).era_percentile  ?? 0), unit: 'ERA'  },
      { label: '승',    value: Number((p as any).w    ?? 0), percentile: Number((p as any).w_percentile    ?? 0), unit: '승'   },
      { label: '세이브', value: Number((p as any).sv  ?? 0), percentile: Number((p as any).sv_percentile   ?? 0), unit: '세'   },
      { label: '탈삼진', value: Number((p as any).pitcher_so ?? 0), percentile: Number((p as any).so_percentile ?? 0), unit: 'K' },
      { label: 'WHIP',  value: Number((p as any).whip ?? 0), percentile: Number((p as any).whip_percentile ?? 0), unit: 'WHIP' },
    ] : [
      { label: 'wOBA', value: Number(p.woba    ?? 0), percentile: Number((p as any).woba_percentile ?? 0), unit: 'wOBA' },
      { label: 'OPS',  value: Number(p.ops     ?? 0), percentile: Number((p as any).ops_percentile  ?? 0), unit: 'OPS'  },
      { label: 'HR',   value: Number(p.hr      ?? 0), percentile: Number((p as any).hr_percentile   ?? 0), unit: 'HR'   },
      { label: 'BB%',  value: Number(p.bb_rate ?? 0), percentile: Number((p as any).bb_percentile   ?? 0), unit: '%'    },
      { label: 'K%',   value: Number(p.k_rate  ?? 0), percentile: Number((p as any).k_percentile    ?? 0), unit: '%'    },
    ],
    radar: isPitcher ? [
      { stat: '구위',   value: Math.min(99, Math.max(1, Math.round(100 - Number((p as any).era ?? 5) * 10))) },
      { stat: '제구',   value: Math.min(99, Math.max(1, Math.round(100 - Number((p as any).whip ?? 2) * 30))) },
      { stat: '탈삼진', value: Math.min(99, Math.round(Number((p as any).pitcher_so ?? 0) * 1.5)) },
      { stat: '이닝',   value: 60 },
      { stat: '수비',   value: 60 },
      { stat: '승리',   value: Math.min(99, Math.round(Number((p as any).w ?? 0) * 8)) },
    ] : [
      { stat: '컨택',   value: Math.min(99, Math.round(Number(p.avg     ?? 0) * 300)) },
      { stat: '파워',   value: Math.min(99, Math.round(Number((p as any).iso ?? 0) * 400)) },
      { stat: '선구안', value: Math.min(99, Math.round(Number(p.bb_rate ?? 0) * 5))   },
      { stat: '스피드', value: 50 },
      { stat: '수비',   value: 60 },
      { stat: '출루',   value: Math.min(99, Math.round(Number(p.obp     ?? 0) * 200)) },
    ],
  };
}

export default function PlayerPage() {
  const [player, setPlayer]                 = useState<Player | null>(null);
  const [rawData, setRawData]               = useState<PlayerDB | null>(null);
  const [players, setPlayers]               = useState<Player[]>([]);
  const [loading, setLoading]               = useState(false);
  const [listLoading, setListLoading]       = useState(false);
  const [error, setError]                   = useState(false);
  const [query, setQuery]                   = useState('');
  const [showList, setShowList]             = useState(true);
  const [selectedSeason, setSelectedSeason] = useState<number | null>(null);
  const [seasons, setSeasons]               = useState<PlayerSeasons | null>(null);
  const [moneyball, setMoneyball]           = useState<any>(null);
  const [mbDist, setMbDist]                 = useState<any[]>([]);
  const [searchParams]                      = useSearchParams();
  const { playerId }                        = useParams<{ playerId: string }>();

  async function loadPlayer(id: string, season?: number) {
    setLoading(true);
    setError(false);
    try {
      const [data, seasonData] = await Promise.all([
        fetchPlayerById(id, season),
        fetchPlayerSeasons(id),
      ]);
      setRawData(data);
      setPlayer(dbToPlayer(data));
      setSelectedSeason(data.current_season ?? null);
      setSeasons(seasonData);

      const isHitter = (data as any).avg !== null && (data as any).avg !== undefined;
      if (isHitter) {
        try {
          const [mb, dist] = await Promise.all([
            fetch(`http://localhost:8000/api/players/${id}/moneyball`),
            fetch(`http://localhost:8000/api/moneyball/distribution`),
          ]);
          if (mb.ok) setMoneyball(await mb.json());
          if (dist.ok) { const d = await dist.json(); setMbDist(d.distribution); }
        } catch { setMoneyball(null); setMbDist([]); }
      } else {
        setMoneyball(null);
        setMbDist([]);
      }
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (!playerId) return;
    setShowList(false);
    loadPlayer(playerId);
  }, [playerId]);

  useEffect(() => {
    if (playerId) return;
    const q = searchParams.get('search');
    if (q) { setQuery(q); setShowList(true); setPlayer(null); }
  }, [searchParams, playerId]);

  useEffect(() => {
    if (!query.trim()) { setPlayers([]); return; }
    const timer = setTimeout(async () => {
      setListLoading(true);
      try {
        const data = await fetchPlayers(query);
        setPlayers(data.map(dbToPlayer));
      } catch { setPlayers([]); }
      finally { setListLoading(false); }
    }, 300);
    return () => clearTimeout(timer);
  }, [query]);

  async function selectPlayer(p: Player) {
    setShowList(false);
    await loadPlayer(String(p.id));
  }

  async function handleSeasonChange(season: number) {
    const id = playerId ?? rawData?.player_id;
    if (id) await loadPlayer(id, season);
  }

  function handleBack() {
    setPlayer(null); setShowList(true);
    setRawData(null); setSelectedSeason(null);
    setMoneyball(null); setMbDist([]);
  }

  const availableSeasons = rawData?.available_seasons ?? [];
  const isPitcher = rawData && (rawData as any).era !== undefined && (rawData as any).era !== null && !(rawData as any).avg;

  if (showList && !playerId) {
    return (
      <div className="min-h-screen bg-gray-900 px-10 py-8">
        <h1 className="text-white text-3xl font-black mb-2">선수 프로필</h1>
        <p className="text-gray-400 text-sm mb-6">선수 이름 또는 팀명으로 검색하세요</p>
        <div className="relative max-w-lg mb-6">
          <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 text-sm">🔍</span>
          <input
            type="text" value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="선수 이름 또는 팀명 검색..."
            className="w-full bg-gray-800 text-white placeholder-gray-500 rounded-lg pl-9 pr-4 py-2.5 text-sm border border-gray-700 focus:outline-none focus:border-orange-400 transition-colors"
          />
          {query && (
            <button onClick={() => setQuery('')} className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-600 hover:text-gray-400 text-xs">✕</button>
          )}
        </div>
        <div className="max-w-lg space-y-2">
          {listLoading ? (
            <p className="text-gray-500 text-sm text-center py-10 animate-pulse">검색 중...</p>
          ) : query && players.length === 0 ? (
            <p className="text-gray-500 text-sm text-center py-10">검색 결과가 없습니다</p>
          ) : !query ? (
            <p className="text-gray-600 text-sm text-center py-10">선수 이름을 입력해서 검색하세요</p>
          ) : (
            players.map((p) => <PlayerCard key={p.id} player={p} onClick={selectPlayer} />)
          )}
        </div>
      </div>
    );
  }

  if (loading) return <LoadingSpinner />;
  if (error)   return <ErrorBox onRetry={handleBack} />;
  if (!player) return null;

  return (
    <div className="min-h-screen bg-gray-900">
      <div className="bg-gradient-to-r from-gray-800 to-gray-900 border-b border-gray-700 px-10 py-8">
        <div className="flex items-center gap-6">
          <button onClick={handleBack} className="text-gray-400 hover:text-white text-sm transition-colors mr-2">
            ← 목록
          </button>
          <PlayerAvatar position={player.position} />
          <div>
            <div className="flex items-center gap-3 mb-1">
              <h1 className="text-white text-4xl font-black">{player.name}</h1>
              <span className="bg-orange-500 text-white text-xs font-bold px-2 py-1 rounded">{player.position}</span>
            </div>
            <p className="text-gray-400 text-sm">{player.team}</p>
            {availableSeasons.length > 1 && (
              <div className="flex gap-2 mt-3">
                {availableSeasons.map((s) => (
                  <button key={s} onClick={() => handleSeasonChange(s)}
                    className={`px-3 py-1 rounded-lg text-xs font-bold transition-colors ${
                      selectedSeason === s ? 'bg-orange-500 text-white' : 'bg-gray-700 text-gray-400 hover:text-white'
                    }`}
                  >
                    {s}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* 스탯 바 */}
          <div className="ml-auto flex gap-6">
            {!isPitcher ? (
              <>
                {[
                  { label: 'AVG',  value: Number(rawData?.avg  ?? 0).toFixed(3) },
                  { label: 'OBP',  value: Number(rawData?.obp  ?? 0).toFixed(3) },
                  { label: 'SLG',  value: Number(rawData?.slg  ?? 0).toFixed(3) },
                  { label: 'OPS',  value: Number(rawData?.ops  ?? 0).toFixed(3) },
                  { label: 'wOBA', value: Number(rawData?.woba ?? 0).toFixed(3) },
                ].map((s) => (
                  <div key={s.label} className="text-center">
                    <p className="text-orange-400 text-xl font-black">{s.value}</p>
                    <p className="text-gray-400 text-xs mt-1">{s.label}</p>
                  </div>
                ))}
                {(rawData as any)?.wrc_plus != null && (
                  <div className="text-center border-l border-gray-700 pl-6">
                    <p className={`text-xl font-black ${
                      Number((rawData as any).wrc_plus) >= 130 ? 'text-orange-400' :
                      Number((rawData as any).wrc_plus) >= 100 ? 'text-green-400' : 'text-gray-400'
                    }`}>
                      {Number((rawData as any).wrc_plus)}
                    </p>
                    <p className="text-gray-400 text-xs mt-1">wRC+</p>
                  </div>
                )}
              </>
            ) : (
              <>
                {[
                  { label: 'ERA',  value: Number((rawData as any)?.era  ?? 0).toFixed(2) },
                  { label: 'W-L',  value: `${(rawData as any)?.w ?? 0}-${(rawData as any)?.l ?? 0}` },
                  { label: 'IP',   value: (rawData as any)?.ip ?? '0' },
                  { label: 'SO',   value: String((rawData as any)?.pitcher_so ?? 0) },
                  { label: 'WHIP', value: Number((rawData as any)?.whip ?? 0).toFixed(2) },
                ].map((s) => (
                  <div key={s.label} className="text-center">
                    <p className="text-orange-400 text-xl font-black">{s.value}</p>
                    <p className="text-gray-400 text-xs mt-1">{s.label}</p>
                  </div>
                ))}
              </>
            )}
          </div>
        </div>
      </div>

      <div className="px-10 py-8">
        <div className="flex gap-6 mb-6">
          <div className="bg-gray-800 rounded-xl p-6 w-96">
            <p className="text-gray-400 text-xs mb-4 uppercase tracking-widest">
              주요 지표
              {selectedSeason && <span className="ml-2 text-orange-400">{selectedSeason} 시즌</span>}
            </p>
            {player.stats.map((s) => (
              <PercentileBar key={s.label} label={s.label} value={s.value} percentile={s.percentile} unit={s.unit} />
            ))}
          </div>
          <div className="bg-gray-800 rounded-xl p-6 w-80">
            <p className="text-gray-400 text-xs mb-2 uppercase tracking-widest text-center">능력치 레이더</p>
            <PlayerRadarChart data={player.radar} />
          </div>
        </div>

        <div className="max-w-xl">
          <InsightBox name={player.name} stats={player.stats} />
        </div>

        {/* 머니볼 엔진 카드 */}
        {moneyball && (
          <div className="bg-gradient-to-br from-gray-800 to-gray-900 border border-orange-500/20 rounded-xl p-6 mt-6 max-w-xl">
            <p className="text-orange-400 text-xs mb-4 uppercase tracking-widest font-bold">⚾ 머니볼 엔진 분석</p>
            <div className="grid grid-cols-3 gap-3 mb-5">
              <div className="bg-gray-900 rounded-lg p-3 text-center">
                <p className="text-gray-500 text-xs mb-1">선수 유형</p>
                <p className="text-white text-sm font-black">{moneyball.cluster_type}</p>
              </div>
              <div className="bg-gray-900 rounded-lg p-3 text-center">
                <p className="text-gray-500 text-xs mb-1">UV Score</p>
                <p className={`text-sm font-black ${
                  moneyball.uv_score >= 20  ? 'text-green-400' :
                  moneyball.uv_score >= 5   ? 'text-blue-400'  :
                  moneyball.uv_score >= -5  ? 'text-gray-300'  :
                  moneyball.uv_score >= -20 ? 'text-yellow-400': 'text-red-400'
                }`}>
                  {moneyball.uv_score > 0 ? '+' : ''}{moneyball.uv_score}
                </p>
              </div>
              <div className="bg-gray-900 rounded-lg p-3 text-center">
                <p className="text-gray-500 text-xs mb-1">평가</p>
                <p className={`text-sm font-black ${
                  moneyball.uv_label === '매우 저평가' ? 'text-green-400' :
                  moneyball.uv_label === '저평가'     ? 'text-blue-400'  :
                  moneyball.uv_label === '적정 평가'  ? 'text-gray-300'  :
                  moneyball.uv_label === '고평가'     ? 'text-yellow-400': 'text-red-400'
                }`}>
                  {moneyball.uv_label}
                </p>
              </div>
            </div>
            <p className="text-gray-400 text-xs mb-3 leading-relaxed">{moneyball.cluster_desc}</p>
            <p className="text-gray-500 text-xs mb-5 leading-relaxed">
              wOBA 백분위 <span className="text-orange-400 font-bold">{moneyball.woba_pct}%</span> — PA 백분위 <span className="text-blue-400 font-bold">{moneyball.pa_pct}%</span> = UV Score <span className="font-bold text-white">{moneyball.uv_score}</span>
            </p>

            {/* 리그 유형 분포 도넛 차트 */}
            {mbDist.length > 0 && (
              <div className="mb-5">
                <p className="text-gray-500 text-xs mb-3">리그 전체 유형 분포</p>
                <div className="flex items-center gap-4">
                  <PieChart width={120} height={120}>
                    <Pie data={mbDist} cx={55} cy={55} innerRadius={35} outerRadius={55} dataKey="count" nameKey="type">
                      {mbDist.map((entry, index) => (
                        <Cell
                          key={entry.type}
                          fill={MB_COLORS[index % MB_COLORS.length]}
                          opacity={entry.type === moneyball.cluster_type ? 1 : 0.4}
                          stroke={entry.type === moneyball.cluster_type ? '#fff' : 'none'}
                          strokeWidth={entry.type === moneyball.cluster_type ? 2 : 0}
                        />
                      ))}
                    </Pie>
                  </PieChart>
                  <div className="flex flex-col gap-1.5">
                    {mbDist.map((entry, index) => (
                      <div key={entry.type} className={`flex items-center gap-2 text-xs ${entry.type === moneyball.cluster_type ? 'text-white font-bold' : 'text-gray-500'}`}>
                        <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: MB_COLORS[index % MB_COLORS.length], opacity: entry.type === moneyball.cluster_type ? 1 : 0.4 }} />
                        {entry.type} {entry.pct}%
                        {entry.type === moneyball.cluster_type && <span className="text-orange-400">← 현재</span>}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* 같은 유형 선수 */}
            {moneyball.same_cluster_players?.length > 0 && (
              <div>
                <p className="text-gray-500 text-xs mb-2">같은 유형 선수</p>
                <div className="flex gap-2 flex-wrap">
                  {moneyball.same_cluster_players.map((name: string) => (
                    <span key={name} className="bg-gray-700 text-gray-300 text-xs px-2 py-1 rounded-lg">{name}</span>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* 연도별 스탯 차트 */}
        {seasons && seasons.seasons.length >= 2 && (
          <div className="bg-gray-800 rounded-xl p-6 mt-6 max-w-3xl">
            <p className="text-gray-400 text-xs mb-6 uppercase tracking-widest">연도별 성적 추이</p>
            {seasons.type === 'hitter' ? (
              <>
                <div className="mb-8">
                  <p className="text-gray-500 text-xs mb-3">wOBA / OPS</p>
                  <ResponsiveContainer width="100%" height={200}>
                    <LineChart data={seasons.seasons}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                      <XAxis dataKey="season_year" stroke="#9ca3af" tick={{ fontSize: 12 }} />
                      <YAxis stroke="#9ca3af" tick={{ fontSize: 12 }} domain={[0, 1.2]} />
                      <Tooltip contentStyle={{ backgroundColor: '#1f2937', border: '1px solid #374151', borderRadius: '8px' }} labelStyle={{ color: '#f97316' }} itemStyle={{ color: '#d1d5db' }} />
                      <Legend wrapperStyle={{ color: '#9ca3af', fontSize: '12px' }} />
                      <Line type="monotone" dataKey="woba" stroke="#f97316" strokeWidth={2} dot={{ fill: '#f97316', r: 4 }} name="wOBA" />
                      <Line type="monotone" dataKey="ops"  stroke="#60a5fa" strokeWidth={2} dot={{ fill: '#60a5fa', r: 4 }} name="OPS" />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
                <div className="mb-8">
                  <p className="text-gray-500 text-xs mb-3">홈런 / 타율</p>
                  <ResponsiveContainer width="100%" height={200}>
                    <BarChart data={seasons.seasons}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                      <XAxis dataKey="season_year" stroke="#9ca3af" tick={{ fontSize: 12 }} />
                      <YAxis yAxisId="left" stroke="#9ca3af" tick={{ fontSize: 12 }} />
                      <YAxis yAxisId="right" orientation="right" stroke="#9ca3af" tick={{ fontSize: 12 }} domain={[0, 0.5]} />
                      <Tooltip contentStyle={{ backgroundColor: '#1f2937', border: '1px solid #374151', borderRadius: '8px' }} labelStyle={{ color: '#f97316' }} itemStyle={{ color: '#d1d5db' }} />
                      <Legend wrapperStyle={{ color: '#9ca3af', fontSize: '12px' }} />
                      <Bar yAxisId="left"  dataKey="hr"  fill="#f97316" name="홈런" radius={[4,4,0,0]} />
                      <Bar yAxisId="right" dataKey="avg" fill="#60a5fa" name="타율" radius={[4,4,0,0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
                <div>
                  <p className="text-gray-500 text-xs mb-3">BB% / K%</p>
                  <ResponsiveContainer width="100%" height={200}>
                    <LineChart data={seasons.seasons}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                      <XAxis dataKey="season_year" stroke="#9ca3af" tick={{ fontSize: 12 }} />
                      <YAxis stroke="#9ca3af" tick={{ fontSize: 12 }} />
                      <Tooltip contentStyle={{ backgroundColor: '#1f2937', border: '1px solid #374151', borderRadius: '8px' }} labelStyle={{ color: '#f97316' }} itemStyle={{ color: '#d1d5db' }} />
                      <Legend wrapperStyle={{ color: '#9ca3af', fontSize: '12px' }} />
                      <Line type="monotone" dataKey="bb_rate" stroke="#4ade80" strokeWidth={2} dot={{ fill: '#4ade80', r: 4 }} name="BB%" />
                      <Line type="monotone" dataKey="k_rate"  stroke="#f87171" strokeWidth={2} dot={{ fill: '#f87171', r: 4 }} name="K%" />
                    </LineChart>
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
                      <XAxis dataKey="season_year" stroke="#9ca3af" tick={{ fontSize: 12 }} />
                      <YAxis stroke="#9ca3af" tick={{ fontSize: 12 }} />
                      <Tooltip contentStyle={{ backgroundColor: '#1f2937', border: '1px solid #374151', borderRadius: '8px' }} labelStyle={{ color: '#f97316' }} itemStyle={{ color: '#d1d5db' }} />
                      <Legend wrapperStyle={{ color: '#9ca3af', fontSize: '12px' }} />
                      <Line type="monotone" dataKey="era"  stroke="#f97316" strokeWidth={2} dot={{ fill: '#f97316', r: 4 }} name="ERA" />
                      <Line type="monotone" dataKey="whip" stroke="#60a5fa" strokeWidth={2} dot={{ fill: '#60a5fa', r: 4 }} name="WHIP" />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
                <div>
                  <p className="text-gray-500 text-xs mb-3">승 / 탈삼진</p>
                  <ResponsiveContainer width="100%" height={200}>
                    <BarChart data={seasons.seasons}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                      <XAxis dataKey="season_year" stroke="#9ca3af" tick={{ fontSize: 12 }} />
                      <YAxis stroke="#9ca3af" tick={{ fontSize: 12 }} />
                      <Tooltip contentStyle={{ backgroundColor: '#1f2937', border: '1px solid #374151', borderRadius: '8px' }} labelStyle={{ color: '#f97316' }} itemStyle={{ color: '#d1d5db' }} />
                      <Legend wrapperStyle={{ color: '#9ca3af', fontSize: '12px' }} />
                      <Bar dataKey="w"          fill="#f97316" name="승" radius={[4,4,0,0]} />
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