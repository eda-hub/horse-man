"""70/30は試験トリガー。二頭軸候補を生成し、標準採用/性能を認証しない。"""
from itertools import permutations
import math


def compare(production, *, cancelled_horses=()):
    """固定順位を保ち、明示取消だけ除外。欠測で候補や確率を推測しない。"""
    base={'joint_probability_status':'NOT_CALCULATED','joint_probability':None,
          'selected_points':None,'performance_promotion':'NOT_APPROVED',
          'standard_adoption':'NOT_APPROVED'}
    def missing(reason):
        return {**base,'status':'MISSING','reason':reason}
    if not isinstance(production,dict):return missing('固定Production情報が不足')
    ranking=production.get('ranking');rows=production.get('probabilities')
    if not isinstance(ranking,list) or not ranking or any(type(h) is not int or h<=0 for h in ranking) or len(set(ranking))!=len(ranking):
        return missing('固定Production順位が不足または不正')
    if not isinstance(cancelled_horses,(list,tuple)) or any(type(h) is not int or h not in ranking for h in cancelled_horses) or len(set(cancelled_horses))!=len(cancelled_horses):
        return missing('取消馬の固定順位との対応が不足または不正')
    ranking=[h for h in ranking if h not in cancelled_horses]
    if not isinstance(rows,list):return missing('3着内率が不足')
    rates={}
    for row in rows:
        if not isinstance(row,dict) or type(row.get('horse_no')) is not int:return missing('馬と3着内率の対応が不正')
        h=row['horse_no']
        if h in cancelled_horses:continue
        p=row.get('top3_probability')
        if h not in ranking or h in rates or type(p) not in (int,float) or not math.isfinite(p) or not 0<=p<=1:
            return missing('3着内率が未算定または対応が不正')
        rates[h]=p
    if set(rates)!=set(ranking):return missing('実出走対象の3着内率が不足')
    axes=[h for h in ranking if rates[h]>=.70]
    if len(axes)<2:
        return {**base,'status':'NOT_APPLICABLE','reason':'推定3着内率70%以上が2頭未満'}
    # 3頭以上も同じProduction順位を使い、価格や結果から選ばない。
    chosen=axes[:2]
    trio=[h for h in ranking[:6] if h not in chosen]
    trifecta=[h for h in ranking if h not in chosen and rates[h]>=.30]
    return {**base,'status':'SHADOW_CANDIDATE','axes':chosen,'qualified_axes':axes,
            'cancelled_horses':list(cancelled_horses),
            'axis_reason':'固定Production順位の上位2頭を選定（3着内率70%以上）',
            'trio_tickets':[{'type':'TRIO','horses':sorted(chosen+[h])} for h in trio],
            'trifecta_tickets':[{'type':'TRIFECTA','horses':list(p)} for h in trifecta for p in permutations(chosen+[h])],
            'trio_points':len(trio),'trifecta_points':6*len(trifecta),
            'joint_probability_status':'NOT_CALCULATED','performance_promotion':'NOT_APPROVED',
            'note':'候補全点。◎中心・着順役割の標準制約を満たす採用点とは別。'}
