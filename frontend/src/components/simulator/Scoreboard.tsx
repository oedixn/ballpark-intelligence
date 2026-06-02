interface TeamScore {
  team: string;
  innings: number[];
  total: number;
}

interface Props {
  away: TeamScore;
  home: TeamScore;
}

export default function Scoreboard({ away, home }: Props) {
  const inningCount  = Math.max(away.innings.length, home.innings.length, 9);
  const inningLabels = Array.from({ length: inningCount }, (_, i) => i + 1);

  return (
    <div style={{
      background: '#0a0a0a',
      border: '4px solid #f97316',
      boxShadow: '0 0 0 2px #000, 0 0 0 4px #f97316, 8px 8px 0 #7c2d12',
      borderRadius: '4px',
      padding: '20px',
      fontFamily: "'Press Start 2P', cursive",
    }}>
      <p style={{ color: '#f97316', fontSize: '8px', marginBottom: '16px', letterSpacing: '2px' }}>
        ★ SCORE BOARD ★
      </p>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '10px' }}>
          <thead>
            <tr>
              <th style={{ textAlign: 'left', padding: '6px 12px 6px 0', color: '#f97316', width: '120px', fontSize: '8px' }}>TEAM</th>
              {inningLabels.map((i) => (
                <th key={i} style={{ textAlign: 'center', padding: '6px 4px', color: '#6b7280', width: '28px', fontSize: '8px' }}>{i}</th>
              ))}
              <th style={{ textAlign: 'center', padding: '6px 8px', color: '#f97316', fontSize: '10px' }}>R</th>
            </tr>
          </thead>
          <tbody>
            {[away, home].map((team, ti) => (
              <tr key={team.team} style={{ borderTop: '2px solid #1f2937' }}>
                <td style={{ padding: '10px 12px 10px 0', color: '#fff', fontSize: '8px', whiteSpace: 'nowrap', overflow: 'hidden', maxWidth: '120px', textOverflow: 'ellipsis' }}>
                  {team.team}
                </td>
                {inningLabels.map((_, i) => {
                  const score = team.innings[i];
                  return (
                    <td key={i} style={{ textAlign: 'center', padding: '10px 4px', width: '28px' }}>
                      {score === undefined ? (
                        <span style={{ color: '#374151', fontSize: '8px' }}>-</span>
                      ) : score === 0 ? (
                        <span style={{ color: '#4b5563', fontSize: '8px' }}>0</span>
                      ) : (
                        <span style={{ color: '#fbbf24', fontSize: '10px', textShadow: '0 0 8px #f97316' }}>{score}</span>
                      )}
                    </td>
                  );
                })}
                <td style={{ textAlign: 'center', padding: '10px 8px' }}>
                  <span style={{
                    color: '#f97316',
                    fontSize: '16px',
                    fontWeight: 900,
                    textShadow: '2px 2px 0 #7c2d12',
                  }}>
                    {team.total}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}