"""Read-only, bounded production facts for the AI assistant.

Only this module sees numeric source rows. The external client receives the
small, locally calculated result of ``query_facts``, never the snapshot itself.
"""
from contextlib import contextmanager
from datetime import date, timedelta
import hashlib
import json
from pathlib import Path
import sqlite3
import abnormality

from database import DB_PATH
from production_dashboard import aggregate_machines, machine_sort, summarize

ROW_FIELDS = (
    'production_date', 'shift', 'machine_id', 'product', 'planned_rolls',
    'input_rolls', 'qualified_rolls', 'actual_output_m2', 'qualified_output_m2',
    'reported_yield_pct',
)
EVENT_FIELDS = ('production_date', 'machine_id', 'shift', 'from_product', 'to_product')
METRICS = (
    'planned_rolls', 'input_rolls', 'qualified_rolls', 'actual_output_m2',
    'qualified_output_m2', 'attainment', 'qualification', 'machine_count', 'record_count',
)
SCOPE_FIELDS = {'start_date', 'end_date', 'shift', 'machines'}
QUERY_FIELDS = SCOPE_FIELDS | {'view', 'metrics'}
SHIFT_NAMES = {None: '全部班次', 'Day': '白班', 'Night': '夜班'}


def _iso_day(value):
    if type(value) is not str:
        raise ValueError('日期必须为 YYYY-MM-DD 字符串。')
    try:
        parsed = date.fromisoformat(value)
    except ValueError as error:
        raise ValueError('日期必须为 YYYY-MM-DD。') from error
    if parsed.isoformat() != value:
        raise ValueError('日期必须为 YYYY-MM-DD。')
    return parsed


def _machine_ids(machines):
    if machines is None:
        return []
    if type(machines) is not list:
        raise ValueError('设备必须为 ID 字符串列表。')
    if any(type(item) is not str or not item or item.strip() != item
           or len(item) > 128 or any(ord(c) < 32 for c in item) for item in machines):
        raise ValueError('设备 ID 必须为非空、无控制字符的字符串。')
    return sorted(set(machines), key=machine_sort)


def normalize_scope(start_date, end_date, shift=None, machines=None):
    """Normalize a strict inclusive scope of at most 30 calendar dates."""
    start, end = _iso_day(start_date), _iso_day(end_date)
    if not 0 <= (end - start).days < 30:
        raise ValueError('起止日期须按顺序，且最多包含 30 天。')
    if shift is not None and (type(shift) is not str or shift not in ('Day', 'Night')):
        raise ValueError('班次必须为 Day、Night 或 None。')
    return dict(start_date=start.isoformat(), end_date=end.isoformat(),
                shift=shift, machines=_machine_ids(machines))


def _scope_dict(scope):
    if type(scope) is not dict or set(scope) != SCOPE_FIELDS:
        raise ValueError('查询范围字段必须精确匹配日期、班次和设备。')
    return normalize_scope(**scope)


@contextmanager
def _readonly_connection(db_path):
    """Never create a database; SQLite enforces both file and connection read-only."""
    path = Path(db_path).expanduser().resolve()
    if not path.is_file():
        raise ValueError('生产数据库不存在；请先完成本地数据初始化。')
    connection = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)
    try:
        connection.execute('PRAGMA query_only = ON')
        connection.row_factory = sqlite3.Row
        yield connection
    finally:
        connection.close()


def _has_table(connection, name):
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,),
    ).fetchone() is not None


def _catalog(connection):
    dates, machines = set(), set()
    for table in ('slitting_records','abnormality_events'):
        if _has_table(connection, table):
            dates.update(row[0] for row in connection.execute('SELECT DISTINCT production_date FROM '+table))
            machines.update(row[0] for row in connection.execute('SELECT DISTINCT machine_id FROM '+table))
    return {'dates': sorted(dates), 'machines': sorted(machines, key=machine_sort)}


def catalog(db_path=DB_PATH):
    """Historical production IDs and dates, without inspecting simulated masters.

    A missing file raises ValueError; an initialized file without production
    tables returns empty lists and is not modified.
    """
    with _readonly_connection(db_path) as connection:
        return _catalog(connection)


def _matching_rows(rows, scope):
    return [row for row in rows
            if scope['start_date'] <= row['production_date'] <= scope['end_date']
            and (scope['shift'] is None or row['shift'] == scope['shift'])
            and (not scope['machines'] or row['machine_id'] in scope['machines'])]


def _coverage(rows, scope, available_machines):
    start, end = _iso_day(scope['start_date']), _iso_day(scope['end_date'])
    dates = [(start + timedelta(days=i)).isoformat() for i in range((end - start).days + 1)]
    observed = sorted({row['production_date'] for row in rows})
    expected = [scope['shift']] if scope['shift'] else ['Day', 'Night']
    machines = scope['machines'] or available_machines
    pairs = {}
    for row in rows:
        pairs.setdefault((row['production_date'], row['machine_id']), set()).add(row['shift'])
    partial = [dict(production_date=day, machine_id=machine,
                    observed_shifts=[shift for shift in expected if shift in shifts],
                    missing_shifts=[shift for shift in expected if shift not in shifts])
               for (day, machine), shifts in sorted(pairs.items())
               if not set(expected).issubset(shifts)]
    result = dict(
        observed_dates=observed,
        missing_dates=[day for day in dates if day not in observed],
        expected_shifts=expected,
        partial_machine_dates=partial,
        unrecorded_machine_dates_count=sum((day, machine) not in pairs
                                          for day in dates for machine in machines),
    )
    for name, shift in (('day', 'Day'), ('night', 'Night')):
        selected = [row for row in rows if row['shift'] == shift]
        result[name] = dict(record_count=len(selected),
                            machine_count=len({r['machine_id'] for r in selected}),
                            observed_dates=sorted({r['production_date'] for r in selected}))
    missing = '、'.join(result['missing_dates']) or '无'
    text = (f"当前范围有记录 {len(observed)} 天／{len(dates)} 天；无记录日期：{missing}。"
            f"白班 {result['day']['record_count']} 条、夜班 {result['night']['record_count']} 条记录；"
            f"已有设备日期中 {len(partial)} 组缺少所选班次记录。"
            '缺失记录不代表零产量；未记录设备状态未知，记录覆盖不代表全厂数据完整。')
    result['text'] = result['message'] = text
    return result


def _snapshot_parts(rows, events, scope, available_machines):
    daily = [dict(production_date=day, **summarize(
        [row for row in rows if row['production_date'] == day]))
        for day in sorted({row['production_date'] for row in rows})]
    return dict(scope=scope, rows=rows, summary=summarize(rows),
                machines=aggregate_machines(rows), daily=daily,
                coverage=_coverage(rows, scope, available_machines), changeovers=events,
                available_machines=list(available_machines))


def read_snapshot(scope, db_path=DB_PATH):
    """Read one consistent numeric snapshot without any source or private notes."""
    scope = _scope_dict(scope)
    with _readonly_connection(db_path) as connection:
        connection.execute('BEGIN')
        available = _catalog(connection)['machines']
        if set(scope['machines']) - set(available):
            raise ValueError('包含未知设备；请使用生产记录中的历史设备 ID。')
        if not _has_table(connection, 'slitting_records'):
            rows, events = [], []
        else:
            conditions = 'production_date BETWEEN ? AND ?'
            params = [scope['start_date'], scope['end_date']]
            if scope['shift']:
                conditions += ' AND shift=?'
                params.append(scope['shift'])
            if scope['machines']:
                conditions += ' AND machine_id IN (' + ','.join('?' for _ in scope['machines']) + ')'
                params.extend(scope['machines'])
            rows = [dict(row) for row in connection.execute(
                'SELECT ' + ','.join(ROW_FIELDS) + ' FROM slitting_records WHERE ' + conditions
                + ' ORDER BY production_date,machine_id,shift,product', params)]
            events = []
            if _has_table(connection, 'changeover_events'):
                keys = {(r['production_date'], r['machine_id'], r['shift']) for r in rows}
                events = [dict(row) for row in connection.execute(
                    'SELECT ' + ','.join(EVENT_FIELDS) + ' FROM changeover_events WHERE '
                    + conditions + ' ORDER BY production_date,machine_id,shift', params)
                    if (row['production_date'], row['machine_id'], row['shift']) in keys]
        # An abnormality may exist without a production observation on that day.
        conditions = 'production_date BETWEEN ? AND ?'
        params = [scope['start_date'], scope['end_date']]
        if scope['shift']:
            conditions += ' AND shift=?'
            params.append(scope['shift'])
        if scope['machines']:
            conditions += ' AND machine_id IN (' + ','.join('?' for _ in scope['machines']) + ')'
            params.extend(scope['machines'])
        abnormalities = [dict(row) for row in connection.execute(
            'SELECT '+','.join(abnormality.PUBLIC_FIELDS)+' FROM abnormality_events WHERE '+conditions+
            ' ORDER BY production_date,machine_id,event_id', params)] if _has_table(connection,'abnormality_events') else []
    snapshot = _snapshot_parts(rows, events, scope, available)
    snapshot['abnormalities'] = abnormalities
    canonical = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)
    snapshot['version'] = hashlib.sha256(canonical.encode('utf-8')).hexdigest()
    return snapshot


def _query_scope(snapshot, query):
    if type(query) is not dict or set(query) != QUERY_FIELDS:
        raise ValueError('工具参数字段不匹配，不能增加 SQL 或其它指令。')
    if type(query['view']) is not str or query['view'] not in ('overview', 'comparison', 'daily', 'changeovers'):
        raise ValueError('不支持该查询视图。')
    if type(query['shift']) is not str or query['shift'] not in ('All', 'Day', 'Night'):
        raise ValueError('工具班次必须为 All、Day 或 Night。')
    if type(query['machines']) is not list:
        raise ValueError('工具设备参数必须为 ID 字符串列表。')
    metrics = query['metrics']
    if (type(metrics) is not list or not 1 <= len(metrics) <= 3
            or any(type(metric) is not str or metric not in METRICS for metric in metrics)
            or len(set(metrics)) != len(metrics)):
        raise ValueError('每次须选择 1 至 3 个不同的受支持指标。')
    parent = _scope_dict(snapshot['scope'])
    scope = normalize_scope(query['start_date'], query['end_date'],
                            None if query['shift'] == 'All' else query['shift'], query['machines'])
    if scope['start_date'] < parent['start_date'] or scope['end_date'] > parent['end_date']:
        raise ValueError('问题日期超出页面所选范围，请先调整筛选。')
    if parent['shift'] is not None and scope['shift'] != parent['shift']:
        raise ValueError('问题班次超出页面所选范围，请先调整筛选。')
    if not scope['machines']:
        scope['machines'] = list(parent['machines'])
    if set(scope['machines']) - set(snapshot['available_machines']):
        raise ValueError('问题包含未知设备 ID。')
    if parent['machines'] and not set(scope['machines']).issubset(parent['machines']):
        raise ValueError('问题设备超出页面所选范围，请先调整筛选。')
    return scope


def _metric_text(summary, metric):
    labels = {'planned_rolls': ('计划投入', '卷'), 'input_rolls': ('实际投入', '卷'),
              'qualified_rolls': ('合格成品', '卷'), 'actual_output_m2': ('实际产出', 'm²'),
              'qualified_output_m2': ('合格产出', 'm²'), 'machine_count': ('已记录设备', '台'),
              'record_count': ('生产记录', '条')}
    if metric in ('attainment', 'qualification'):
        numerator, denominator, label, unit = (
            ('input_rolls', 'planned_rolls', '投入计划达成率', '卷') if metric == 'attainment'
            else ('qualified_output_m2', 'actual_output_m2', '面积合格率', 'm²'))
        n, d = summary[numerator], summary[denominator]
        value = summary[metric] if d else '不可用（分母为零）'
        return f'{label} {value}（{n:,.1f} {unit} ÷ {d:,.1f} {unit}，按合计计算）'
    label, unit = labels[metric]
    value = summary[metric]
    rendered = f'{value:,.1f}' if metric.endswith('_m2') else f'{value:,}'
    return f'{label} {rendered} {unit}'


def _fact(text):
    return {'id': 'fact-' + hashlib.sha256(text.encode('utf-8')).hexdigest()[:20], 'text': text}


def query_facts(snapshot, query):
    """Calculate whitelisted facts inside the UI's already approved scope only."""
    scope = _query_scope(snapshot, query)
    rows = _matching_rows(snapshot['rows'], scope)
    keys = {(r['production_date'], r['machine_id'], r['shift']) for r in rows}
    events = [event for event in snapshot['changeovers']
              if (event['production_date'], event['machine_id'], event['shift']) in keys]
    parts = _snapshot_parts(rows, events, scope, snapshot['available_machines'])
    machine_label = '、'.join(scope['machines']) if scope['machines'] else '全部已记录设备'
    context = f"{scope['start_date']} 至 {scope['end_date']} · {SHIFT_NAMES[scope['shift']]} · {machine_label}"
    facts = [_fact(context + '：' + parts['coverage']['text'])]
    if not rows:
        facts.append(_fact(context + '：暂无生产记录；无法提供产量或比率，缺失记录不能当作零。'))
    elif query['view'] == 'changeovers':
        if not events:
            facts.append(_fact(context + '：所选有生产记录的范围内没有已确认换产事件；不从产品代码自动判断换产。'))
        for event in events:
            facts.append(_fact(
                f"{event['production_date']} · {event['machine_id']} · {SHIFT_NAMES[event['shift']]}："
                f"已确认换产，{event['from_product']} → {event['to_product']}。"))
    else:
        if query['view'] == 'comparison':
            groups = [(row['machine_id'], row) for row in parts['machines']]
            observed_machines = {row['machine_id'] for row in parts['machines']}
            for missing in scope['machines']:
                if missing not in observed_machines:
                    facts.append(_fact(context + f' · {missing}：暂无记录，设备状态未知，不代表零产量。'))
        elif query['view'] == 'daily':
            groups = [(row['production_date'], row) for row in parts['daily']]
        else:
            groups = [('汇总', parts['summary'])]
        for name, summary in groups:
            for metric in query['metrics']:
                facts.append(_fact(context + f' · {name}：' + _metric_text(summary, metric) + '。'))
    return dict(scope=scope, view=query['view'], facts=facts, coverage=parts['coverage'])


def export_preview(snapshot):
    """The maximum numeric envelope the user can inspect before permitting calls.

    The API client still sends only query_facts' question-specific result. This
    explicit reconstruction deliberately drops unknown, raw, and source fields.
    """
    summary_fields = METRICS
    def summary(row):
        return {key: row[key] for key in summary_fields}
    raw = snapshot['coverage']
    coverage = {key: list(raw[key]) for key in ('observed_dates', 'missing_dates', 'expected_shifts')}
    coverage['partial_machine_dates'] = [
        {key: (list(item[key]) if key.endswith('_shifts') else item[key])
         for key in ('production_date', 'machine_id', 'observed_shifts', 'missing_shifts')}
        for item in raw['partial_machine_dates']]
    for shift in ('day', 'night'):
        coverage[shift] = {key: (list(raw[shift][key]) if key == 'observed_dates' else raw[shift][key])
                           for key in ('record_count', 'machine_count', 'observed_dates')}
    for key in ('unrecorded_machine_dates_count', 'text', 'message'):
        coverage[key] = raw[key]
    preview = dict(scope=_scope_dict(snapshot['scope']), summary=summary(snapshot['summary']),
                machines=[dict(machine_id=row['machine_id'], **summary(row)) for row in snapshot['machines']],
                daily=[dict(production_date=row['production_date'], **summary(row)) for row in snapshot['daily']],
                coverage=coverage,
                changeovers=[{key: event[key] for key in EVENT_FIELDS} for event in snapshot['changeovers']])
    if snapshot.get('abnormalities'):
        preview['abnormalities'] = dict(summary=abnormality.summarize(snapshot['abnormalities']),
            machines=abnormality.grouped(snapshot['abnormalities'],'machine'),
            categories=abnormality.grouped(snapshot['abnormalities'],'category'),
            coverage=abnormality.coverage(snapshot['abnormalities']))
    from production_diagnostics import summary as diagnostic_summary
    d=diagnostic_summary(snapshot['rows'],snapshot.get('abnormalities',[]))
    preview['diagnostics']={key:d[key] for key in ('input_delta','input_shortfall','input_excess')}
    return preview


METRIC_LABELS = {
    'planned_rolls':'计划投入（卷）', 'input_rolls':'实际投入（卷）',
    'qualified_rolls':'合格成品（卷）', 'actual_output_m2':'实际产出（m²）',
    'qualified_output_m2':'合格产出（m²）', 'attainment':'投入计划达成率',
    'qualification':'面积合格率', 'machine_count':'已记录设备数（台）', 'record_count':'生产记录数（条）',
    'reported_minutes':'异常记录时长合计（分钟）', 'event_count':'异常记录数（条）',
    'valid_minutes_count':'有分钟记录数（条）', 'missing_minutes_count':'缺分钟记录数（条）',
    'open_count':'处理中记录数（条）', 'unknown_status_count':'状态未确认（条）',
}
ABNORMAL_METRICS = ('reported_minutes','event_count','valid_minutes_count','missing_minutes_count',
                    'open_count','unknown_status_count')
GROUP_LABELS = {'machine':'设备', 'date':'生产日期', 'shift':'班次', 'category':'异常类别', 'overview':'范围'}
ANALYSIS_FIELDS = SCOPE_FIELDS | {'domain','group_by','metrics','categories','status','chart'}
MAX_TABLE_ROWS = 1000


def _analysis_scope(snapshot, query):
    if not isinstance(query,dict) or set(query) != ANALYSIS_FIELDS:
        raise ValueError('Invalid analysis fields.')
    domain, group = query['domain'], query['group_by']
    allowed_groups = ('overview','machine','date','shift') if domain == 'production' else ('overview','machine','date','shift','category','details')
    if domain not in ('production','abnormalities') or group not in allowed_groups:
        raise ValueError('Unsupported analysis domain/group.')
    allowed = METRICS if domain == 'production' else ABNORMAL_METRICS
    metrics = query['metrics']
    if not isinstance(metrics,list) or not 1 <= len(metrics) <= 9 or len(set(metrics)) != len(metrics) or any(m not in allowed for m in metrics):
        raise ValueError('Invalid analysis metrics.')
    categories = query['categories']
    known = {e['category'] for e in snapshot.get('abnormalities',[])}
    if not isinstance(categories,list) or any(not isinstance(c,str) or c not in known for c in categories) or len(set(categories)) != len(categories):
        raise ValueError('Unknown abnormality categories.')
    if query['status'] not in ('All','Open','Closed','Unknown') or query['chart'] not in ('none','bar'):
        raise ValueError('Unsupported status/chart.')
    if domain == 'production' and (categories or query['status'] != 'All' or query['chart'] != 'none'):
        raise ValueError('Abnormality filters cannot filter production.')
    if query['chart'] == 'bar' and (group not in ('machine','date','shift','category') or 'reported_minutes' not in metrics):
        raise ValueError('Bar chart requires grouped reported minutes.')
    # Reuse the same strict parent-scope enforcement as the legacy tool.
    parent_query = {k:query[k] for k in SCOPE_FIELDS}
    parent_query.update(view='overview', metrics=['input_rolls'])
    return _query_scope(snapshot,parent_query)


def _presentation(rows, title, chart=None, warnings=()):
    total = len(rows)
    return dict(title=title, rows=rows[:MAX_TABLE_ROWS], total_rows=total,
                truncated=total > MAX_TABLE_ROWS, chart=chart, warnings=list(warnings))


def query_analysis(snapshot, query):
    """Return a transport-safe fact envelope and a separate LOCAL presentation.

    Tables, event IDs/times and chart rows never enter the model-result envelope.
    The model can choose among at most 20 group facts; the full table is independent.
    """
    scope = _analysis_scope(snapshot,query)
    domain, group, metrics = query['domain'], query['group_by'], query['metrics']
    context = f"{scope['start_date']} 至 {scope['end_date']} · {SHIFT_NAMES[scope['shift']]} · " + ('、'.join(scope['machines']) or '全部已记录设备')
    rows = _matching_rows(snapshot['rows'],scope)
    cov = _coverage(rows,scope,snapshot['available_machines'])
    chart, warnings = None, []
    if domain == 'production':
        key = {'machine':'machine_id','date':'production_date','shift':'shift'}.get(group)
        groups = {}
        for r in rows:
            label = SHIFT_NAMES[r[key]] if key == 'shift' else r[key] if key else '合计'
            groups.setdefault(label,[]).append(r)
        summaries = [(label,summarize(groups[label])) for label in sorted(groups, key=machine_sort if group=='machine' else None)]
        summary_text = '；'.join(_metric_text(summarize(rows),m) for m in metrics) if rows else '暂无生产记录，缺失不代表零。'
        coverage_text = cov['text']
        facts = [_fact(context+'：'+coverage_text), _fact(context+' · 合计：'+summary_text)]
        table = [{GROUP_LABELS[group]:label, **{METRIC_LABELS[m]:s[m] for m in metrics}} for label,s in summaries]
        for label,s in summaries[:20]:
            facts.append(_fact(context+f' · {label}：'+'；'.join(_metric_text(s,m) for m in metrics)))
    else:
        events = _matching_rows(snapshot.get('abnormalities',[]),scope)
        if query['categories']:
            events = [e for e in events if e['category'] in query['categories']]
        if query['status'] != 'All':
            events = [e for e in events if e['status'] == query['status']]
        coverage_text = abnormality.coverage(events)
        warnings.append(coverage_text)
        # Don't imply production coverage describes abnormality collection completeness.
        total = abnormality.summarize(events)
        def text(s):
            return '；'.join(METRIC_LABELS[m]+'：'+('不可用' if s[m] is None else f'{s[m]:g}') for m in metrics)
        facts = [_fact(context+'：'+coverage_text), _fact(context+' · 异常合计：'+text(total))]
        cov = dict(text=coverage_text, message=coverage_text)
        if group=='overview':
            summaries = [dict(label='合计',**total)] if events else []
        elif group=='details':
            summaries = []
        else:
            summaries = abnormality.grouped(events,group)
        if group == 'details':
            overlaps = abnormality.overlap_ids(events)
            table = []
            for e in events:
                interval = abnormality.interval_minutes(e)
                table.append({'事件ID':e['event_id'],'生产日期':e['production_date'],'设备':e['machine_id'],
                    '班次':abnormality.SHIFT_NAMES[e['shift']], '异常类别':e['category'], '子类别':e['subcategory'],
                    '开始时间':e['started_at'], '结束时间':e['ended_at'], '原报分钟':e['reported_minutes'],
                    '起止区间分钟':interval, '事件处理状态':abnormality.STATUS_NAMES[e['status']],
                    '时间重叠':e['event_id'] in overlaps,
                    '分钟不一致':interval is not None and e['reported_minutes'] is not None and abs(interval-e['reported_minutes'])>0.01})
        else:
            shown = list(dict.fromkeys(metrics+['event_count','valid_minutes_count','missing_minutes_count']))
            table = [{GROUP_LABELS[group]:s['label'], **{METRIC_LABELS[m]:s[m] for m in shown}} for s in summaries]
            for s in summaries[:20]:
                facts.append(_fact(context+f" · {s['label']}："+text(s)))
        if query['chart'] == 'bar':
            if len(summaries) > MAX_TABLE_ROWS:
                raise ValueError('Too many chart groups; narrow scope.')
            # Null groups remain in the table, with no invented zero bar.
            chart = dict(group=GROUP_LABELS[group], rows=[dict(label=s['label'],value=s['reported_minutes']) for s in summaries
                         if s['reported_minutes'] is not None], omitted_groups=sum(s['reported_minutes'] is None for s in summaries),
                         partial_groups=[dict(label=s['label'],missing_count=s['missing_minutes_count']) for s in summaries
                                         if s['reported_minutes'] is not None and s['missing_minutes_count']])
    # Avoid duplicate facts (overview's aggregate equals its sole group).
    facts = list({f['id']:f for f in facts}.values())
    if len(table)>20:
        facts.append(_fact(f'共有{len(table)}行本机结果表；摘要候选仅含合计和前20组，完整结果以本机表格为准。'))
    domain_label = '生产数据' if domain=='production' else '异常记录'
    filters = '' if domain=='production' else ' · 类别：'+('、'.join(query['categories']) or '全部')+' · 处理状态：'+({'All':'全部',**abnormality.STATUS_NAMES}[query['status']])
    title = context+' · '+domain_label+filters
    return dict(scope=scope,view='analysis',facts=facts,coverage=cov), _presentation(table,title,chart,warnings)


def legacy_presentation(snapshot,query):
    """Give legacy production questions the same complete local tables."""
    scope = _query_scope(snapshot,query)
    if query['view']=='changeovers':
        rows = _matching_rows(snapshot['rows'],scope)
        keys={(r['production_date'],r['machine_id'],r['shift']) for r in rows}
        events=[e for e in snapshot['changeovers'] if (e['production_date'],e['machine_id'],e['shift']) in keys]
        return _presentation([{'生产日期':e['production_date'],'设备':e['machine_id'],'班次':SHIFT_NAMES[e['shift']],
                               '原产品':e['from_product'],'新产品':e['to_product']} for e in events], '已确认换产记录')
    q = {k:query[k] for k in SCOPE_FIELDS}
    q.update(domain='production',group_by={'overview':'overview','comparison':'machine','daily':'date'}[query['view']],
             metrics=query['metrics'],categories=[],status='All',chart='none')
    return query_analysis(snapshot,q)[1]



def query_diagnostics(snapshot, query):
    """Bounded program facts plus a separate LOCAL evidence table/chart."""
    from production_diagnostics import analyze, presentation
    if not isinstance(query,dict) or set(query) != SCOPE_FIELDS | {'group_by','chart'}:
        raise ValueError('Invalid diagnostic fields.')
    parent={k:query[k] for k in SCOPE_FIELDS}
    scope=_query_scope(snapshot,dict(**parent,view='overview',metrics=['input_rolls']))
    rows=_matching_rows(snapshot['rows'],scope)
    events=_matching_rows(snapshot.get('abnormalities',[]),scope)
    changes=_matching_rows(snapshot.get('changeovers',[]),scope)
    local=_snapshot_parts(rows,changes,scope,snapshot['available_machines'])
    local['abnormalities']=events
    result=analyze(local,query['group_by'])
    shown=presentation(local,query['group_by'],query['chart'])
    s=result['summary'];a=s['abnormalities']
    def val(v):return '不可用' if v is None else f'{v:g}' if isinstance(v,(int,float)) else str(v)
    context=f"{scope['start_date']} 至 {scope['end_date']} · {SHIFT_NAMES[scope['shift']]} · "+('、'.join(scope['machines']) or '全部设备')
    facts=[_fact(context+'：'+' '.join(result['warnings'])),
           _fact(context+f"：生产记录{s['record_count']}条；计划投入{val(s['planned_rolls'])}母卷；实际投入{val(s['input_rolls'])}母卷；未达计划逐记录合计{val(s['input_shortfall'])}母卷；超额投入逐记录合计{val(s['input_excess'])}母卷；异常记录{a['event_count']}条；原报{val(a['reported_minutes'])}事件分钟。")]
    # No products, event IDs, timestamps, notes or full evidence rows leave this layer.
    for row in result['rows'][:20]:
        if query['group_by']=='category':
            text=f"{row['异常类别']}：{val(row['异常记录时长合计（分钟）'])}事件分钟，占已知分钟{row['已知事件分钟占比'] or '不可用'}；缺分钟{row['缺分钟记录数（条）']}条。"
        else:
            label=' · '.join(str(row[k]) for k in ('生产日期','设备','班次') if k in row)
            text=(label+f"：未达计划{val(row['未达计划（母卷，逐记录）'])}母卷，超额投入{val(row['超额投入（母卷，逐记录）'])}母卷；异常{row['异常记录数（条）']}条／{val(row['异常记录时长合计（分钟）'])}事件分钟。同期出现不能直接归因；记录不完整需复核。")
        facts.append(_fact(context+' · '+text))
    if len(result['rows'])>20:
        facts.append(_fact(f"本机共{len(result['rows'])}组；摘要候选仅前20组；表格最多前1000行，不等于全部异常或完整产量。"))
    return dict(scope=scope,view='analysis',facts=facts,coverage=dict(text=' '.join(result['warnings']),message=' '.join(result['warnings']))),shown
