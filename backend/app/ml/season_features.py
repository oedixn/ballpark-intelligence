"""Shared yearly features and sequence checks for LSTM training/inference."""

from collections import Counter, defaultdict
import logging
import math
import re

logger = logging.getLogger(__name__)
PREPROCESSING_VERSION = 2


def innings_to_outs(value):
    """Parse KBO fractions and baseball decimal notation using integer outs.

    '54 2/3' and '54.2' both mean 164 outs, not 54.2 decimal innings.
    Missing, negative, and ambiguous decimal values are rejected.
    """
    text = str(value).strip()
    match = re.fullmatch(r'(?:(\d+)\s+)?([12])/3', text)
    if match:
        return int(match[1] or 0) * 3 + int(match[2])
    match = re.fullmatch(r'(\d+)(?:\.([012])0*)?', text)
    if match:
        return int(match[1]) * 3 + int(match[2] or 0)
    raise ValueError(f'유효하지 않은 이닝 표기: {value!r}')


def _count(value):
    number = float(value)
    if not math.isfinite(number) or number < 0 or not number.is_integer():
        raise ValueError(f'유효하지 않은 누적 기록: {value!r}')
    return int(number)


def _groups(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[(str(row.get('player_id', '')), int(row['season_year']))].append(row)
    return sorted(groups.items())


def _sum_counts(rows, keys):
    return {key: sum(_count(row[key]) for row in rows) for key in keys}


def aggregate_hitter_seasons(rows, min_pa=50, *, include_games=False):
    """Combine team stints before applying eligibility and recomputing rates."""
    seasons = []
    keys = ['pa', 'ab', 'h', 'double_hit', 'triple_hit', 'hr', 'bb', 'hbp', 'so', 'sf']
    if include_games:
        keys = keys + ['g']
    for (player_id, year), stints in _groups(rows):
        try:
            totals = _sum_counts(stints, keys)
            pa, ab, hits = totals['pa'], totals['ab'], totals['h']
            singles = hits - totals['double_hit'] - totals['triple_hit'] - totals['hr']
            if pa < min_pa or ab <= 0 or singles < 0 or hits > ab:
                continue
            obp_denominator = ab + totals['bb'] + totals['hbp'] + totals['sf']
            avg = hits / ab
            slg = (hits + totals['double_hit'] + 2 * totals['triple_hit'] + 3 * totals['hr']) / ab
            obp = (hits + totals['bb'] + totals['hbp']) / obp_denominator
            woba = (totals['bb'] * 0.69 + totals['hbp'] * 0.72 + singles * 0.87
                    + totals['double_hit'] * 1.217 + totals['triple_hit'] * 1.529
                    + totals['hr'] * 1.74) / pa
        except (KeyError, TypeError, ValueError):
            logger.warning('타자 %s %s 시즌: 잘못되거나 누락된 누적 기록으로 제외', player_id, year)
            continue
        seasons.append({
            **totals, 'player_id': player_id, 'season_year': year,
            'avg': avg, 'obp': obp, 'slg': slg, 'ops': obp + slg,
            'iso': slg - avg, 'bb_rate': totals['bb'] / pa * 100,
            'k_rate': totals['so'] / pa * 100, 'woba': woba,
        })
    return seasons


def aggregate_pitcher_seasons(rows, min_games=5):
    """Sum integer outs/counts and derive per-nine, workload and role features."""
    seasons = []
    keys = ['g', 'gs', 'h', 'hr', 'bb', 'so', 'er']
    for (player_id, year), stints in _groups(rows):
        try:
            totals = _sum_counts(stints, keys)
            outs = sum(innings_to_outs(row['ip']) for row in stints)
            games = totals['g']
            if games < min_games or outs <= 0 or totals['gs'] > games:
                continue
        except (KeyError, TypeError, ValueError):
            logger.warning('투수 %s %s 시즌: 잘못되거나 누락된 누적 기록으로 제외', player_id, year)
            continue
        innings = outs / 3
        seasons.append({
            **totals, 'player_id': player_id, 'season_year': year,
            'outs': outs, 'ip': innings,
            'era': totals['er'] * 27 / outs,
            'whip': (totals['h'] + totals['bb']) * 3 / outs,
            'k9': totals['so'] * 27 / outs, 'bb9': totals['bb'] * 27 / outs,
            'hr9': totals['hr'] * 27 / outs, 'ip_per_g': innings / games,
            'starter_ratio': totals['gs'] / games,
        })
    return seasons


def valid_sequence(rows, keys, *, season_counts=None):
    """The same consecutive-year, unique-year and finite-value contract everywhere."""
    if not rows:
        return False
    try:
        years = [int(row['season_year']) for row in rows]
        counts = season_counts if season_counts is not None else Counter(years)
        return (years == list(range(years[0], years[0] + len(rows)))
                and all(counts[year] == 1 for year in years)
                and all(row[key] is not None and math.isfinite(float(row[key]))
                        for row in rows for key in keys))
    except (KeyError, TypeError, ValueError, OverflowError):
        return False


def latest_sequence(data, keys, length=3):
    ordered = sorted(data, key=lambda row: int(row['season_year']))
    recent = ordered[-length:]
    counts = Counter(int(row['season_year']) for row in ordered)
    if len(recent) != length or not valid_sequence(recent, keys, season_counts=counts):
        return None
    return recent
