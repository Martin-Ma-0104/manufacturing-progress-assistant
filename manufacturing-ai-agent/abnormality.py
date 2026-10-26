"""Reviewed abnormality events. Reported minutes are not net downtime."""
from datetime import date, datetime
import math
import re

FIELDS = ('event_id', 'production_date', 'shift', 'machine_id', 'category',
          'subcategory', 'started_at', 'ended_at', 'reported_minutes', 'status',
          'source_name', 'notes')
PUBLIC_FIELDS = FIELDS[:-2]
SCHEMA = '''CREATE TABLE IF NOT EXISTS abnormality_events (
    event_id TEXT PRIMARY KEY NOT NULL, production_date TEXT NOT NULL,
    shift TEXT CHECK(shift IN ('Day','Night') OR shift IS NULL),
    machine_id TEXT NOT NULL, category TEXT NOT NULL, subcategory TEXT NOT NULL,
    started_at TEXT, ended_at TEXT,
    reported_minutes REAL CHECK(reported_minutes >= 0 OR reported_minutes IS NULL),
    status TEXT NOT NULL CHECK(status IN ('Open','Closed','Unknown')),
    source_name TEXT NOT NULL, notes TEXT NOT NULL)'''
SHIFT_NAMES = {None: '班次未确认', 'Day': '白班', 'Night': '夜班'}
STATUS_NAMES = {'Open': '处理中', 'Closed': '已完成', 'Unknown': '状态未确认'}
CAUTION = '异常记录时长合计可能重叠，不代表实际净停机时长；跨设备合计为设备事件分钟合计，不是工厂经历时长。'


def _timestamp(value):
    if value is None:
        return None
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?', value):
        raise ValueError('Event times must be explicit local YYYY-MM-DDTHH:MM[:SS], or null.')
    return datetime.fromisoformat(value)


def validate(event):
    if not isinstance(event, dict) or set(event) != set(FIELDS):
        raise ValueError('Abnormality fields must match the documented format exactly.')
    day = event['production_date']
    if not isinstance(day, str) or date.fromisoformat(day).isoformat() != day:
        raise ValueError('Invalid abnormality production date.')
    if event['shift'] not in (None, 'Day', 'Night') or event['status'] not in STATUS_NAMES:
        raise ValueError('Invalid abnormality shift or event status.')
    for key, limit in [('event_id',128), ('machine_id',128), ('category',128),
                       ('subcategory',256), ('source_name',512), ('notes',4000)]:
        value = event[key]
        if not isinstance(value, str) or len(value) > limit or any(ord(c) < 32 and c not in '\n\t' for c in value):
            raise ValueError('Invalid abnormality text field: ' + key)
        if key not in ('subcategory', 'notes') and (not value or value.strip() != value or '\n' in value or '\t' in value):
            raise ValueError('Abnormality labels must be nonempty trimmed text.')
    start, end = _timestamp(event['started_at']), _timestamp(event['ended_at'])
    if start is not None and end is not None and end < start:
        raise ValueError('End precedes start; provide explicit cross-midnight dates, never inferred dates.')
    value = event['reported_minutes']
    if value is not None and (type(value) not in (int, float) or not math.isfinite(value) or value < 0):
        raise ValueError('Reported minutes must be finite and nonnegative, or null.')


def import_events(events, connection):
    """Participate in the caller's atomic transaction; never silently update IDs."""
    for event in events:
        validate(event)
    added = 0
    for event in events:
        values = tuple(event[k] for k in FIELDS)
        existing = connection.execute('SELECT '+','.join(FIELDS)+' FROM abnormality_events WHERE event_id=?',
                                      (event['event_id'],)).fetchone()
        if existing is not None:
            if tuple(existing) != values:
                raise ValueError('Conflicting abnormality event ID; batch rolled back. Review corrections separately.')
            continue
        connection.execute('INSERT INTO abnormality_events ('+','.join(FIELDS)+') VALUES ('+
                           ','.join('?' for _ in FIELDS)+')', values)
        added += 1
    return added


def interval_minutes(event):
    start, end = _timestamp(event['started_at']), _timestamp(event['ended_at'])
    return round((end-start).total_seconds()/60, 3) if start is not None and end is not None else None


def overlap_ids(events):
    """Mark participating events, including overlaps across dates/categories."""
    machines = {}
    for event in events:
        start, end = _timestamp(event['started_at']), _timestamp(event['ended_at'])
        if start is not None and end is not None and start < end:
            machines.setdefault(event['machine_id'], []).append((start, end, event['event_id']))
    result = set()
    for intervals in machines.values():
        furthest, furthest_id = None, None
        for start, end, event_id in sorted(intervals):
            if furthest is not None and start < furthest:
                result.update((event_id, furthest_id))
            if furthest is None or end > furthest:
                furthest, furthest_id = end, event_id
    return result


def summarize(events):
    valid = [e['reported_minutes'] for e in events if e['reported_minutes'] is not None]
    mismatches = sum(interval_minutes(e) is not None and e['reported_minutes'] is not None and
                     abs(interval_minutes(e)-e['reported_minutes']) > 0.01 for e in events)
    return dict(event_count=len(events), reported_minutes=sum(valid) if valid else None,
                valid_minutes_count=len(valid), missing_minutes_count=len(events)-len(valid),
                open_count=sum(e['status']=='Open' for e in events),
                unknown_status_count=sum(e['status']=='Unknown' for e in events),
                unknown_shift_count=sum(e['shift'] is None for e in events),
                incomplete_time_count=sum(e['started_at'] is None or e['ended_at'] is None for e in events),
                mismatch_count=mismatches, overlap_event_count=len(overlap_ids(events)))


def grouped(events, group_by):
    key = {'machine':'machine_id', 'date':'production_date', 'shift':'shift', 'category':'category'}.get(group_by)
    if key is None:
        raise ValueError('Unsupported abnormality grouping.')
    groups = {}
    for e in events:
        label = SHIFT_NAMES[e[key]] if key == 'shift' else e[key]
        groups.setdefault(label, []).append(e)
    from production_dashboard import machine_sort
    return [dict(label=label, **summarize(groups[label]))
            for label in sorted(groups, key=machine_sort if group_by == 'machine' else None)]


def coverage(events):
    s = summarize(events)
    if not events:
        return '所选范围暂无已录入异常记录；不代表没有异常或零停机。'
    return (f"已录入异常 {s['event_count']} 条，有原报分钟 {s['valid_minutes_count']} 条，"
            f"缺分钟 {s['missing_minutes_count']} 条；班次未确认 {s['unknown_shift_count']} 条，"
            f"起止不完整 {s['incomplete_time_count']} 条，原报与区间分钟不一致 {s['mismatch_count']} 条；"
            f"当前所选记录的已确认起止中参与重叠 {s['overlap_event_count']} 条，时间不完整记录无法核验重叠。" + CAUTION)
