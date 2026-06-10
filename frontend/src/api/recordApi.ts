import axios from 'axios';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL,
});

export interface GameRecord {
  id: number;
  team_name: string;
  opponent_name: string;
  result: string;
  my_score: number;
  opp_score: number;
  played_at: string;
}

export interface GameRecordCreate {
  team_name: string;
  opponent_name: string;
  result: string;
  my_score: number;
  opp_score: number;
}

export async function saveRecord(data: GameRecordCreate): Promise<{ id: number }> {
  const res = await api.post('/api/records', data);
  return res.data;
}

export async function fetchRecords(teamName?: string): Promise<GameRecord[]> {
  const params = teamName ? { team_name: teamName } : {};
  const res = await api.get<{ records: GameRecord[] }>('/api/records', { params });
  return res.data.records;
}

export async function deleteRecord(id: number): Promise<void> {
  await api.delete(`/api/records/${id}`);
}