import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import type { Player } from '../../data/mockPlayers';

interface Props {
  player: Player;
  order: number;
}

export default function LineupCard({ player, order }: Props) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: player.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.4 : 1,
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...attributes}
      {...listeners}
      className="flex items-center gap-4 bg-gray-700 hover:bg-gray-600 rounded-xl px-5 py-3 cursor-grab active:cursor-grabbing transition-colors"
    >
      {/* 타순 번호 */}
      <span className="text-orange-400 font-black text-lg w-6 shrink-0">{order}</span>

      {/* 포지션 뱃지 */}
      <span className="bg-gray-600 text-gray-300 text-xs font-bold px-2 py-1 rounded w-10 text-center shrink-0">
        {player.position}
      </span>

      {/* 선수명 */}
      <span className="text-white font-semibold">{player.name}</span>

      {/* 드래그 핸들 아이콘 */}
      <span className="ml-auto text-gray-500 text-lg">⠿</span>
    </div>
  );
}