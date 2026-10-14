"""Offline production Dashboard report; calculations shared with the web app."""
import argparse
import html
import sqlite3
from contextlib import closing
from pathlib import Path

from database import DB_PATH, get_connection
from production import get_records
from production_dashboard import (
    SHIFT_LABELS, aggregate_machines, coverage_text, detail_records, filter_records,
    percent, summarize,
)


def total(rows, key):
    return sum(row[key] for row in rows)


def chart(rows, fields, labels, unit):
    """Machine totals, with outside legends and room for long numerical labels."""
    maximum = max((row[field] for row in rows for field in fields), default=0) or 1
    height = 24 + max(len(rows), 1) * 72
    parts = [f'<svg viewBox="0 0 960 {height}" role="img" aria-label="{html.escape(" / ".join(labels))}">']
    colors = ('#94a3b8', '#2563a6')
    for index, row in enumerate(rows):
        y = 16 + index * 72
        parts.append(f'<text x="16" y="{y+26}">{html.escape(row["machine_id"])}</text>')
        for j, field in enumerate(fields):
            width = row[field] / maximum * 610
            value = f'{row[field]:,.1f}' if unit == 'm²' else f'{row[field]:,}'
            parts.append(f'<rect x="110" y="{y+j*27}" width="{width:.2f}" height="18" rx="3" fill="{colors[j]}"/>'
                         f'<text x="{122+width:.2f}" y="{y+j*27+14}">{value} {unit}</text>')
    parts.append('</svg>')
    legend = '<div class="legend">' + ''.join(
        f'<span><i style="background:{colors[i]}"></i>{html.escape(label)}（{unit}）</span>'
        for i, label in enumerate(labels)) + '</div>'
    return legend + ''.join(parts)


STYLE = '''body{font-family:system-ui,sans-serif;background:#f4f7fb;color:#19344f;margin:0;padding:24px}
main{max-width:1250px;margin:auto}h1{font-size:28px}h2{font-size:20px}p{line-height:1.7;color:#53677d}
section,article{background:white;border:1px solid #dce5ee;border-radius:10px;padding:20px;margin:16px 0}
.cards{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}.cards article{margin:0}.cards strong{display:block;font-size:clamp(20px,2.3vw,30px);overflow-wrap:anywhere;margin:10px 0;color:#204d79}
.legend{display:flex;flex-wrap:wrap;gap:12px 24px;margin:8px 0 20px;color:#53677d}.legend span{display:flex;align-items:center;gap:8px}.legend i{display:block;width:14px;height:14px;border-radius:2px}
svg{width:100%;height:auto}svg text{font:15px system-ui;fill:#19344f}.scroll{overflow-x:auto}table{border-collapse:collapse;white-space:nowrap;width:100%;font-size:13px}td,th{padding:12px;text-align:right;border-bottom:1px solid #dde6ee}th{background:#edf3f8}summary{cursor:pointer;font-weight:600}small{line-height:1.5;color:#53677d}
@media(max-width:850px){.cards{grid-template-columns:repeat(2,minmax(0,1fr))}body{padding:12px}}
@media print{details>*,details table{display:block}section,article{break-inside:avoid}}
'''


def chart_document(content):
    return f'<!doctype html><html lang="zh-CN"><meta charset="utf-8"><style>{STYLE}body{{padding:4px;background:white}}</style>{content}</html>'


def detail_table(rows):
    records = detail_records(rows)
    if not records:
        return '<p>暂无生产明细。</p>'
    heads = ''.join(f'<th>{html.escape(k)}</th>' for k in records[0])
    body = ''.join('<tr>' + ''.join(f'<td>{html.escape(str(v))}</td>' for v in r.values()) + '</tr>' for r in records)
    return f'<div class="scroll"><table><thead><tr>{heads}</tr></thead><tbody>{body}</tbody></table></div>'


def render_report(rows, day, shift=None, machine=None):
    rows = filter_records(rows, shift, machine)
    summary = summarize(rows)
    machines = aggregate_machines(rows)
    cards = [
        ('合格产出面积', f"{summary['qualified_output_m2']:,.1f} m²" if rows else '—', '合格成品的产出面积'),
        ('投入计划达成率', summary['attainment'], '投入卷数 ÷ 计划卷数'),
        ('面积合格率', summary['qualification'], '合格面积 ÷ 实际面积'),
        ('已记录设备数', f"{summary['machine_count']} 台", '按设备编号去重'),
    ]
    cards_html = ''.join(f'<article>{label}<strong>{value}</strong><small>{hint}</small></article>' for label,value,hint in cards)
    auxiliary = (f"计划投入 {summary['planned_rolls']:,} 卷 · 实际投入 {summary['input_rolls']:,} 卷 · "
                 f"合格成品 {summary['qualified_rolls']:,} 卷 · 实际产出 {summary['actual_output_m2']:,.1f} m²") if rows else '暂无数据'
    shift_summaries = ''
    if shift is None and rows:
        lines = []
        for recorded_shift in ('Day', 'Night'):
            subset = filter_records(rows, recorded_shift)
            if subset:
                s = summarize(subset)
                lines.append(f"{SHIFT_LABELS[recorded_shift]}：合格面积 {s['qualified_output_m2']:,.1f} m²，投入计划达成率 {s['attainment']}，面积合格率 {s['qualification']}")
        shift_summaries = '<p>' + '<br>'.join(lines) + '</p>'
    comparisons = (
        '<section><h2>计划投入与实际投入</h2>' + chart(machines, ('planned_rolls','input_rolls'), ('计划投入','实际投入'), '卷') + '</section>'
        '<section><h2>实际产出与合格产出</h2>' + chart(machines, ('actual_output_m2','qualified_output_m2'), ('实际产出','合格产出'), 'm²') + '</section>'
    ) if rows else '<section><p>当前日期、班次及设备范围暂无生产记录。</p></section>'
    return f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(day)} 生产 Dashboard</title><style>{STYLE}</style><main>
<h1>Production Data Viewer Agent · {html.escape(day)}</h1>
<p>{SHIFT_LABELS[shift]} · {html.escape(machine or '全部设备')} · {summary['record_count']} 条记录<br>{coverage_text(rows,shift)}</p>
<div class="cards">{cards_html}</div><p>{auxiliary}</p>{shift_summaries}{comparisons}
<section><details><summary>生产明细 · {len(rows)} 条记录</summary>{detail_table(rows)}</details></section>
</main></html>'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--date', required=True)
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
