import type { PlayerStat } from '../../data/mockPlayers';

interface Props {
  name: string;
  stats: PlayerStat[];
}

// 백분위 기반 자동 해석 생성
function generateInsight(name: string, stats: PlayerStat[]): string[] {
  const insights: string[] = [];

  const get = (label: string) => stats.find((s) => s.label === label);

  const woba  = get('wOBA');
  const ops   = get('OPS');
  const hr    = get('HR');
  const bb    = get('BB%');
  const k     = get('K%');

  // 전체 평가
  const topStats = stats.filter((s) => s.percentile >= 80);
  if (topStats.length >= 3) {
    insights.push(`${name} 선수는 리그 상위 ${100 - Math.round(stats.reduce((a, b) => a + b.percentile, 0) / stats.length)}% 수준의 엘리트 타자입니다.`);
  } else if (topStats.length >= 1) {
    insights.push(`${name} 선수는 특정 영역에서 리그 평균 이상의 기량을 보유한 타자입니다.`);
  } else {
    insights.push(`${name} 선수는 현재 리그 평균 수준의 타자입니다.`);
  }

  // 파워 평가
  if (hr && hr.percentile >= 80) {
    insights.push(`홈런(${hr.value}개, 상위 ${100 - hr.percentile}%)에서 리그 최상위권으로, 강한 장타력을 보유하고 있습니다.`);
  }

  // 출루 평가
  if (woba && woba.percentile >= 80) {
    insights.push(`wOBA ${woba.value} (상위 ${100 - woba.percentile}%)로 출루 및 장타 능력이 매우 뛰어납니다.`);
  }

  // 선구안 평가
  if (bb && k) {
    if (bb.percentile >= 70 && k.percentile <= 50) {
      insights.push(`볼넷 비율이 높고 삼진 비율이 낮아 선구안이 우수한 컨택형 타자입니다.`);
    } else if (k.percentile >= 70) {
      insights.push(`삼진 비율(${k.value}%)이 높은 편으로, 컨택 능력 개선이 필요합니다.`);
    }
  }

  // OPS 평가
  if (ops && ops.percentile >= 85) {
    insights.push(`OPS ${ops.value}는 리그 최정상급 수치로, 팀 득점에 핵심적인 역할을 합니다.`);
  }

  return insights;
}

export default function InsightBox({ name, stats }: Props) {
  const insights = generateInsight(name, stats);

  return (
    <div className="bg-gray-800 rounded-xl p-6">
      <p className="text-gray-400 text-xs mb-4 uppercase tracking-widest">AI 분석</p>
      <div className="space-y-3">
        {insights.map((text, i) => (
          <div key={i} className="flex gap-3">
            <span className="text-orange-400 mt-1 shrink-0">•</span>
            <p className="text-gray-200 text-sm leading-relaxed">{text}</p>
          </div>
        ))}
      </div>
    </div>
  );
}