#!/usr/bin/env python3
"""構成依存と任意の仮想資金リスクを読取検査。推奨・購入・上限を生成しない。"""
import argparse
import json
import math
from collections import Counter
from pathlib import Path

from cycle04_operations import ticket_event, require
from probability_presentation import validate as validate_probability


def key_text(key):
    return key[0]+':'+','.join(map(str,key[1]))


def tickets(items, horses, frames):
    require(isinstance(items,list), '明示的な券一覧が必要')
    out={}
    for item in items:
        require(isinstance(item,dict), '券の形式が不正')
        key=ticket_event(item,horses=horses,frames=frames)
        require(key not in out, '同一券の重複・二重計上を拒否')
        require(isinstance(item.get('scenario_id'),str) and item['scenario_id'].strip(), '券のシナリオが必要')
        out[key]=item
    return out


def dependencies(items,anchor):
    horse_counts=Counter();scenarios=Counter()
    for key,item in items.items():
        if key[0]!='BRACKET_QUINELLA':horse_counts.update(key[1])
        scenarios.update([item['scenario_id']])
    count=len(items);hits=horse_counts.get(anchor,0) if anchor is not None else None
    return {'unique_ticket_count':count,'horse_ticket_counts':dict(sorted(horse_counts.items())),
            'scenario_ticket_counts':dict(sorted(scenarios.items())),
            'anchor_ticket_count':hits,'anchor_ticket_ratio':hits/count if count and anchor is not None else None,
            'frame_ticket_count':sum(k[0]=='BRACKET_QUINELLA' for k in items),
            'note':'馬別点数は重複所属するため総和を券点数としない。枠連を特定馬の依存へ代用しない。'}


def hit(key,order,frames,place_places):
    kind,values=key;top2=order[:2];top3=order[:3]
    if kind=='WIN':return order[0]==values[0]
    if kind=='PLACE':return values[0] in order[:place_places]
    if kind=='BRACKET_QUINELLA':return tuple(sorted(frames[h] for h in top2))==values
    if kind=='QUINELLA':return set(values)==set(top2)
    if kind=='WIDE':return set(values).issubset(top3)
    if kind=='EXACTA':return tuple(top2)==values
    if kind=='TRIO':return set(values)==set(top3)
    return tuple(top3)==values


def audit(candidates,selected,anchor,*,field_horses=None,frames=None,allocations=None,joint_model=None):
    require(anchor is None or type(anchor) is int and anchor>0, '軸馬は正整数または未確認null')
    require(isinstance(selected,list) and (candidates is None or isinstance(candidates,list)), '券一覧が必要')
    require(all(isinstance(t,dict) for t in selected+(candidates or [])), '券の形式が不正')
    frames=frames or {}
    if field_horses is None:
        require(not any(t.get('type')=='BRACKET_QUINELLA' for t in selected+(candidates or [])), '枠連には全頭/枠対応が必要')
        require(all(isinstance(t.get('horses'),list) and all(type(h) is int and h>0 for h in t['horses'])
                    for t in selected+(candidates or [])), '馬番号一覧が不正')
        horses={h for t in selected+(candidates or []) for h in t.get('horses',[])}|({anchor} if anchor is not None else set())
    else:
        require(isinstance(field_horses,list) and field_horses and
                all(type(h) is int and h>0 for h in field_horses) and len(set(field_horses))==len(field_horses), '全出走馬集合が不正')
        horses=set(field_horses);require(anchor is None or anchor in horses,'軸馬が出走集合にない')
    chosen=tickets(selected,horses,frames);proposed=tickets(candidates,horses,frames) if candidates is not None else None
    if proposed is not None:
        require(set(chosen).issubset(proposed), '採用券は候補券の部分集合である必要')
        require(all(chosen[k]['scenario_id']==proposed[k]['scenario_id'] for k in chosen), '同一券の候補/採用シナリオが不一致')
    result={'schema_version':'dependency-risk-report-v1',
            'candidate':dependencies(proposed,anchor) if proposed is not None else None,
            'selected':dependencies(chosen,anchor),'candidate_status':'UNRECORDED' if proposed is None else 'RECORDED',
            'finance':{'status':'NOT_CALCULATED','total_allocation_yen':None,'max_single_ticket_yen':None,
                       'horse_dependent_allocation_yen':None,'frame_dependent_allocation_yen':None,
                       'full_loss_probability':None,'full_loss_basis':'未算定・周辺確率の積を使わない'},
            'recommendation_changed':False,'performance_promoted':False}
    if allocations is None:
        require(joint_model is None, '配分なしで金銭全損率を算定しない');return result
    require(isinstance(allocations,list),'任意の仮想配分一覧が必要')
    funding={}
    for a in allocations:
        require(isinstance(a,dict),'仮想配分が不正')
        key=ticket_event(a,horses=horses,frames=frames)
        require(key in chosen and key not in funding, '未採用券/重複配分を拒否')
        amount=a.get('amount_yen');require(type(amount) is int and amount>=0,'配分は0以上の整数円が必要')
        funding[key]=amount
    require(set(funding)==set(chosen),'採用券全点の仮想配分を明示。欠測を0へ補完しない')
    total=sum(funding.values());horse_money=Counter();frame_money=Counter()
    for key,amount in funding.items():
        (frame_money if key[0]=='BRACKET_QUINELLA' else horse_money).update({v:amount for v in set(key[1])})
    finance=result['finance'];finance.update(status='HYPOTHETICAL_ALLOCATION',total_allocation_yen=total,
        max_single_ticket_yen=max(funding.values(),default=0),horse_dependent_allocation_yen=dict(sorted(horse_money.items())),
        frame_dependent_allocation_yen=dict(sorted(frame_money.items())))
    if joint_model is None or total==0:
        require(total>0 or joint_model is None,'資金0の全損率は未算定');return result
    require(field_horses is not None and isinstance(joint_model,dict), '共同結果モデルには全出走馬と明示モデルが必要')
    require(joint_model.get('coverage')=='EXHAUSTIVE_DISJOINT' and joint_model.get('source_ref'), '網羅・排他な共同結果モデルの根拠が必要')
    places=joint_model.get('place_places');require(type(places) is int and 1<=places<=min(3,len(horses)), '複勝対象着順が必要')
    rows=joint_model.get('outcomes');require(isinstance(rows,list) and rows,'共同結果シナリオが必要')
    seen=set();probabilities=[];loss=[]
    for row in rows:
        require(isinstance(row,dict),'共同結果シナリオが不正')
        order=row.get('finish_order')
        require(isinstance(order,list) and all(type(h) is int for h in order) and
                len(order)==len(horses) and set(order)==horses and tuple(order) not in seen,'全頭着順の欠測/重複/取消馬を拒否')
        seen.add(tuple(order));p=row.get('probability')
        validate_probability({'probability':p,'probability_method':joint_model.get('probability_method'),
                              'calibration_ref':joint_model.get('calibration_ref')})
        require(type(p) in (int,float),'未算定の共同結果確率を0へ変換しない');probabilities.append(p)
        if not any(amount>0 and hit(key,order,frames,places) for key,amount in funding.items()):loss.append(p)
    require(abs(math.fsum(probabilities)-1)<=1e-6,'共同結果確率の総和は1が必要')
    finance.update(full_loss_probability=math.fsum(loss),full_loss_basis='入力した共同結果モデルに条件付く値・証跡認証なし',
                   probability_method=joint_model['probability_method'],source_ref=joint_model['source_ref'],calibration_authenticated=False)
    return result


def describe(report):
    f=report['finance'];p=f['full_loss_probability']
    return {'候補点数':'未記録' if report['candidate'] is None else report['candidate']['unique_ticket_count'],
            '採用点数':report['selected']['unique_ticket_count'],'馬別依存点数':report['selected']['horse_ticket_counts'],
            'シナリオ別点数':report['selected']['scenario_ticket_counts'],
            '軸依存率':'未算定' if report['selected']['anchor_ticket_ratio'] is None else str(report['selected']['anchor_ticket_ratio']*100)+'%',
            '最大単券仮想配分':f['max_single_ticket_yen'] if f['max_single_ticket_yen'] is not None else '未算定',
            '馬別仮想依存額':f['horse_dependent_allocation_yen'] if f['horse_dependent_allocation_yen'] is not None else '未算定',
            '枠券点数':report['selected']['frame_ticket_count'],
            '枠別仮想依存額':f['frame_dependent_allocation_yen'] if f['frame_dependent_allocation_yen'] is not None else '未算定',
            '馬依存額の範囲':'馬番指定券の配分のみ。枠連は枠別に表示',
            '全損率':'未算定' if p is None else str(p*100)+'%','全損率の根拠':f['full_loss_basis']}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('path',type=Path);a=p.parse_args(argv)
    try:
        request=json.loads(a.path.read_text(encoding='utf-8'))
        r=audit(request.get('candidates'),request['selected'],request['anchor'],field_horses=request.get('field_horses'),
                frames={int(k):v for k,v in request.get('frames',{}).items()},allocations=request.get('allocations'),joint_model=request.get('joint_model'))
        print(json.dumps(describe(r),ensure_ascii=False,indent=2));return 0
    except (ValueError,OSError,TypeError,KeyError) as exc:
        print('依存・任意市場リスクの確認失敗：'+str(exc));return 1


if __name__=='__main__':raise SystemExit(main())
