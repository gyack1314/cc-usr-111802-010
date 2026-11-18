"""把储水异常、人口暴露、替代供水与水车容量合成分配方案。

各地区自报的储水异常比例只在基线年份与覆盖范围一致时可比；无法对齐时
保留分组名次并说明比较限制，不给合并名次。分配按各区自身口径的净需求
比例配置水车：净需求=人口×人均需求×异常比例−可用替代供水。
"""
import hashlib,json,math
from .evidence import records

METRIC='tws_deficit_ratio'
DEFAULT_PER_CAPITA_L=50.0

def _latest(rows):
    return max(rows,key=lambda r:(r['source']['received_at'],r['revision'])) if rows else None

def _group_key(entry):
    b=entry.get('baseline');c=entry.get('coverage')
    return (b['start_year'],b['end_year'],c) if b and c else None

def _group_label(key):
    return '%s-%s年/%s'%key if key else '基准不明'

def assess(db,known_at):
    """按 known_at 时点已取得的资料形成一份水车分配方案。"""
    param=_latest(records(db,'parameter',known_at))
    per_capita=(param['payload']['per_capita_need'] if param else DEFAULT_PER_CAPITA_L)/1000.0
    fleet=_latest(records(db,'fleet',known_at))
    trucks_total=fleet['payload']['trucks'] if fleet else 0
    truck_cap=fleet['payload']['capacity_per_truck'] if fleet else 0
    pops={}
    for r in records(db,'population',known_at):
        region=r['payload']['region']
        if region not in pops or (r['source']['received_at'],r['revision'])>(pops[region]['source']['received_at'],pops[region]['revision']):pops[region]=r
    alts={}
    for r in records(db,'alternative_supply',known_at):alts.setdefault(r['payload']['region'],[]).append(r)
    limitations=[]
    if not fleet:limitations.append('缺少水车队资料，无法配置运力')
    if not param:limitations.append('缺少人均需求参数，按默认 %g L/人/天估算'%DEFAULT_PER_CAPITA_L)
    regions=[]
    obs=[r for r in records(db,'observation',known_at) if r['payload'].get('metric')==METRIC]
    for o in sorted(obs,key=lambda r:r['payload']['region']):
        p=o['payload'];region=p['region']
        entry={'region':region,'deficit_ratio':p['value'],'baseline':p.get('baseline'),
               'coverage':p.get('coverage'),'sources':[o['source']['sha256']],'notes':[]}
        supplies=alts.get(region,[])
        entry['alternative_supply']=round(sum(s['payload']['value'] for s in supplies),6)
        entry['sources']+=[s['source']['sha256'] for s in supplies]
        pop=pops.get(region)
        entry['population']=pop['payload']['value'] if pop else None
        if pop:entry['sources'].append(pop['source']['sha256'])
        if not _group_key(entry):entry['notes'].append('基准不明：缺少基线年份或覆盖范围，异常比例按自报口径使用')
        if pop is None:
            entry.update(status='资料不全',missing=['人口'],gross_need=None,emergency_need=None,net_need=None)
            entry['notes'].append('缺少人口资料，无法估算需求，本轮不参与分配')
        else:
            gross=round(entry['population']*per_capita,6)
            emergency=round(gross*p['value'],6)
            net=round(max(0.0,emergency-entry['alternative_supply']),6)
            entry.update(status='已评估',gross_need=gross,emergency_need=emergency,net_need=net)
        regions.append(entry)
    evaluated=[e for e in regions if e['status']=='已评估']
    groups={}
    for e in evaluated:groups.setdefault(_group_key(e),[]).append(e)
    known=[k for k in groups if k]
    if len(known)>1:
        limitations.append('基线口径不一致（'+'、'.join(_group_label(k) for k in sorted(known))+'），异常比例不能跨组精确排序，未给出合并名次')
    if None in groups:
        limitations.append('基准不明地区：'+'、'.join(e['region'] for e in groups[None])+'，不参与精确排序')
    for key,members in groups.items():
        for i,e in enumerate(sorted(members,key=lambda e:(-e['net_need'],e['region'])),1):
            e['rank_in_group']=i if key else None;e['group']=_group_label(key)
    rankable=bool(evaluated) and len(groups)==1 and None not in groups
    for e in regions:e['rank']=None
    if rankable:
        for i,e in enumerate(sorted(evaluated,key=lambda e:(-e['net_need'],e['region'])),1):e['rank']=i
    alloc={e['region']:0 for e in regions}
    eligible=[e for e in evaluated if e['net_need']>0 and truck_cap>0]
    total_need=sum(e['net_need'] for e in eligible)
    if eligible and trucks_total>0 and total_need>0:
        raw={e['region']:trucks_total*e['net_need']/total_need for e in eligible}
        cap={e['region']:max(1,math.ceil(e['net_need']/truck_cap-1e-9)) for e in eligible}
        for e in eligible:
            r=e['region'];alloc[r]=min(int(raw[r]),cap[r])
        leftover=trucks_total-sum(alloc.values())
        order=sorted(eligible,key=lambda e:(-(raw[e['region']]-int(raw[e['region']])),-e['net_need'],e['region']))
        for e in order:
            if leftover<=0:break
            r=e['region']
            if alloc[r]<cap[r]:alloc[r]+=1;leftover-=1
        while leftover>0:
            open_regions=[e for e in eligible if alloc[e['region']]<cap[e['region']]]
            if not open_regions:break
            e=sorted(open_regions,key=lambda e:(-(e['net_need']-alloc[e['region']]*truck_cap),e['region']))[0]
            alloc[e['region']]+=1;leftover-=1
    for e in regions:
        t=alloc[e['region']]
        e['trucks_allocated']=t
        e['aid_volume']=round(t*truck_cap,6)
        e['unmet_need']=round(max(0.0,e['net_need']-t*truck_cap),6) if e['status']=='已评估' else None
    totals={'net_need':round(sum(e['net_need'] for e in evaluated),6),
            'aid':round(sum(e['aid_volume'] for e in regions),6),
            'unmet':round(sum(e['unmet_need'] for e in evaluated),6),
            'trucks_used':sum(alloc.values()),'trucks_total':trucks_total}
    plan={'known_at':known_at,'metric':METRIC,
          'method':'净需求=人口×人均需求×异常比例−替代供水；按净需求比例配置水车，名次仅在基线口径一致的组内有效',
          'parameters':{'per_capita_need_m3':per_capita,'sources':[param['source']['sha256']] if param else []},
          'fleet':{'trucks':trucks_total,'capacity_per_truck':truck_cap,'total_capacity':round(trucks_total*truck_cap,6),
                   'sources':[fleet['source']['sha256']] if fleet else []},
          'regions':regions,
          'comparability':{'rankable':rankable,
                           'groups':{_group_label(k):sorted(e['region'] for e in v) for k,v in sorted(groups.items(),key=lambda kv:_group_label(kv[0]))},
                           'limitations':limitations},
          'totals':totals}
    plan['fingerprint']=hashlib.sha256(json.dumps(plan,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
    return plan

def explain(before,after):
    """比较两期分配方案，说明援助量与未满足需求的变化及原因。"""
    b={e['region']:e for e in before['regions']};a={e['region']:e for e in after['regions']}
    regions={};notes=[]
    for r in sorted(set(b)|set(a)):
        x,y=b.get(r),a.get(r)
        if x is None:notes.append('%s 为新增评估地区'%r);continue
        if y is None:notes.append('%s 本轮不再纳入评估'%r);continue
        d={'aid_before':x['aid_volume'],'aid_after':y['aid_volume'],
           'unmet_before':x['unmet_need'],'unmet_after':y['unmet_need'],
           'trucks_before':x['trucks_allocated'],'trucks_after':y['trucks_allocated']}
        regions[r]=d
        if x['status']!='已评估' or y['status']!='已评估':
            notes.append('%s 评估状态变化：%s→%s'%(r,x['status'],y['status']));continue
        if y['alternative_supply']!=x['alternative_supply']:
            notes.append('%s 补交替代供水证据（%g→%g m³/天），净需求 %g→%g m³/天'%(r,x['alternative_supply'],y['alternative_supply'],x['net_need'],y['net_need']))
        if y['aid_volume']!=x['aid_volume'] or y['unmet_need']!=x['unmet_need']:
            notes.append('%s 援助量 %g→%g m³/天（水车 %d→%d 辆），未满足需求 %g→%g m³/天'%(r,x['aid_volume'],y['aid_volume'],x['trucks_allocated'],y['trucks_allocated'],x['unmet_need'],y['unmet_need']))
    ta,tb=before['totals'],after['totals']
    if before['fleet']['trucks']!=after['fleet']['trucks']:
        notes.append('水车队规模 %d→%d 辆'%(before['fleet']['trucks'],after['fleet']['trucks']))
    notes.append('合计未满足需求 %g→%g m³/天；投入水车 %d→%d 辆'%(ta['unmet'],tb['unmet'],ta['trucks_used'],tb['trucks_used']))
    return {'before':before['fingerprint'],'after':after['fingerprint'],'regions':regions,
            'totals':{'aid_before':ta['aid'],'aid_after':tb['aid'],'unmet_before':ta['unmet'],'unmet_after':tb['unmet']},
            'explanation':notes}
