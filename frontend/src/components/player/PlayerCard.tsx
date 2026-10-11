import type { Player } from '../../data/mockPlayers';
import PlayerPhoto from '../common/PlayerPhoto';

interface Props {
  player: Player;
  onClick: (player: Player) => void;
}

export default function PlayerCard({ player, onClick }: Props) {
  return (
    <div
      onClick={() => onClick(player)}
      className="bg-gray-800 hover:bg-gray-700 rounded-xl px-5 py-4 cursor-pointer transition-colors border border-transparent hover:border-orange-400"
    >
      <div className="flex items-center gap-4">
        <PlayerPhoto playerId={player.id} fallback={player.position} size={48} fallbackClass="bg-orange-500" />

        <div>
          <p className="text-white font-bold">{player.name}</p>
          <p className="text-gray-400 text-xs mt-1">{player.team}</p>
        </div>

        {player.stats.length > 0 && (
          <div className="ml-auto flex gap-4">
            {player.stats.slice(0, 2).map((s) => (
              <div key={s.label} className="text-right">
                <p className="text-orange-400 text-sm font-bold">{s.value}</p>
                <p className="text-gray-500 text-xs">{s.label}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}