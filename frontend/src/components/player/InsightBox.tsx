import type { PlayerStat } from '../../data/mockPlayers';

interface Props {
  name: string;
  stats: PlayerStat[];
}

function generateInsight(name: string, stats: PlayerStat[]): string[] {
  const insights: string[] = [];
  const get = (label: string) => stats.find((s) => s.label === label);

  const isPitcher = stats.some(s => s.label === 'ERA' || s.label === 'WHIP');

  if (isPitcher) {
    const era  = get('ERA');
    const w    = get('승');
    const sv   = get('세이브');
    const so   = get('탈삼진');
    const whip = get('WHIP');

    if (era) {
      if (era.value === 0) {
        insights.push(`${name} 선수는 현재 시즌 무실점을 기록 중인 투수입니다.`);
      } else if (era.value <= 2.5) {
        insights.push(`${name} 선수는 ERA ${era.value}로 리그 최정상급 선발/마무리 투수입니다.`);
      } else if (era.value <= 4.0) {
        insights.push(`${name} 선수는 ERA ${era.value}로 리그 평균 이상의 안정적인 투수입니다.`);
      } else {
        insights.push(`${name} 선수는 ERA ${era.value}로 현재 안정감 개선이 필요한 상황입니다.`);
      }
    }
    if (sv && sv.value >= 10) {
      insights.push(`${sv.value}세이브로 팀의 핵심 마무리 투수로 활약하고 있습니다.`);
    } else if (sv && sv.value >= 5) {
      insights.push(`${sv.value}세이브를 기록하며 불펜에서 중요한 역할을 수행하고 있습니다.`);
    }
    if (so && so.value >= 50) {
      insights.push(`${so.value}탈삼진으로 강력한 구위를 바탕으로 타자를 압도하고 있습니다.`);
    } else if (so && so.value >= 20) {
      insights.push(`${so.value}탈삼진을 기록하며 꾸준한 삼진 능력을 보여주고 있습니다.`);
    }
    if (whip) {
      if (whip.value <= 1.0) {
        insights.push(`WHIP ${whip.value}로 매우 뛰어난 제구력을 보유한 투수입니다.`);
      } else if (whip.value <= 1.3) {
        insights.push(`WHIP ${whip.value}로 안정적인 제구력을 갖추고 있습니다.`);
      } else {
        insights.push(`WHIP ${whip.value}로 주자 허용이 많아 제구력 개선이 필요합니다.`);
      }
    }
    if (w && w.value >= 8) {
      insights.push(`${w.value}승을 기록하며 팀 승리에 크게 기여하고 있는 에이스급 투수입니다.`);
    }
  } else {
    const woba = get('wOBA');
    const ops  = get('OPS');
    const hr   = get('HR');
    const bb   = get('BB%');
    const k    = get('K%');

    const topStats = stats.filter((s) => s.percentile >= 80);
    if (topStats.length >= 3) {
      insights.push(`${name} 선수는 리그 상위 ${100 - Math.round(stats.reduce((a, b) => a + b.percentile, 0) / stats.length)}% 수준의 엘리트 타자입니다.`);
    } else if (topStats.length >= 1) {
      insights.push(`${name} 선수는 특정 영역에서 리그 평균 이상의 기량을 보유한 타자입니다.`);
    } else {
      insights.push(`${name} 선수는 현재 리그 평균 수준의 타자입니다.`);
    }
    if (hr && hr.percentile >= 80) {
      insights.push(`홈런(${hr.value}개, 상위 ${100 - hr.percentile}%)에서 리그 최상위권으로, 강한 장타력을 보유하고 있습니다.`);
    }
    if (woba && woba.percentile >= 80) {
      insights.push(`wOBA ${woba.value} (상위 ${100 - woba.percentile}%)로 출루 및 장타 능력이 매우 뛰어납니다.`);
    }
    if (bb && k) {
      if (bb.percentile >= 70 && k.percentile <= 50) {
        insights.push(`볼넷 비율이 높고 삼진 비율이 낮아 선구안이 우수한 컨택형 타자입니다.`);
      } else if (k.percentile >= 70) {
        insights.push(`삼진 비율(${k.value}%)이 높은 편으로, 컨택 능력 개선이 필요합니다.`);
      }
    }
    if (ops && ops.percentile >= 85) {
      insights.push(`OPS ${ops.value}는 리그 최정상급 수치로, 팀 득점에 핵심적인 역할을 합니다.`);
    }
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