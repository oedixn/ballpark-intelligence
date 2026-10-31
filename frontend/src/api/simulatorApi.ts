import axios from 'axios';

const api = axios.create({ baseURL: import.meta.env.VITE_API_URL });

export interface PlayerRecord { name:string; ab:number; hits:number; double:number; triple:number; hr:number; bb:number; hbp:number; player_id?:string; }
export interface PlateAppearance { inning:number; half:string; batter_order:number; batter_name:string; event:string; runs_scored:number; outs_after:number; bases_after:string; pitcher_name?:string|null; pitcher_id?:string|null; pitching_change_reason?:string|null; }
export interface InningLog { inning:number; half:string; team_name:string; runs:number; plate_appearances:PlateAppearance[]; }
export interface GameLog { team_a:string; team_b:string; final_score:[number,number]; innings:InningLog[]; bullpen_enabled?:boolean; }
export interface PitcherInfo { player_id:string; player_name:string; era:number; gs:number; g:number; w:number; l:number; whip:number; so:number; ip:string; }

export interface SimulateRequest {
  team_a_name:string; team_a_lineup:PlayerRecord[];
  team_b_name:string; team_b_lineup:PlayerRecord[];
  innings?:number;
  pitcher_a?:string;
  pitcher_b?:string;
  pitcher_a_id?:string;
  pitcher_b_id?:string;
  as_of?:string;
  seed?:number;
  bullpen_enabled?:boolean;
}

export interface BullpenSummary {
  enabled:boolean;
  calibrated:boolean;
  usage?:Record<string,{mean_pitchers:number; mean_starter_batters:number; mean_starter_innings:number}>;
}

export interface SimulationMetadata {
  season:number; as_of:string; last_game_date:string; date_rule:string;
  seed?:number; source:string; data_sha256:string;
}
export interface HistoricalTeam {
  lineup:PlayerRecord[]; batters:PlayerRecord[]; pitchers:PitcherInfo[];
  metadata:SimulationMetadata;
}
export interface SimulateResponse { team_a_name:string; team_b_name:string; game_log:GameLog; metadata?:SimulationMetadata; }

export interface MultiSimulateResponse {
  team_a:{ name:string; markov_expected:number; mean_runs:number; variance:number; prob_0_runs:number; prob_5_or_more:number; };
  team_b:{ name:string; markov_expected:number; mean_runs:number; variance:number; prob_0_runs:number; prob_5_or_more:number; };
  n_games:number;
  bullpen?:BullpenSummary;
  metadata?:SimulationMetadata;
  score_distribution?:{team_a_score:number; team_b_score:number; count:number}[];
  matchup?:{
    team_a_wins:number; team_b_wins:number; draws:number;
    team_a_win_probability:number; team_b_win_probability:number; draw_probability:number;
    team_a_win_rate:number|null; team_b_win_rate:number|null;
  };
}

export async function fetchHistoricalTeam(teamName:string, asOf:string):Promise<HistoricalTeam> {
  return (await api.get<HistoricalTeam>(`/api/simulate/history/${encodeURIComponent(teamName)}`, {params:{as_of:asOf}})).data;
}

export function simulatorErrorMessage(error:unknown):string {
  if (axios.isAxiosError(error) && typeof error.response?.data?.detail === 'string') return error.response.data.detail;
  return '시뮬레이션 데이터를 불러오지 못했습니다. 연결과 선택한 조건을 확인하세요.';
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
