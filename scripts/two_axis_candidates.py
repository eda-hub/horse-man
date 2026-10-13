"""70/30は試験トリガー。二頭軸候補を生成し、標準採用/性能を認証しない。"""
from itertools import permutations


def compare(production):
    ranking=production['ranking']
    rates={p['horse_no']:p['top3_probability'] for p in production['probabilities']}
    axes=[h for h in ranking if rates[h]>=.70]
    if len(axes)<2:
        return {'status':'NOT_APPLICABLE','reason':'推定3着内率70%以上が2頭未満','performance_promotion':'NOT_APPROVED'}
    # 3頭以上も同じProduction順位を使い、価格や結果から選ばない。
    chosen=axes[:2]
    trio=[h for h in ranking[:6] if h not in chosen]
    trifecta=[h for h in ranking if h not in chosen and rates[h]>=.30]
    return {'status':'SHADOW_CANDIDATE','axes':chosen,'qualified_axes':axes,
            'axis_reason':'固定Production順位の上位2頭を選定（3着内率70%以上）',
            'trio_tickets':[{'type':'TRIO','horses':sorted(chosen+[h])} for h in trio],
            'trifecta_tickets':[{'type':'TRIFECTA','horses':list(p)} for h in trifecta for p in permutations(chosen+[h])],
            'trio_points':len(trio),'trifecta_points':6*len(trifecta),
            'joint_probability_status':'NOT_CALCULATED','performance_promotion':'NOT_APPROVED',
            'note':'候補全点。◎中心・着順役割の標準制約を満たす採用点とは別。'}
