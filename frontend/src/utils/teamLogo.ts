const TEAM_CODE_MAP: Record<string, string> = {
  'LG': 'LG',
  '한화': 'HH',
  'SSG': 'SSG',
  '삼성': 'SS',
  'NC': 'NC',
  'KT': 'KT',
  '롯데': 'LT',
  'KIA': 'KIA',
  '두산': 'OB',
  '키움': 'WO',
};

export function getTeamLogo(teamName: string): string {
  const code = TEAM_CODE_MAP[teamName];
  return code ? `/logos/${code}.png` : '';
}