import axios from 'axios';

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

const api = axios.create({ baseURL: BASE_URL });

// 선수 전체 목록
export const getPlayers = async () => {
  const res = await api.get('/api/players');
  return res.data;
};

// 선수 단건 조회
export const getPlayerById = async (playerId: number) => {
  const res = await api.get(`/api/players/${playerId}`);
  return res.data;
};

// 선수 이벤트 확률 조회
export const getPlayerProbs = async (playerId: number) => {
  const res = await api.get(`/api/players/${playerId}/probs`);
  return res.data;
};