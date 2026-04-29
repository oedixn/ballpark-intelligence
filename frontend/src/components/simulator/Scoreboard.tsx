interface TeamScore {
  team: string;
  scores: number[];
  total: number;
}

interface Props {
  away: TeamScore;
  home: TeamScore;
}

export default function Scoreboard({ away, home }: Props) {
  const innings = Array.from({ length: 9 }, (_, i) => i + 1);

  return (
    <div className="bg-gray-800 rounded-xl p-6">
      <p className="text-gray-400 text-xs mb-4 uppercase tracking-widest">스코어보드</p>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-gray-400">
              <th className="text-left py-2 pr-6 w-32">팀</th>
              {innings.map((i) => (
                <th key={i} className="text-center py-2 w-8">{i}</th>
              ))}
              <th className="text-center py-2 px-4 text-white font-bold">R</th>
            </tr>
          </thead>
          <tbody>
            {[away, home].map((team) => (
              <tr key={team.team} className="border-t border-gray-700">
                <td className="py-3 pr-6 text-white font-semibold text-xs">{team.team}</td>
                {team.scores.map((score, i) => (
                  <td key={i} className="text-center py-3 text-gray-300 w-8">
                    {score === 0
                      ? <span className="text-gray-600">0</span>
                      : <span className="text-orange-400 font-bold">{score}</span>
                    }
                  </td>
                ))}
                <td className="text-center py-3 px-4 text-orange-400 font-black text-lg">
                  {team.total}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}