#!/usr/bin/env python3
"""第4サイクル10月17日・36レースの事後結果全数照合と正式KPIの不適格認証判定。"""
import argparse
import json
import re
import sys
from pathlib import Path

DATE = '2026-10-17'
MORNING = 'docs/validation/persistence-intents/2026-10-17/morning.json'
DAY = 'docs/validation/reconciliations/2026-10-17-day-index.json'
RESULTS = 'docs/validation/reviews/cycle_04/2026-10-17-all-36-official-results-reference.json'
SIX = 'docs/validation/reviews/cycle_04/2026-10-17-jra-postrace-reference.json'
DECISION = 'docs/validation/reviews/cycle_04/2026-10-17-formal-kpi-certification-decision.json'
FORMAL_LEDGER = 'docs/validation/records/cycle_04/2026-10-17.json'


class FullDayReviewError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise FullDayReviewError(message)


def read(root, relative):
    require(isinstance(relative, str) and relative.startswith('docs/validation/'),
            'unexpected input path')
    f = (root / relative).resolve()
    require(f.is_relative_to(root) and f.is_file(), 'missing source: ' + relative)
    return json.loads(f.read_text(encoding='utf-8'))


def check(root):
    root = Path(root).resolve()
    morning = read(root, MORNING)
    day = read(root, DAY)
    full = read(root, RESULTS)
    six = read(root, SIX)
    cert = read(root, DECISION)
    expected = morning.get('required_race_ids')
    require(morning.get('race_date_jst') == DATE and
            isinstance(expected, list) and len(expected) == 36 and
            len(set(expected)) == 36, 'morning intent must retain 36 unique races')
    require(full.get('schema_version') == 'cycle04-postrace-all-declared-races-v1' and
            full.get('race_date_jst') == DATE and
            full.get('source_intent_path') == MORNING and
            full.get('source_day_index_path') == DAY and
            full.get('source_six_race_review_path') == SIX,
            'full-day provenance cannot be changed')
    require(day.get('schema_version') == 'cycle04-unfinished-day-index-v1' and
            day.get('full_day_postrace_reference', {}).get('path') == RESULTS and
            day.get('full_day_postrace_reference', {}).get('formal_ledger_created') is False,
            'day reference is not a formal ledger')
    require(not (root / FORMAL_LEDGER).exists(), 'formal day ledger unexpectedly exists; rerun formal contract')
    coverage = full.get('coverage', {})
    require(coverage.get('declared') == 36 and
            coverage.get('result_top3_retrieved') == 36 and
            coverage.get('result_official_page_identified_count') == 6 and
            coverage.get('prior_forecast_reviewable') == 6 and
            coverage.get('no_evaluable_final_forecast') == 30,
            'result coverage misrepresented')
    races = full.get('races')
    index = day.get('races')
    decisions = cert.get('decisions')
    require(all(isinstance(items, list) and len(items) == 36
                for items in (races, index, decisions)) and
            [row.get('race_id') for row in races] == expected and
            [row.get('race_id') for row in index] == expected and
            [row.get('race_id') for row in decisions] == expected,
            '36-race scope, order, or decision set mismatch')
    lookup_six = {x.get('race_id'): x for x in six.get('races', [])}
    require(len(lookup_six) == 6, 'original six reviews missing')
    have_forecasts = 0
    for ix, (row, original, decision) in enumerate(zip(races, index, decisions)):
        rid = expected[ix]
        require(row.get('scheduled_post_time_jst', '').startswith(DATE + 'T'),
                rid + ': date missing')
        require(row.get('source', {}).get('overview_url', '').startswith(
                    'https://sports.yahoo.co.jp/keiba/race/list/'),
                rid + ': race list source missing')
        result = row.get('result', {})
        top = result.get('top3_horse_numbers')
        horses = result.get('top_finishers')
        require(result.get('status') == 'RESULT_PUBLISHED' and
                isinstance(top, list) and len(top) == 3 and
                len(set(top)) == 3 and
                isinstance(horses, list) and len(horses) == 3 and
                all(isinstance(h, int) and h > 0 for h in top) and
                [z.get('horse_no') for z in horses] == top and
                all(isinstance(z.get('horse_name'), str) and z['horse_name']
                    for z in horses),
                rid + ': finishing order inconsistent')
        positions = [z['position'] for z in horses]
        require((positions == [1, 2, 2] and
                 result.get('dead_heat') == {'position': 2, 'horse_numbers': top[1:]}
                 if rid == DATE + '-KYOTO-12' else
                 positions == [1, 2, 3] and result.get('dead_heat') is None),
                rid + ': placing/dead-heat mismatch')
        require(original.get('full_day_postrace_result', {}).get('top3_horse_numbers') == top and
                original['full_day_postrace_result']['source_path'] == RESULTS and
                original['full_day_postrace_result']['official_result_url'] ==
                row['source']['official_url'],
                rid + ': original day index differs from full results')
        prev = lookup_six.get(rid)
        if prev:
            have_forecasts += 1
            require(prev['result']['finishing_order_horse_numbers'][:3] == top and
                    row.get('previous_six_race_review_path') == SIX and
                    row['pre_off_forecast']['path'] == prev['prediction_evidence']['path'] and
                    original['prediction']['path'] == row['pre_off_forecast']['path'],
                    rid + ': six-result or fixed prediction changed')
            require(row['source'].get('official_individual_page_verified') is True and
                    row['source'].get('official_individual_page_identified') is True and
                    row['source'].get('official_url') == prev['source']['url'] and
                    re.match(r'^https://(?:www\\.jra\\.go\\.jp|jra\\.jp)/JRADB/accessS\\.html\\?CNAME=',
                             row['source']['official_url']),
                    rid + ': verified JRA source mismatch')
        else:
            require(not row.get('previous_six_race_review_path') and
                    original['prediction']['status'] == 'NOT_PERSISTED' and
                    row['pre_off_forecast']['path'] is None,
                    rid + ': invented result-time forecast')
            require(row['source'].get('official_url') is None and
                    row['source'].get('official_individual_page_verified') is False and
                    row['source'].get('official_individual_page_identified') is False and
                    row['source'].get('top3_transcription_source') ==
                    'SPORTS_NAVIGATION_JRA_RESULTS_REPRODUCTION',
                    rid + ': secondary results must not claim primary JRA verification')
        require(decision.get('official_result_page') == row['source']['official_url'] and
                decision.get('finishers_available') is True and
                decision.get('pre_off_prediction_artifact') == original['prediction'].get('path') and
                decision.get('initial_forecast', {}).get('status') == 'MISSING',
                rid + ': formal decision provenance error')
        for kind, valkey in [('prediction', 'score'), ('recommendation', 'hit'),
                             ('shadow', 'non_degradation')]:
            value = decision.get(kind)
            require(isinstance(value, dict) and value.get('status') == 'INELIGIBLE' and
                    value.get(valkey, 'MISSING') is None,
                    rid + ': invalid formal KPI promotion: ' + kind)
    require(have_forecasts == 6, 'expected six research-only predictions')
    c = cert.get('certification', {})
    require(cert.get('schema_version') == 'cycle04-postrace-certification-rejection-v1' and
            cert.get('race_date_jst') == DATE and
            cert.get('official_day_ledger_exists_at_check') is False and
            cert.get('official_day_ledger_path') == FORMAL_LEDGER and
            cert.get('original_intent_path') == MORNING and
            cert.get('result_reference_path') == RESULTS and
            cert.get('reconciliation_day_index_path') == DAY and
            c.get('status') == 'REJECTED_UNDER_V1_7_0' and
            c.get('formal_eligible_denominators') == {
                'prediction': 0, 'recommendation': 0, 'shadow': 0} and
            all(v is None for v in c.get('rates', {}).values()),
            'formal KPI status must remain rejected and null')
    return {
        'day': DATE, 'verified_result_races': 36, 'linked_six_predictions': have_forecasts,
        'without_fixed_final_prediction': 30, 'tie_2nd_place': 1,
        'official_result_pages_verified': 6,
        'formal_eligible_denominators': c['formal_eligible_denominators'],
        'formal_certification': 'REJECTED_UNDER_V1_7_0',
        'note': '結果照合は成立。発走前の公式scopeがないため正式KPI認証は不合格。',
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root', type=Path, default=Path('.'))
    args = ap.parse_args()
    try:
        result = check(args.root)
    except (FullDayReviewError, OSError, ValueError, KeyError, TypeError) as error:
        print('FULL_DAY_REVIEW_INVALID: ' + str(error), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
