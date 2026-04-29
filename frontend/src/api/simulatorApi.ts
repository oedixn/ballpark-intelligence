import axios from 'axios';

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

const api = axios.create({ baseURL: BASE_URL });

// 단일 경기 시뮬레이션
export const simulateGame = async (awayLineup: number[], homeLineup: number[]) => {
  const res = await api.post('/api/simulate/game', {
    away_lineup: awayLineup,
    home_lineup: homeLineup,
  });
  return res.data;
};

// 다경기 시뮬레이션 (n회 반복)
export const simulateMulti = async (
  awayLineup: number[],
  homeLineup: number[],
  n: number = 1000
) => {
  const res = await api.post('/api/simulate/multi', {
    away_lineup: awayLineup,
    home_lineup: homeLineup,
    n,
  });
  return res.data;
};