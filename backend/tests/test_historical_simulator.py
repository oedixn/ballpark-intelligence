import copy
from datetime import date
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from game_simulator.historical import HistoricalInputs, HistoryUnavailable, simulate_historical
from game_simulator.season_backtest import SeasonInputs, parse_starting_lineups, read_prior
from game_simulator.collect_history import reconcile


def history_fixture():
    h={"schema_version":1,"complete":True,"season":2026,"coverage_start":"2026-01-01",
       "coverage_before":"2026-10-31","source":"test daily lines","collected_at":"2026-10-31",
       "hitters":[],"pitchers":[]}
    for team in ('A','B'):
        for i in range(9):
            for day in ('2026-04-01','2026-04-02','2026-04-03'):
                h['hitters'].append(dict(player_id=f'{team}{i}',player_name=f'{team} hitter {i}',
                    team_name=team,game_date=day,appearance=1,ab=10,h=3,double_hit=1,triple_hit=0,
                    hr=0,bb=1,hbp=0,pa=11))
        for day in ('2026-04-01','2026-04-02','2026-04-03'):
            h['pitchers'].append(dict(player_id=f'{team}p',player_name=f'{team} pitcher',team_name=team,
                game_date=day,appearance=1,tbf=25,outs=18,h=5,hr=1,bb=2,hbp=0,so=4,er=2,gs=1))
    return h


def priors(h):
    return {kind:{r['player_id']:(r|{'name':r['player_name'],'teams':[r['team_name']]}) for r in h[kind]}
            for kind in ('hitters','pitchers')}


def fixture_game():
    return {'G_DT':'20260402','AWAY_NM':'A','HOME_NM':'B',
            'lineup_a':[f'A hitter {i}' for i in range(9)],'lineup_b':[f'B hitter {i}' for i in range(9)],
            'lineup_ids_a':[f'A{i}' for i in range(9)],'lineup_ids_b':[f'B{i}' for i in range(9)],
            'T_PIT_P_ID':'Ap','B_PIT_P_ID':'Bp','T_PIT_P_NM':'A pitcher','B_PIT_P_NM':'B pitcher'}


class PointInTimeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.folder=Path(self.temp.name)
        self.h=history_fixture();self.save()

    def tearDown(self):self.temp.cleanup()

    def save(self):
        (self.folder/'2026.json').write_text(json.dumps(self.h),encoding='utf-8')

    def inputs(self):return HistoricalInputs(date(2026,4,2),self.folder)

    def test_same_day_future_and_later_transfer_never_enter_roster_or_rates(self):
        base=self.inputs()
        for kind in ('hitters','pitchers'):
            for r in self.h[kind]:
                if r['game_date']>='2026-04-02':
                    r['team_name']='later team';r['h']=999999
        self.save();changed=self.inputs()
        self.assertEqual(base.hitters,changed.hitters)
        self.assertEqual(base.pitchers,changed.pitchers)
        self.assertEqual(base.league_average(),changed.league_average())
        self.assertEqual(changed.metadata['last_game_date'],'2026-04-01')
        self.assertEqual(len(changed.team('A')['lineup']),9)

    def test_invalid_coverage_missing_data_and_duplicates_fail_without_annual_fallback(self):
        with self.assertRaises(HistoryUnavailable):HistoricalInputs(date(2026,11,1),self.folder)
        with self.assertRaises(HistoryUnavailable):HistoricalInputs(date(2025,5,1),self.folder)
        with self.assertRaises(HistoryUnavailable):HistoricalInputs(date(2026,4,1),self.folder)
        self.h['hitters'].append(copy.deepcopy(self.h['hitters'][0]));self.save()
        with self.assertRaises(ValueError):self.inputs()

    def test_seed_reproducibility_and_win_loss_draw_accounting(self):
        names_a=fixture_game()['lineup_a'];names_b=fixture_game()['lineup_b']
        args=(self.inputs(),'A',names_a,'B',names_b)
        r=simulate_historical(*args,n_games=30,seed=42,pitcher_a_id='Ap',pitcher_b_id='Bp')
        self.assertEqual(r,simulate_historical(*args,n_games=30,seed=42,pitcher_a_id='Ap',pitcher_b_id='Bp'))
        self.assertEqual(sum(x['count'] for x in r['score_distribution']),30)
        self.assertEqual(r['matchup']['team_a_wins']+r['matchup']['team_b_wins']+r['matchup']['draws'],30)

    def test_same_name_players_use_ids_and_aliases_cannot_duplicate_a_player(self):
        for r in self.h['hitters']:
            if r['player_id']=='A1':r['player_name']='A hitter 0'
        self.save();inputs=self.inputs()
        lineup,records=inputs.lineup('A',[f'A{i}' for i in range(9)])
        self.assertEqual(len({r['player_id'] for r in records}),9)
        self.assertEqual(lineup[0].name,lineup[1].name)
        ids=[f'A{i}' for i in range(9)];ids[1]='A hitter 2'
        with self.assertRaises(ValueError):inputs.lineup('A',ids)

    def test_dated_api_reloads_stats_instead_of_trusting_client_totals(self):
        from fastapi.testclient import TestClient
        from app.main import app
        client=TestClient(app)
        payload={'as_of':'2026-04-02','team_a_name':'A','team_b_name':'B','n_games':20,'seed':7,
                 'team_a_lineup':[],'team_b_lineup':[]}
        for side,team in (('a','A'),('b','B')):
            payload[f'team_{side}_lineup']=[dict(name=f'{team} hitter {i}',ab=10,hits=3,double=1,
                                                 triple=0,hr=0,bb=1,hbp=0) for i in range(9)]
        with patch.dict(os.environ,{'SIMULATOR_HISTORY_DIR':str(self.folder)}):
            with patch('app.main.get_conn',side_effect=AssertionError('annual DB must not be read')):
                r=client.post('/api/simulate/multi',json=payload)
                self.assertEqual(r.status_code,200,r.text)
                for side in ('a','b'):
                    for p in payload[f'team_{side}_lineup']:p.update(ab=999,hits=999,hr=999)
                mutated=client.post('/api/simulate/multi',json=payload)
                self.assertEqual(r.json(),mutated.json())
                payload['as_of']='2026-11-01'
                self.assertEqual(client.post('/api/simulate/multi',json=payload).status_code,409)


class WalkForwardTests(unittest.TestCase):
    def test_cached_monte_carlo_preserves_fixed_seed_scores_and_eleven_inning_limit(self):
        from game_simulator.season_backtest import _FixedLineupMatch
        from game_simulator.simulator_main import MatchSimulator,PlayerProb
        lineup=[PlayerProb(str(i),.09,.15,.04,.005,.03) for i in range(9)]
        for seed in range(3):
            baseline=MatchSimulator('A',lineup,'B',list(reversed(lineup)),seed=seed).simulate_many(30,max_innings=11)
            cached=_FixedLineupMatch('A',lineup,'B',list(reversed(lineup)),seed=seed).simulate_many(30,max_innings=11)
            self.assertEqual(baseline,cached)

    def test_missing_players_are_rejected_by_independent_event_totals(self):
        lines={'hitters':[dict(h=3,hr=1,bb=2,hbp=0,pa=12,r=2)],
               'pitchers':[dict(h=3,hr=1,bb=2,hbp=0,tbf=12)]}
        games=[dict(G_ID='game1',T_SCORE_CN='1',B_SCORE_CN='1')]
        self.assertTrue(reconcile(lines,games)['passed'])
        lines['pitchers'][0]['h']=2
        with self.assertRaisesRegex(ValueError,'불일치'):reconcile(lines,games)

    def test_markov_cached_innings_preserve_the_known_two_inning_distribution(self):
        from game_simulator.simulator_main import LineupMarkovModel,PlayerProb
        model=LineupMarkovModel([PlayerProb(str(i),0,0,0,0,0) for i in range(9)],max_runs=2)
        with patch.object(model,'inning_run_distribution',return_value=([.5,.5,0],[1/9]*9)) as calculate:
            result=model.game_run_distribution(innings=2)
        for actual,expected in zip(result,[.25,.5,.25]):self.assertAlmostEqual(actual,expected)
        self.assertLessEqual(calculate.call_count,9)

    def test_game_date_and_later_stats_do_not_change_a_prediction(self):
        h=history_fixture();prior=priors(h);g=fixture_game()
        expected=SeasonInputs(h,prior).fixture(g)
        future=copy.deepcopy(h)
        for kind in ('hitters','pitchers'):
            for r in future[kind]:
                if r['game_date']>=g['G_DT'][:4]+'-'+g['G_DT'][4:6]+'-'+g['G_DT'][6:]:
                    r['ab']=99999;r['tbf']=99999;r['h']=99999;r['team_name']='future transfer'
        self.assertEqual(expected,SeasonInputs(future,prior).fixture(g))

    def test_opening_day_and_new_player_use_only_previous_year_prior(self):
        h=history_fixture();g=fixture_game();g['G_DT']='20260328'
        g['lineup_a'][0]='new hitter';g['lineup_ids_a'][0]='new'
        a,b,audit=SeasonInputs(h,priors(h)).fixture(g)
        self.assertIsNone(audit['last_current_season_game'])
        self.assertTrue(all(r['current_opportunities']==0 for r in audit['players']))
        self.assertEqual(audit['players'][0]['prior_source'],'previous_league')
        self.assertEqual(len(a),9);self.assertEqual(len(b),9)

    def test_annual_loader_ignores_target_year_even_if_its_counts_are_invalid(self):
        import csv
        with tempfile.TemporaryDirectory() as folder:
            for kind,filename,fields in (
                ('h','player_hitter_stats.csv',['ab','h','double_hit','triple_hit','hr','bb','hbp']),
                ('p','player_pitcher_stats.csv',['tbf','h','hr','bb','hbp'])):
                with (Path(folder)/filename).open('w',newline='',encoding='utf-8') as f:
                    w=csv.DictWriter(f,fieldnames=['season_year','player_id','player_name','team_name']+fields);w.writeheader()
                    w.writerow(dict(season_year=2025,player_id=kind,player_name='past',team_name='A')|dict.fromkeys(fields,10))
                    w.writerow(dict(season_year=2026,player_id=kind,player_name='future',team_name='A')|dict.fromkeys(fields,'bad future'))
            p,_=read_prior(2026,folder)
            self.assertEqual(p['hitters']['h']['name'],'past')
            self.assertEqual(p['pitchers']['p']['tbf'],10)


if __name__=='__main__':unittest.main()
