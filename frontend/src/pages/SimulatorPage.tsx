import { useState } from 'react';
import { useLocation } from 'react-router-dom';
import Scoreboard from '../components/simulator/Scoreboard';
import GameLogView from '../components/simulator/GameLog';
import StatsModal from '../components/simulator/StatsModal';
import { simulateGame, simulateMulti } from '../api/simulatorApi';
import { saveRecord } from '../api/recordApi';
import type { GameLog, MultiSimulateResponse } from '../api/simulatorApi';

const DEFAULT_LINEUP_A = [
  { name: "최지훈",   ab: 400, hits: 120, double: 20, triple: 2, hr: 5,  bb: 40, hbp: 3 },
  { name: "최정",     ab: 380, hits: 100, double: 18, triple: 1, hr: 25, bb: 55, hbp: 5 },
  { name: "한유섬",   ab: 360, hits: 105, double: 22, triple: 0, hr: 18, bb: 35, hbp: 2 },
  { name: "기예르모", ab: 350, hits: 98,  double: 19, triple: 1, hr: 20, bb: 30, hbp: 1 },
  { name: "박성한",   ab: 370, hits: 108, double: 21, triple: 2, hr: 8,  bb: 38, hbp: 4 },
  { name: "오태곤",   ab: 300, hits: 85,  double: 15, triple: 1, hr: 10, bb: 28, hbp: 2 },
  { name: "김민식",   ab: 280, hits: 75,  double: 12, triple: 0, hr: 7,  bb: 22, hbp: 1 },
  { name: "이재원",   ab: 260, hits: 68,  double: 10, triple: 0, hr: 5,  bb: 18, hbp: 1 },
  { name: "고효준",   ab: 240, hits: 60,  double: 8,  triple: 0, hr: 3,  bb: 15, hbp: 0 },
];

const DEFAULT_LINEUP_B = [
  { name: "장두성",   ab: 48,  hits: 16, double: 1, triple: 1, hr: 0, bb: 1,  hbp: 1 },
  { name: "윤동희",   ab: 75,  hits: 14, double: 4, triple: 0, hr: 3, bb: 6,  hbp: 1 },
  { name: "레이예스", ab: 113, hits: 39, double: 8, triple: 0, hr: 5, bb: 11, hbp: 2 },
  { name: "유강남",   ab: 62,  hits: 16, double: 4, triple: 0, hr: 2, bb: 1,  hbp: 0 },
  { name: "김민성",   ab: 14,  hits: 1,  double: 0, triple: 0, hr: 1, bb: 3,  hbp: 0 },
  { name: "박승욱",   ab: 32,  hits: 11, double: 2, triple: 0, hr: 1, bb: 1,  hbp: 0 },
  { name: "전민재",   ab: 77,  hits: 18, double: 3, triple: 0, hr: 0, bb: 7,  hbp: 0 },
  { name: "손성빈",   ab: 48,  hits: 10, double: 2, triple: 0, hr: 1, bb: 6,  hbp: 0 },
  { name: "한태양",   ab: 74,  hits: 18, double: 3, triple: 0, hr: 0, bb: 7,  hbp: 1 },
];

export default function SimulatorPage() {
  const location = useLocation();

  const fromMyTeam = location.state as {
    lineup: typeof DEFAULT_LINEUP_A;
    teamName: string;
  } | null;

  const teamALineup = fromMyTeam?.lineup ?? DEFAULT_LINEUP_A;
  const teamAName   = fromMyTeam?.teamName ?? 'SSG 랜더스';
  const teamBName   = '롯데 자이언츠';

  const [started, setStarted]       = useState(false);
  const [loading, setLoading]       = useState(false);
  const [showStats, setShowStats]   = useState(false);
  const [gameLog, setGameLog]       = useState<GameLog | null>(null);
  const [multiStats, setMultiStats] = useState<MultiSimulateResponse | null>(null);
  const [error, setError]           = useState<string | null>(null);

  async function handleStart() {
    setLoading(true);
    setError(null);
    try {
      const res = await simulateGame({
        team_a_name: teamAName,
        team_a_lineup: teamALineup,
        team_b_name: teamBName,
        team_b_lineup: DEFAULT_LINEUP_B,
      });
      setGameLog(res.game_log);
      setStarted(true);

      // 경기 결과 자동 저장
      const scoreA = res.game_log.final_score[0];
      const scoreB = res.game_log.final_score[1];
      const result = scoreA > scoreB ? '승' : scoreA < scoreB ? '패' : '무';
      await saveRecord({
        team_name:     teamAName,
        opponent_name: teamBName,
        result,
        my_score:  scoreA,
        opp_score: scoreB,
      });

    } catch {
      setError('시뮬레이션 중 오류가 발생했습니다.');
    } finally {
      setLoading(false);
    }
  }

  async function handleMultiStats() {
    setLoading(true);
    try {
      const res = await simulateMulti({
        team_a_name: teamAName,
        team_a_lineup: teamALineup,
        team_b_name: teamBName,
        team_b_lineup: DEFAULT_LINEUP_B,
        n_games: 1000,
      });
      setMultiStats(res);
      setShowStats(true);
    } catch {
      setError('통계 계산 중 오류가 발생했습니다.');
    } finally {
      setLoading(false);
    }
  }

  function handleReset() {
    setStarted(false);
    setGameLog(null);
    setMultiStats(null);
    setError(null);
  }

  const scoreboard = gameLog ? {
    away: {
      team: teamAName,
      innings: gameLog.innings.filter((i) => i.half === '초').map((i) => i.runs),
      total: gameLog.final_score[0],
    },
    home: {
      team: teamBName,
      innings: gameLog.innings.filter((i) => i.half === '말').map((i) => i.runs),
      total: gameLog.final_score[1],
    },
  } : null;

  return (
    <div className="min-h-screen bg-gray-900">

      {/* 헤더 */}
      <div className="bg-gradient-to-r from-gray-800 to-gray-900 border-b border-gray-700 px-10 py-8">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-white text-3xl font-black">경기 시뮬레이터</h1>
            <p className="text-gray-400 text-sm mt-1">마르코프 체인 기반 경기 예측</p>
          </div>
          <div className="flex items-center gap-6">
            <div className="text-right">
              <p className="text-white font-bold">{teamAName}</p>
              <p className="text-gray-400 text-xs">원정</p>
            </div>
            <div className="bg-gray-700 rounded-full px-4 py-2">
              <span className="text-orange-400 font-black text-xl">
                {gameLog ? gameLog.final_score[0] : '-'}
              </span>
              <span className="text-gray-500 mx-2">:</span>
              <span className="text-orange-400 font-black text-xl">
                {gameLog ? gameLog.final_score[1] : '-'}
              </span>
            </div>
            <div className="text-left">
              <p className="text-white font-bold">{teamBName}</p>
              <p className="text-gray-400 text-xs">홈</p>
            </div>
          </div>
        </div>

        {/* 나만의 팀 라인업 표시 */}
        {fromMyTeam && (
          <div className="mt-4 flex flex-wrap gap-2">
            {teamALineup.map((p, i) => (
              <span key={i} className="text-xs bg-gray-700 text-gray-300 px-3 py-1 rounded-full">
                {i + 1}. {p.name}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* 본문 */}
      <div className="px-10 py-8 space-y-6">

        {error && (
          <div className="bg-red-900/30 border border-red-700 rounded-xl px-6 py-4 text-red-400">
            {error}
          </div>
        )}

        {!started && !loading && (
          <div className="flex justify-center py-10">
            <button
              onClick={handleStart}
              className="bg-orange-500 hover:bg-orange-600 text-white font-black text-lg px-12 py-4 rounded-xl transition-colors"
            >
              ▶ 경기 시작
            </button>
          </div>
        )}

        {loading && (
          <div className="flex justify-center py-10">
            <p className="text-gray-400 text-lg animate-pulse">⚾ 시뮬레이션 중...</p>
          </div>
        )}

        {started && !loading && gameLog && scoreboard && (
          <>
            <Scoreboard away={scoreboard.away} home={scoreboard.home} />
            <GameLogView gameLog={gameLog.innings} />
            <div className="flex gap-4">
              <button
                onClick={handleReset}
                className="bg-gray-700 hover:bg-gray-600 text-white font-bold px-8 py-3 rounded-xl transition-colors"
              >
                🔄 다시 시뮬
              </button>
              <button
                onClick={handleMultiStats}
                disabled={loading}
                className="bg-blue-600 hover:bg-blue-700 text-white font-bold px-8 py-3 rounded-xl transition-colors disabled:opacity-50"
              >
                📊 100경기 통계
              </button>
            </div>
          </>
        )}
      </div>

      {showStats && multiStats && (
        <StatsModal onClose={() => setShowStats(false)} stats={multiStats} />
      )}
    </div>
  );
}