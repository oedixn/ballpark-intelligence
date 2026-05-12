import axios from 'axios';

const api = axios.create({
  baseURL: 'http://localhost:8000',
});

export interface PlayerDB {
  player_id: string;
  player_name: string;
  team_name: string;
  season_year: number;
  avg: number;
  pa: number;
  ab: number;
  h: number;
  double_hit: number;
  triple_hit: number;
  hr: number;
  bb: number;
  hbp: number;
  so: number;
  slg: number;
  obp: number;
  ops: number;
  isop: number;
  rbi: number;
  babip: number | null;
  bb_rate: number | null;
  k_rate: number | null;
  iso: number | null;
  spd: number | null;
  war: number | null;
  woba: number | null;
  position: string | null;
}

export async function fetchPlayers(search?: string): Promise<PlayerDB[]> {
  const params = search ? { search } : {};
  const res = await api.get<{ players: PlayerDB[] }>('/api/players', { params });
  return res.data.players;
}

export async function fetchPlayerById(playerId: string): Promise<PlayerDB> {
  const res = await api.get<PlayerDB>(`/api/players/${playerId}`);
  return res.data;
}

export async function fetchTeamLineup(teamName: string): Promise<{
  name: string; ab: number; hits: number; double: number;
  triple: number; hr: number; bb: number; hbp: number;
}[]> {
  const res = await api.get(`/api/teams/${encodeURIComponent(teamName)}/lineup`);
  return res.data.lineup.map((p: any) => ({
    name:   p.player_name,
    ab:     p.ab     ?? 300,
    hits:   p.hits   ?? 80,
    double: p.double ?? 15,
    triple: p.triple ?? 2,
    hr:     p.hr     ?? 5,
    bb:     p.bb     ?? 30,
    hbp:    p.hbp    ?? 3,
  }));
}