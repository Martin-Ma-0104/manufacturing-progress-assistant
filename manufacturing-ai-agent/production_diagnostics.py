"""Pure reviewed-data analysis. Co-occurrence is evidence for review, not a cause."""
from collections import defaultdict
import abnormality
from production_dashboard import machine_sort, summarize

CAUTION = ('投入计划是母卷计划，不是合格成品目标；异常记录分钟不是净停机。'
           '同期出现仅供复核，不代表因果或已识别系统瓶颈。产品组合与班次覆盖不同不能直接比较产能。'
           '异常班次可能来自已核对的时间推定；这里沿用已录入归属，不重新推定。')
GROUPS = ('machine', 'date', 'shift', 'details', 'category')


def summary(rows, events):
    production = summarize(rows)
    if not rows:
        production = {k: (0 if k in ('record_count', 'machine_count') else None) for k in production}
    return dict(**production,
        input_delta=sum(r['input_rolls']-r['planned_rolls'] for r in rows) if rows else None,
        input_shortfall=sum(max(r['planned_rolls']-r['input_rolls'],0) for r in rows) if rows else None,
        input_excess=sum(max(r['input_rolls']-r['planned_rolls'],0) for r in rows) if rows else None,
        abnormalities=abnormality.summarize(events))


def analyze(snapshot, group_by='details'):
    if group_by not in GROUPS:
        raise ValueError('Unsupported diagnostics group.')
    rows, events = snapshot['rows'], snapshot.get('abnormalities', [])
    total = summary(rows, events)
    warnings = [snapshot['coverage']['text'], abnormality.coverage(events), CAUTION]
    # Deliberately aggregate independently; never JOIN event details to output rows.
    production_groups, event_groups, change_groups = defaultdict(list), defaultdict(list), defaultdict(list)
    def key(r):
        if group_by == 'machine': return (r['machine_id'],)
        if group_by == 'date': return (r['production_date'],)
        if group_by == 'shift': return (r['shift'],)
        return (r['production_date'],r['machine_id'],r['shift'])
    if group_by == 'category':
        table=[]
        for s in abnormality.grouped(events,'category'):
            minutes=s['reported_minutes']
            denominator=total['abnormalities']['reported_minutes']
            share=minutes/denominator if minutes is not None and denominator else None
            table.append({'异常类别':s['label'],'异常记录时长合计（分钟）':minutes,
                          '已知事件分钟占比':f'{share:.1%}' if share is not None else '不可用','异常记录数（条）':s['event_count'],
                          '缺分钟记录数（条）':s['missing_minutes_count']})
        return dict(summary=total,rows=table,warnings=warnings)
    for r in rows: production_groups[key(r)].append(r)
    for e in events: event_groups[key(e)].append(e)
    for e in snapshot.get('changeovers',[]): change_groups[key(e)].append(e)
    keys=set(production_groups)|set(event_groups)
    if group_by == 'machine': ordered=sorted(keys,key=lambda k:machine_sort(k[0]))
    elif group_by == 'details': ordered=sorted(keys,key=lambda k:(k[0],machine_sort(k[1]),k[2] or ''))
    else: ordered=sorted(keys,key=lambda k:k[0] or '')
    table=[]
    for k in ordered:
        prod, ev = production_groups[k], event_groups[k]
        s=summary(prod,ev)
        label = ({'设备':k[0]} if group_by=='machine' else {'生产日期':k[0]} if group_by=='date'
                 else {'班次':abnormality.SHIFT_NAMES[k[0]]} if group_by=='shift'
                 else {'生产日期':k[0],'设备':k[1],'班次':abnormality.SHIFT_NAMES[k[2]]})
        table.append({**label,'计划投入（母卷）':s['planned_rolls'],'实际投入（母卷）':s['input_rolls'],
            '投入偏差（实际−计划，母卷）':s['input_delta'],'未达计划（母卷，逐记录）':s['input_shortfall'],
            '超额投入（母卷，逐记录）':s['input_excess'],'投入计划达成率':s['attainment'],
            '合格成品（卷）':s['qualified_rolls'],'实际产出（m²）':s['actual_output_m2'],
            '合格产出（m²）':s['qualified_output_m2'],'面积合格率':s['qualification'],
            '生产记录数':s['record_count'],'异常记录数（条）':len(ev),
            '异常记录时长合计（分钟）':s['abnormalities']['reported_minutes'],
            '缺分钟记录数（条）':s['abnormalities']['missing_minutes_count'],
            '起止不完整（条）':s['abnormalities']['incomplete_time_count'],
            '重叠事件（条）':s['abnormalities']['overlap_event_count'],
            '产品／规格':'；'.join(sorted({r['product'] for r in prod})) or '无生产记录',
            '确认换产':'；'.join(f"{e['production_date']} {abnormality.SHIFT_NAMES[e['shift']]}：{e['from_product']} → {e['to_product']}" for e in change_groups[k]) or '无已确认事件',
            '记录提示':('生产已记录' if prod else '无生产记录，不补零')+'；'+('异常已记录' if ev else '未录入异常，不代表无异常')})
    return dict(summary=total,rows=table,warnings=warnings)


def presentation(snapshot, group_by='details', chart='none'):
    if chart not in ('none','deviation','category') or (chart=='deviation' and group_by!='machine') or (chart=='category' and group_by!='category'):
        raise ValueError('Invalid diagnostic chart/group.')
    result=analyze(snapshot,group_by)
    scope=snapshot['scope']
    title=f"{scope['start_date']} 至 {scope['end_date']} · {abnormality.SHIFT_NAMES[scope['shift']]} · "+('、'.join(scope['machines']) or '全部设备')+' · 生产差距与异常证据'
    data=None
    if chart != 'none':
        field='投入偏差（实际−计划，母卷）' if chart=='deviation' else '异常记录时长合计（分钟）'
        label='设备' if chart=='deviation' else '异常类别'
        known=[r for r in result['rows'] if r[field] is not None]
        if len(result['rows'])>1000:
            raise ValueError('Too many chart groups; narrow scope.')
        data=dict(group=label,kind=chart,rows=[dict(label=r[label],value=r[field]) for r in known],
                  omitted_groups=len(result['rows'])-len(known),partial_groups=[])
        if chart=='category':
            data['partial_groups']=[dict(label=r[label],missing_count=r['缺分钟记录数（条）']) for r in known if r['缺分钟记录数（条）']]
    return dict(title=title,rows=result['rows'][:1000],total_rows=len(result['rows']),
                truncated=len(result['rows'])>1000,chart=data,warnings=result['warnings'])
