"""Generate a standalone, offline HTML report from daily SQLite records."""
import argparse
import html
import sqlite3
from contextlib import closing
from pathlib import Path

from database import DB_PATH, get_connection
from production import get_records


def percent(numerator, denominator):
    return f'{numerator / denominator * 100:.1f}%' if denominator else '—'


def total(rows, key):
    return sum(row[key] for row in rows)


def chart(rows, fields, labels, unit):
    """Grouped horizontal SVG bars; counts and areas always use separate scales."""
    maximum = max((row[field] for row in rows for field in fields), default=0) or 1
    height = 45 + len(rows) * 66
    parts = [f'<svg viewBox="0 0 960 {height}" role="img" aria-label="{html.escape(" / ".join(labels))}">']
    colors = ('#9caec2', '#007f86')
    for i, label in enumerate(labels):
        parts.append(f'<rect x="{180 + i * 310}" y="5" width="12" height="12" fill="{colors[i]}"/>'
                     f'<text x="{200 + i * 310}" y="16">{html.escape(label)} ({unit})</text>')
    for index, row in enumerate(rows):
        y = 42 + index * 66
        name = f"{row['machine_id']} · {'白班' if row['shift'] == 'Day' else '夜班'}"
        parts.append(f'<text x="10" y="{y + 20}">{html.escape(name)}</text>')
        for j, field in enumerate(fields):
            width = row[field] / maximum * 590
            value = f'{row[field]:,.1f}' if unit == 'm²' else f'{row[field]:,}'
            parts.append(f'<rect x="180" y="{y + j * 24}" width="{width:.2f}" height="18" rx="3" fill="{colors[j]}"/>'
                         f'<text x="{190 + width:.2f}" y="{y + j * 24 + 14}">{value}</text>')
    return ''.join(parts) + '</svg>'


def render_report(rows, day, shift=None):
    if shift not in (None, 'Day', 'Night'):
        raise ValueError('Unknown shift.')
    if shift is not None:
        rows = [row for row in rows if row['shift'] == shift]
    shift_label = {None: '白班 / 夜班', 'Day': '白班', 'Night': '夜班'}[shift]
    groups = [(shift_label, rows)] if shift else [
        ('全天', rows), ('白班', [r for r in rows if r['shift'] == 'Day']),
        ('夜班', [r for r in rows if r['shift'] == 'Night'])]
    cards = []
    for label, subset in groups:
        if not subset:
            continue
        p, i, q, a, qa = (total(subset, field) for field in (
            'planned_rolls', 'input_rolls', 'qualified_rolls', 'actual_output_m2', 'qualified_output_m2'))
        cards.append(f'<article><h2>{label}</h2><strong>{qa:,.1f} m²</strong><p>合格产出</p>'
                     f'<p>计划 {p} 卷 · 投入 {i} 卷 · 合格成品 {q} 卷</p>'
                     f'<p>实际产出 {a:,.1f} m²</p><p>投入计划达成率 <b>{percent(i, p)}</b>'
                     f' · 面积合格率 <b>{percent(qa, a)}</b></p></article>')
    body = []
    for row in rows:
        values = [row['machine_id'], '白班' if row['shift'] == 'Day' else '夜班', row['product'],
                  row['planned_rolls'], row['input_rolls'], row['qualified_rolls'],
                  f"{row['actual_output_m2']:,.1f}", f"{row['qualified_output_m2']:,.1f}",
                  percent(row['input_rolls'], row['planned_rolls']),
                  percent(row['qualified_output_m2'], row['actual_output_m2']),
                  '—' if row['reported_yield_pct'] is None else f"{row['reported_yield_pct']:.1f}%"]
        body.append('<tr>' + ''.join(f'<td>{html.escape(str(v))}</td>' for v in values) + '</tr>')
    headings = ['设备', '班次', '产品', '计划卷', '投入卷', '合格卷', '实际 m²', '合格 m²', '投入达成率', '面积合格率', '原报表综收']
    return f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{html.escape(day)} 分切生产日报</title>
<style>body{{font-family:system-ui,sans-serif;background:#f1f5f9;color:#173042;margin:0;padding:32px}}
main{{max-width:1250px;margin:auto}}h1{{font-size:32px}}.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px}}
article,section{{background:white;border:1px solid #dde6ee;border-radius:12px;padding:22px;margin:18px 0}}strong{{font-size:30px;color:#007f86}}p,li{{line-height:1.7}}svg{{width:100%;height:auto}}svg text{{font:14px system-ui,sans-serif;fill:#173042}}
.scroll{{overflow-x:auto}}table{{border-collapse:collapse;white-space:nowrap;width:100%;font-size:13px}}td,th{{padding:12px;text-align:right;border-bottom:1px solid #dde6ee}}th{{background:#edf4f6}}.note{{color:#536777}}@media print{{body{{padding:0}}section,article{{break-inside:avoid}}}}</style>
<main><p class="note">MANUFACTURING · DAILY PRODUCTION</p><h1>{html.escape(day)} · 分切生产日报</h1>
<p>{shift_label} · 来自本地 SQLite · {len(rows)} 条机器／班次／产品记录</p>
<div class="cards">{''.join(cards)}</div>
<section><h2>计划与实际投入</h2><p class="note">比较相同口径的投入卷数，避免将母卷与成品卷直接比较。</p>{chart(rows, ('planned_rolls','input_rolls'), ('计划投入','实际投入'), '卷')}</section>
<section><h2>实际产出与合格产出</h2><p class="note">两项均为面积（m²）；条形差值仅表示未计入合格产出的面积，不直接认定为废料。</p>{chart(rows, ('actual_output_m2','qualified_output_m2'), ('实际产出','合格产出'), 'm²')}</section>
<section><h2>生产明细</h2><div class="scroll"><table><thead><tr>{''.join(f'<th>{h}</th>' for h in headings)}</tr></thead><tbody>{''.join(body)}</tbody></table></div></section>
</main></html>'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--date', required=True, help='Production date YYYY-MM-DD')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if not DB_PATH.is_file():
        parser.exit(1, 'Database not initialized. Run python3 init_db.py first.\n')
    try:
        with closing(get_connection()) as connection:
            rows = get_records(connection, args.date)
        if not rows:
            raise ValueError('No production records for this date.')
        output = args.output or Path(__file__).resolve().parent / 'reports' / f'slitting-{args.date}.html'
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(render_report(rows, args.date), encoding='utf-8')
        print(f'Report created: {output.resolve()}')
    except (ValueError, OSError, sqlite3.Error) as error:
        parser.exit(1, f'Report failed: {error}\n')


if __name__ == '__main__':
    main()
