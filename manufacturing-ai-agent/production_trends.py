"""Daily machine aggregates and offline SVG trend reports (standard library)."""
from datetime import date, timedelta
from html import escape

METRICS = {
    '合格产出面积': ('qualified_output_m2', 'm²'),
    '实际产出面积': ('actual_output_m2', 'm²'),
    '投入卷数（实际 / 计划）': ('input_rolls', '卷'),
    '合格成品卷数': ('qualified_rolls', '卷'),
}


def get_trend_data(connection, end_date, days, shift=None):
    if days not in (7, 30) or shift not in (None, 'Day', 'Night'):
        raise ValueError('Unsupported period or shift.')
    end = date.fromisoformat(end_date)
    start = end - timedelta(days=days - 1)
    conditions = 'production_date BETWEEN ? AND ?'
    parameters = [start.isoformat(), end.isoformat()]
    if shift:
        conditions += ' AND shift = ?'
        parameters.append(shift)
    cursor = connection.execute(f'''
        SELECT production_date, machine_id,
               SUM(qualified_output_m2) AS qualified_output_m2,
               SUM(actual_output_m2) AS actual_output_m2,
               SUM(input_rolls) AS input_rolls,
               SUM(planned_rolls) AS planned_rolls,
               SUM(qualified_rolls) AS qualified_rolls,
               COUNT(DISTINCT shift) AS shift_count
        FROM slitting_records WHERE {conditions}
        GROUP BY production_date, machine_id ORDER BY machine_id, production_date
    ''', parameters)
    fields = [item[0] for item in cursor.description]
    result = [dict(zip(fields, row)) for row in cursor.fetchall()]
    # Product codes alone do not establish a real machine changeover.
    # Only explicitly confirmed, shift-specific events appear on the chart.
    changes = {}
    has_events = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='changeover_events'"
    ).fetchone()
    if has_events:
        event_sql = (
            "SELECT production_date, machine_id, shift, from_product, to_product "
            "FROM changeover_events WHERE production_date BETWEEN ? AND ?"
        )
        event_params = [start.isoformat(), end.isoformat()]
        if shift:
            event_sql += " AND shift = ?"
            event_params.append(shift)
        event_sql += " ORDER BY production_date, machine_id, shift"
        for event_day, machine_id, event_shift, old, new in connection.execute(event_sql, event_params):
            shift_name = '白班' if event_shift == 'Day' else '夜班'
            changes.setdefault((machine_id, event_day), []).append(
                f"已确认换产（{shift_name}）：{old} → {new}"
            )
    for row in result:
        events = changes.get((row['machine_id'], row['production_date']), [])
        row['changeover'] = '；'.join(events) if events else None
    return result


def render_trends(rows, end_date, days, metric='合格产出面积', shift=None, machine=None, *, show_changeovers=False):
    """Always mark confirmed events; the legacy flag controls only their detail list."""
    field, unit = METRICS[metric]
    compare_plan = metric == '投入卷数（实际 / 计划）'
    end = date.fromisoformat(end_date)
    dates = [(end - timedelta(days=days - 1 - i)).isoformat() for i in range(days)]
    rows = [r for r in rows if machine is None or r['machine_id'] == machine]
    machines = sorted({r['machine_id'] for r in rows})
    scale_fields = (field, 'planned_rolls') if compare_plan else (field,)
    maximum = max((r[f] for r in rows for f in scale_fields), default=0) or 1
    # Share the Y scale across machines for a fair visual comparison.
    maximum *= 1.1
    sections = []
    for name in machines:
        points = {r['production_date']: r for r in rows if r['machine_id'] == name}
        svg = [f'<svg viewBox="0 0 960 335" role="img" aria-label="{escape(name)} {escape(metric)}趋势">']
        for tick in range(5):
            y = 230 - tick * 48
            value = maximum * tick / 4
            svg.append(f'<line x1="85" x2="925" y1="{y}" y2="{y}" stroke="#e2e8f0"/>'
                       f'<text x="77" y="{y+4}" text-anchor="end">{value:,.0f}</text>')
        legend_html = (
            '<div class="legend" aria-label="图例">'
            '<span><i class="actual-swatch"></i>实际投入</span>'
            '<span><i class="plan-swatch"></i>计划投入（标准线）</span>'
            '</div>' if compare_plan else ''
        )
        data_labels = []
        previous = None
        previous_plan = None
        for index, day in enumerate(dates):
            x = 85 + index * 840 / (days - 1)
            if days == 7 or index % 5 == 0 or index == days - 1:
                svg.append(f'<text x="{x}" y="280" text-anchor="middle">{day[5:]}</text>')
            row = points.get(day)
            if row is None:
                # Missing dates have no points; connect the existing observations.
                continue
            label_anchor = 'end' if index == days - 1 else ('start' if index == 0 else 'middle')
            show_label = days == 7 or len(points) == 1
            value = row[field]
            y = 230 - value / maximum * 192
            if previous:
                svg.append(f'<line x1="{previous[0]}" y1="{previous[1]}" x2="{x}" y2="{y}" stroke="#2563a6" stroke-width="2.5"/>')
            if compare_plan:
                planned = row['planned_rolls']
                plan_y = 230 - planned / maximum * 192
                if previous_plan is not None:
                    svg.append(f'<line class="planned-line" x1="{previous_plan[0]}" y1="{previous_plan[1]}" x2="{x}" y2="{plan_y}" stroke="#64748b" stroke-width="2.5" stroke-dasharray="7 5"/>')
                svg.append(f'<circle cx="{x}" cy="{plan_y}" r="4" fill="white" stroke="#64748b"><title>{day} · 计划投入 {planned:,.0f} 卷</title></circle>')
                if show_label:
                    plan_label_y = plan_y + 24 if value > planned else plan_y - 14
                    data_labels.append(f'<text class="point-label plan-label" x="{x}" y="{plan_label_y}" text-anchor="{label_anchor}" style="fill:#64748b">计划 {planned:,.0f}</text>')
                previous_plan = (x, plan_y)
            incomplete = shift is None and row['shift_count'] < 2
            color = '#c47b15' if incomplete else '#2563a6'
            series_name = '实际投入 ' if compare_plan else ''
            tip = f'{day} · {series_name}{value:,.1f} {unit}' + (' · 仅有一个班次记录' if incomplete else '')
            svg.append(f'<circle cx="{x}" cy="{y}" r="5" fill="{color}"><title>{escape(tip)}</title></circle>')
            if show_label:
                label_y = (y - 14 if value > planned else y + 24) if compare_plan else y - 14
                value_label = f'实际 {value:,.0f}' if compare_plan else f'{value:,.1f}'
                label_class = 'point-label actual-label' if compare_plan else 'point-label'
                label_style = ' style="fill:#2563a6"' if compare_plan else ''
                data_labels.append(f'<text class="{label_class}" x="{x}" y="{label_y}" text-anchor="{label_anchor}"{label_style}>{value_label}</text>')
            changeover = row.get('changeover')
            if changeover:
                # Keep an independent marker so shift-coverage colors remain visible.
                anchor = 'end' if index == days - 1 else 'start'
                label_x = x - 8 if index == days - 1 else x + 8
                svg.append(f'<line x1="{x}" x2="{x}" y1="30" y2="230" stroke="#7c3aed" stroke-dasharray="4 4"/>'
                           f'<text x="{label_x}" y="22" text-anchor="{anchor}" style="fill:#7c3aed;font-weight:bold">换产<title>{escape(changeover)}</title></text>'
                           f'<circle cx="{x}" cy="{y}" r="9" fill="none" stroke="#7c3aed" stroke-width="2"><title>{escape(changeover)}</title></circle>')
            previous = (x, y)
        svg.extend(data_labels)
        svg.append(f'<text x="85" y="318">单位：{unit} · 横轴：生产日期</text></svg>')
        hint = '目前只有 1 个日期的数据点，积累更多日期后显示趋势。' if len(points) == 1 else f'有记录 {len(points)} 天 / {days} 天'
        plan_heading = '<th>计划投入（卷）</th>' if compare_plan else ''
        metric_heading = '实际投入' if compare_plan else metric
        details = ''.join(
            f'<tr><td>{d}</td><td>{r[field]:,.1f}</td>'
            + (f'<td>{r["planned_rolls"]:,.0f}</td>' if compare_plan else '')
            + f'<td>{r["shift_count"]}</td></tr>'
            for d, r in sorted(points.items())
        )
        events = ''.join(f'<li><b>{d}</b> · {escape(r["changeover"])}</li>'
                         for d, r in sorted(points.items()) if show_changeovers and r.get('changeover'))
        event_html = f'<div class="changes"><ul>{events}</ul></div>' if events else ''
        sections.append(f'<section><h2>{escape(name)}</h2><p>{hint}</p>{legend_html}{"".join(svg)}{event_html}'
                        f'<details><summary>查看数据点</summary><table><tr><th>日期</th><th>{escape(metric_heading)}（{unit}）</th>{plan_heading}<th>已记录班次数</th></tr>{details}</table></details></section>')
    label = {None: '全部班次', 'Day': '白班', 'Night': '夜班'}[shift]
    gap_note = '按已有记录日期连线，未记录日期不补数据。'
    changeover_note = '紫色“换产”标记表示已确认的换产事件，仍按设备汇总；产品代码不同不会自动判定为换产。'
    return f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>分切机趋势 · {days} 天</title><style>
body{{font-family:system-ui,sans-serif;background:#f4f7fb;color:#173042;padding:24px;margin:0}}main{{max-width:1250px;margin:auto}}section{{background:white;border:1px solid #dbe5ed;border-radius:12px;padding:24px;margin:20px 0}}svg{{width:100%;height:auto}}.legend{{display:flex;flex-wrap:wrap;gap:12px 28px;margin:12px 0 20px;color:#536777}}.legend span{{display:flex;align-items:center;gap:10px}}.legend i{{display:inline-block;width:32px;flex-shrink:0}}.actual-swatch{{border-top:3px solid #2563a6}}.plan-swatch{{border-top:3px dashed #64748b}}svg text{{font:13px system-ui;fill:#536777}}svg .point-label{{paint-order:stroke;stroke:white;stroke-width:5px;stroke-linejoin:round}}p{{line-height:1.7;color:#536777}}table{{border-collapse:collapse}}td,th{{padding:10px;border-bottom:1px solid #ddd}}summary{{cursor:pointer}}.changes{{border-left:3px solid #7c3aed;padding:4px 12px;background:#f5f0ff}}.changes li{{line-height:1.7;overflow-wrap:anywhere}}
</style><main><h1>分切机 · 最近 {days} 天趋势</h1><p>{dates[0]} 至 {dates[-1]} · {label} · {escape(metric)}</p>
<p>每个数据点汇总同一设备当天已记录的产品与所选班次。{gap_note}橙色点表示“全部班次”下仅有一个班次记录，不代表完整两班产量。{changeover_note}</p>
{''.join(sections) if sections else '<p>所选范围暂无生产记录。</p>'}</main></html>'''
