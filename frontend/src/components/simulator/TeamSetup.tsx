import { useEffect, useMemo, useState } from 'react';
import { DndContext, closestCenter, KeyboardSensor, PointerSensor, useSensor, useSensors } from '@dnd-kit/core';
import type { DragEndEvent } from '@dnd-kit/core';
import { SortableContext, arrayMove, sortableKeyboardCoordinates, useSortable, verticalListSortingStrategy } from '@dnd-kit/sortable';
import type { PitcherInfo } from '../../api/simulatorApi';
import { getTeamLogo } from '../../utils/teamLogo';

export interface Batter { name: string; ab: number; hits: number; double: number; triple: number; hr: number; bb: number; hbp: number; pa?: number; position?: string | null }

interface Props {
  side: 'AWAY' | 'HOME';
  teamName: string; teams: string[]; excludeTeam: string;
  onTeamChange: (name: string) => void;
  pitchers: PitcherInfo[]; pitcherId: string; onPitcherChange: (id: string) => void;
  lineup: Batter[]; onLineupChange: (l: Batter[]) => void;
}

const POSITIONS = ['포수', '1루수', '2루수', '3루수', '유격수', '좌익수', '중견수', '우익수', '지명타자'];

const sel = { background: '#1a1a1a', color: '#f97316', border: '2px solid #374151', padding: '8px 10px', fontSize: '13px', fontFamily: 'inherit', outline: 'none', cursor: 'pointer', width: '100%' } as const;
const mini = { background: '#1a1a1a', color: '#9ca3af', border: '1px solid #374151', fontSize: '11px', padding: '2px 8px', cursor: 'pointer', fontFamily: 'inherit' } as const;
const cap = { color: '#9ca3af', fontSize: '11px', letterSpacing: '1px', marginBottom: '6px' } as const;

function LineupRow({ index, p, pos, dup, onPos, onRemove }: {
  index: number; p: Batter; pos: string; dup: boolean; onPos: (v: string) => void; onRemove: () => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: p.name });
  const stop = { onPointerDown: (e: React.PointerEvent) => e.stopPropagation(), onKeyDown: (e: React.KeyboardEvent) => e.stopPropagation() };
  const options = POSITIONS.includes(pos) ? POSITIONS : [pos, ...POSITIONS];
  return (
    <div ref={setNodeRef} {...attributes} {...listeners}
      style={{
        transform: transform ? `translate3d(${transform.x}px, ${transform.y}px, 0)` : undefined, transition,
        display: 'flex', alignItems: 'center', gap: '8px', padding: '6px 8px', position: 'relative',
        background: isDragging ? '#1f2937' : '#111', border: `1px solid ${isDragging ? '#f97316' : '#1f2937'}`,
        zIndex: isDragging ? 10 : 0, cursor: isDragging ? 'grabbing' : 'grab', touchAction: 'none', userSelect: 'none',
      }}>
      <span style={{ color: '#4b5563', fontSize: '12px' }}>⋮⋮</span>
      <span style={{ color: index < 3 ? '#f97316' : '#6b7280', fontSize: '12px', width: 16 }}>{index + 1}</span>
      <span style={{ color: '#e5e7eb', fontSize: '12px', flex: 1 }}>{p.name}</span>
      <select value={pos} onChange={e => onPos(e.target.value)} {...stop} aria-label={`${p.name} 포지션`}
        style={{ background: '#1f2937', color: dup ? '#fca5a5' : '#d1d5db', border: `1px solid ${dup ? '#ef4444' : '#374151'}`, fontSize: '11px', padding: '3px 4px', fontFamily: 'inherit', outline: 'none', cursor: 'pointer' }}>
        {pos === '-' && <option value="-">포지션</option>}
        {options.filter(o => o !== '-').map(o => <option key={o} value={o}>{o}</option>)}
      </select>
      <button {...stop} onClick={onRemove} aria-label={`${p.name} 제외`} style={{ ...mini, color: '#ef4444' }}>✕</button>
    </div>
  );
}

export default function TeamSetup({ side, teamName, teams, excludeTeam, onTeamChange, pitchers, pitcherId, onPitcherChange, lineup, onLineupChange }: Props) {
  const isKbo = teams.includes(teamName);
  const [batters, setBatters] = useState<Batter[]>([]);

  useEffect(() => {
    if (!isKbo) { setBatters([]); return; }
    let alive = true;
    fetch(`${import.meta.env.VITE_API_URL}/api/teams/${encodeURIComponent(teamName)}/batters`)
      .then(r => r.json()).then(d => alive && setBatters(d.batters ?? [])).catch(() => alive && setBatters([]));
    return () => { alive = false; };
  }, [teamName]);

  const posMap = useMemo(() => new Map(batters.map(b => [b.name, b.position ?? ''] as [string, string])), [batters]);
  const posOf = (p: Batter) => p.position || posMap.get(p.name) || '-';

  const counts = new Map<string, number>();
  lineup.forEach(p => { const k = posOf(p); if (k !== '-') counts.set(k, (counts.get(k) ?? 0) + 1); });
  const dupList = [...counts.entries()].filter(([, n]) => n > 1).map(([k]) => k);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );
  const onDragEnd = ({ active, over }: DragEndEvent) => {
    if (!over || active.id === over.id) return;
    const from = lineup.findIndex(p => p.name === active.id), to = lineup.findIndex(p => p.name === over.id);
    if (from < 0 || to < 0) return;
    onLineupChange(arrayMove(lineup, from, to));
  };
  const setPos = (i: number, v: string) => onLineupChange(lineup.map((p, k) => (k === i ? { ...p, position: v } : p)));

  const used = new Set(lineup.map(p => p.name));
  const pool = batters.filter(b => !used.has(b.name));
  const full = lineup.length >= 9;
  const logo = getTeamLogo(teamName);

  return (
    <div className="retro-box" style={{ padding: '16px', fontFamily: 'inherit' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '14px' }}>
        <span style={{ color: '#6b7280', fontSize: '11px' }}>{side}</span>
        {logo && <img src={logo} alt={teamName} style={{ width: 26, height: 26, objectFit: 'contain' }} />}
        <select value={teamName} onChange={e => onTeamChange(e.target.value)} style={{ ...sel, width: 'auto', flex: 1 }}>
          {!isKbo && <option value={teamName}>{teamName}</option>}
          {teams.map(t => <option key={t} value={t} disabled={t === excludeTeam}>{t}</option>)}
        </select>
      </div>

      <p style={cap}>선발투수</p>
      <select value={pitcherId} onChange={e => onPitcherChange(e.target.value)} style={{ ...sel, marginBottom: '16px' }}>
        <option value="">선택 안함</option>
        {pitchers.map(p => <option key={p.player_id} value={p.player_id}>{p.player_name} (ERA {p.era} / GS {p.gs})</option>)}
      </select>

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
        <p style={{ ...cap, marginBottom: 0 }}>
          타순 <span style={{ color: lineup.length === 9 ? '#f97316' : '#ef4444' }}>{lineup.length}/9</span>
          <span style={{ color: '#6b7280', marginLeft: '8px' }}>드래그로 순서 변경</span>
        </p>
        {isKbo && batters.length > 0 && <button style={mini} onClick={() => onLineupChange(batters.slice(0, 9))}>자동 구성</button>}
      </div>

      <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={onDragEnd}>
        <SortableContext items={lineup.map(p => p.name)} strategy={verticalListSortingStrategy}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '3px', marginBottom: '8px' }}>
            {lineup.map((p, i) => (
              <LineupRow key={p.name} index={i} p={p} pos={posOf(p)} dup={dupList.includes(posOf(p))}
                onPos={v => setPos(i, v)} onRemove={() => onLineupChange(lineup.filter((_, k) => k !== i))} />
            ))}
            {lineup.length === 0 && <p style={{ color: '#6b7280', fontSize: '12px' }}>아래에서 타자를 선택하세요.</p>}
          </div>
        </SortableContext>
      </DndContext>

      {dupList.length > 0 && (
        <p style={{ color: '#fca5a5', fontSize: '11px', marginBottom: '8px' }}>포지션 중복: {dupList.join(', ')} (경기 결과에는 영향 없음)</p>
      )}

      {isKbo ? (
        <>
          <p style={cap}>{full ? '타순이 가득 찼습니다 (✕로 빼고 교체)' : '타자 선택 (타석 많은 순)'}</p>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '5px', maxHeight: 130, overflowY: 'auto' }}>
            {pool.map(b => (
              <button key={b.name} onClick={() => !full && onLineupChange([...lineup, b])} disabled={full}
                style={{ ...mini, color: full ? '#4b5563' : '#d1d5db', cursor: full ? 'not-allowed' : 'pointer', padding: '4px 8px' }}>
                {b.name}{b.position ? ` · ${b.position}` : ''}
              </button>
            ))}
            {pool.length === 0 && <span style={{ color: '#6b7280', fontSize: '12px' }}>선택 가능한 타자가 없습니다.</span>}
          </div>
        </>
      ) : (
        <p style={{ color: '#6b7280', fontSize: '12px' }}>나만의 팀 타순입니다. 구단을 고르면 해당 구단 선수로 바뀝니다.</p>
      )}
    </div>
  );
}