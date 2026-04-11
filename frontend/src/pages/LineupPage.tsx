import { useState } from 'react';
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
} from '@dnd-kit/core';
import {
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
  arrayMove,
} from '@dnd-kit/sortable';
import LineupCard from '../components/lineup/LineupCard';
import { mockLineup } from '../data/mockPlayers';
import type { Player } from '../data/mockPlayers';

export default function LineupPage() {
  const [lineup, setLineup] = useState<Player[]>(mockLineup);

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  const handleDragEnd = (event: any) => {
    const { active, over } = event;
    if (active.id !== over?.id) {
      setLineup((items) => {
        const oldIndex = items.findIndex((i) => i.id === active.id);
        const newIndex = items.findIndex((i) => i.id === over.id);
        return arrayMove(items, oldIndex, newIndex);
      });
    }
  };

  return (
    <div className="min-h-screen bg-gray-900">

      {/* 헤더 */}
      <div className="bg-gradient-to-r from-gray-800 to-gray-900 border-b border-gray-700 px-10 py-8">
        <h1 className="text-white text-3xl font-black">타순 배치</h1>
        <p className="text-gray-400 text-sm mt-1">드래그하여 타순을 변경하세요</p>
      </div>

      {/* 본문 */}
      <div className="px-10 py-8 flex gap-8">

        {/* 타순 리스트 */}
        <div className="w-96">
          <p className="text-gray-400 text-xs mb-4 uppercase tracking-widest">타순</p>
          <DndContext
            sensors={sensors}
            collisionDetection={closestCenter}
            onDragEnd={handleDragEnd}
          >
            <SortableContext
              items={lineup.map((p) => p.id)}
              strategy={verticalListSortingStrategy}
            >
              <div className="space-y-2">
                {lineup.map((player, index) => (
                  <LineupCard
                    key={player.id}
                    player={player}
                    order={index + 1}
                  />
                ))}
              </div>
            </SortableContext>
          </DndContext>
        </div>

        {/* 우측 요약 */}
        <div className="flex-1">
          <p className="text-gray-400 text-xs mb-4 uppercase tracking-widest">현재 타순 요약</p>
          <div className="bg-gray-800 rounded-xl p-6">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-gray-400 border-b border-gray-700">
                  <th className="text-left py-2 w-8">순번</th>
                  <th className="text-left py-2 w-16">포지션</th>
                  <th className="text-left py-2">선수명</th>
                </tr>
              </thead>
              <tbody>
                {lineup.map((player, index) => (
                  <tr key={player.id} className="border-b border-gray-700">
                    <td className="py-3 text-orange-400 font-bold">{index + 1}</td>
                    <td className="py-3 text-gray-400 text-xs">{player.position}</td>
                    <td className="py-3 text-white">{player.name}</td>
                  </tr>
                ))}
              </tbody>
            </table>

            {/* 시뮬레이션 버튼 */}
            <button className="mt-6 w-full bg-orange-500 hover:bg-orange-600 text-white font-black py-3 rounded-xl transition-colors">
              ▶ 이 타순으로 시뮬레이션
            </button>
          </div>
        </div>

      </div>
    </div>
  );
}