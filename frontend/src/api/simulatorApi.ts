import axios from 'axios';

const api = axios.create({ baseURL: import.meta.env.VITE_API_URL });

export interface PlayerRecord { name:string; ab:number; hits:number; double:number; triple:number; hr:number; bb:number; hbp:number; }
export interface PlateAppearance { inning:number; half:string; batter_order:number; batter_name:string; event:string; runs_scored:number; outs_after:number; bases_after:string; }
export interface InningLog { inning:number; half:string; team_name:string; runs:number; plate_appearances:PlateAppearance[]; }
export interface GameLog { team_a:string; team_b:string; final_score:[number,number]; innings:InningLog[]; }
export interface PitcherInfo { player_name:string; era:number; gs:number; g:number; w:number; l:number; whip:number; so:number; ip:string; }

export interface SimulateRequest {
  team_a_name:string; team_a_lineup:PlayerRecord[];
  team_b_name:string; team_b_lineup:PlayerRecord[];
  innings?:number;
  pitcher_a?:string;
  pitcher_b?:string;
}

export interface SimulateResponse { team_a_name:string; team_b_name:string; game_log:GameLog; }

export interface MultiSimulateResponse {
  team_a:{ name:string; markov_expected:number; mean_runs:number; variance:number; prob_0_runs:number; prob_5_or_more:number; };
  team_b:{ name:string; markov_expected:number; mean_runs:number; variance:number; prob_0_runs:number; prob_5_or_more:number; };
  n_games:number;
}

export async function simulateGame(req:SimulateRequest): Promise<SimulateResponse> {
  return (await api.post<SimulateResponse>('/api/simulate/game', req)).data;
}

export async function simulateMulti(req:SimulateRequest & { n_games?:number }): Promise<MultiSimulateResponse> {
  return (await api.post<MultiSimulateResponse>('/api/simulate/multi', req)).data;
}

export async function fetchTeamPitchers(teamName:string): Promise<PitcherInfo[]> {
  return (await api.get<{ pitchers:PitcherInfo[] }>(`/api/pitchers/${encodeURIComponent(teamName)}`)).data.pitchers;
}