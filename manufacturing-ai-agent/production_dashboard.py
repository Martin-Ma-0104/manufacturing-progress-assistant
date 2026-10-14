"""Shared, read-only production aggregates used by the web page and HTML report."""
import re

FIELDS = ('planned_rolls', 'input_rolls', 'qualified_rolls',
          'actual_output_m2', 'qualified_output_m2')
SHIFT_LABELS = {None: '全部班次', 'Day': '白班', 'Night': '夜班'}


def percent(numerator, denominator):
    return f'{numerator / denominator * 100:.1f}%' if denominator else '—'


def machine_sort(machine):
    return [int(part) if part.isdigit() else part for part in re.split(r'(\d+)', machine)]


def filter_records(rows, shift=None, machine=None):
    if shift not in SHIFT_LABELS:
        raise ValueError('Unknown shift.')
    return [r for r in rows if (shift is None or r['shift'] == shift)
            and (machine is None or r['machine_id'] == machine)]


def summarize(rows):
    result = {field: sum(r[field] for r in rows) for field in FIELDS}
    result['machine_count'] = len({r['machine_id'] for r in rows})
    result['record_count'] = len(rows)
    result['attainment'] = percent(result['input_rolls'], result['planned_rolls'])
    result['qualification'] = percent(result['qualified_output_m2'], result['actual_output_m2'])
    return result


def aggregate_machines(rows):
    return [dict(machine_id=machine, **summarize([r for r in rows if r['machine_id'] == machine]))
            for machine in sorted({r['machine_id'] for r in rows}, key=machine_sort)]


def coverage_text(rows, shift=None):
    day = {r['machine_id'] for r in rows if r['shift'] == 'Day'}
    night = {r['machine_id'] for r in rows if r['shift'] == 'Night'}
    if not rows:
        return '当前范围暂无生产记录；缺失记录不代表零产量。'
    if shift is not None:
        selected = day if shift == 'Day' else night
        return f'{SHIFT_LABELS[shift]}有记录 {len(selected)} 台；未记录设备的状态未知。'
    return (f'白班有记录 {len(day)} 台 · 夜班有记录 {len(night)} 台 · '
            f'两班均有记录 {len(day & night)} 台。记录覆盖不代表全厂数据完整。')


def detail_records(rows):
    return [{
        '设备': r['machine_id'], '产品': r['product'], '班次': SHIFT_LABELS[r['shift']],
        '计划投入（卷）': r['planned_rolls'], '实际投入（卷）': r['input_rolls'],
        '合格成品（卷）': r['qualified_rolls'], '实际产出（m²）': r['actual_output_m2'],
        '合格产出（m²）': r['qualified_output_m2'],
        '投入计划达成率': percent(r['input_rolls'], r['planned_rolls']),
        '面积合格率': percent(r['qualified_output_m2'], r['actual_output_m2']),
        '原报表综收': '—' if r['reported_yield_pct'] is None else f"{r['reported_yield_pct']:.1f}%",
    } for r in rows]
