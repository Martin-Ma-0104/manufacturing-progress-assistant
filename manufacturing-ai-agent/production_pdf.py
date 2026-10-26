"""Local PDF reports. Rendering is deferred until download; no database writes."""
from datetime import date, timedelta
from html import escape
from io import BytesIO
from pathlib import Path
from threading import Lock

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.graphics.shapes import Drawing, Line, Rect, Circle, String
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether

from production_dashboard import (SHIFT_LABELS, aggregate_machines, coverage_text,
                                  detail_records, filter_records, machine_sort, summarize)
from production_trends import METRICS

INK = colors.HexColor('#19344f')
BLUE = colors.HexColor('#2563a6')
GRAY = colors.HexColor('#64748b')
GREEN = colors.HexColor('#27896e')
ORANGE = colors.HexColor('#c47b15')
PURPLE = colors.HexColor('#7c3aed')
GRID = colors.HexColor('#dce5ee')
_FONT_LOCK = Lock()


def font_name():
    # Embed the installed macOS Unicode font; use ReportLab's CJK CID font elsewhere.
    with _FONT_LOCK:
        if 'ProductionUnicode' in pdfmetrics.getRegisteredFontNames():
            return 'ProductionUnicode'
        path = Path('/System/Library/Fonts/Supplemental/Arial Unicode.ttf')
        if path.is_file():
            pdfmetrics.registerFont(TTFont('ProductionUnicode', str(path)))
            return 'ProductionUnicode'
        if 'STSong-Light' not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))
        return 'STSong-Light'


def paragraph(text, size=9, color=INK):
    style = ParagraphStyle('report', fontName=font_name(), fontSize=size,
                           leading=size * 1.5, textColor=color, wordWrap='CJK',
                           spaceAfter=5, splitLongWords=True)
    return Paragraph(escape(str(text)).replace('\n', '<br/>'), style)


def table(headers, rows, widths):
    data = [[paragraph(x, 7.5) for x in headers]]
    data += [[paragraph(x, 7.5) for x in row] for row in rows]
    result = Table(data, colWidths=widths, repeatRows=1, hAlign='LEFT')
    result.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#eaf0f7')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LINEBELOW', (0, 0), (-1, -1), .4, GRID),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    return result


def build(story, title, pagesize):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=pagesize, leftMargin=36, rightMargin=36,
                            topMargin=36, bottomMargin=36, title=title,
                            author='Production Data Viewer Agent', pageCompression=1)
    def footer(canvas, document):
        canvas.setFont(font_name(), 8)
        canvas.setFillColor(GRAY)
        canvas.drawString(36, 20, 'Production Data Viewer Agent')
        canvas.drawRightString(pagesize[0]-36, 20, f'{document.page}')
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()


def text(drawing, x, y, value, size=8, color=INK, anchor='start'):
    drawing.add(String(x, y, str(value), fontName=font_name(), fontSize=size,
                       fillColor=color, textAnchor=anchor))


def comparison(devices, fields, labels, unit, width, maximum=None):
    height = 36 + 17 * len(devices)
    drawing = Drawing(width, height)
    for i, (label, color) in enumerate(zip(labels, (GRAY, BLUE))):
        drawing.add(Rect(52 + i*200, height-10, 10, 6, fillColor=color, strokeColor=None))
        text(drawing, 68+i*200, height-10, f'{label} ({unit})')
    maximum = maximum or max((r[f] for r in devices for f in fields), default=0) or 1
    span = width - 190
    for i, row in enumerate(devices):
        y = height - 32 - i*17
        text(drawing, 0, y, row['machine_id'], 9)
        for j, (field, color) in enumerate(zip(fields, (GRAY, BLUE))):
            length = row[field]/maximum*span
            drawing.add(Rect(52, y+5-j*9, length, 6, fillColor=color, strokeColor=None))
            text(drawing, 58+length, y+4-j*9, f'{row[field]:,.1f}' if unit=='m²' else f'{row[field]:,.0f}', 7)
    return drawing


def render_daily_pdf(rows, day, shift=None, machine=None):
    date.fromisoformat(day)
    rows = filter_records(rows, shift, machine)
    summary = summarize(rows)
    width = landscape(A4)[0]-84
    story = [paragraph('Production Data Viewer Agent', 18),
             paragraph(f'生产日报 | {day} | {SHIFT_LABELS[shift]} | {machine or "全部设备"}', 12),
             paragraph(coverage_text(rows, shift), 8, GRAY), Spacer(1, 6)]
    metrics = [f'{summary["qualified_output_m2"]:,.1f} m²' if rows else '—',
               summary['attainment'], summary['qualification'], f'{summary["machine_count"]} 台']
    story += [table(['合格产出面积','投入计划达成率','面积合格率','已记录设备数'], [metrics], [width/4]*4),
              paragraph('投入计划达成率 = 投入卷数合计 / 计划卷数合计；面积合格率 = 合格面积合计 / 实际面积合计。', 8, GRAY)]
    if rows:
        story.append(paragraph(f'计划投入 {summary["planned_rolls"]:,} 卷 | 实际投入 {summary["input_rolls"]:,} 卷 | 合格成品 {summary["qualified_rolls"]:,} 卷 | 实际产出 {summary["actual_output_m2"]:,.1f} m²', 9))
        devices = aggregate_machines(rows)
        for fields, labels, unit in [(('planned_rolls','input_rolls'),('计划投入','实际投入'),'卷'),
                                      (('actual_output_m2','qualified_output_m2'),('实际产出','合格产出'),'m²')]:
            maximum = max((r[f] for r in devices for f in fields), default=0) or 1
            for offset in range(0,len(devices),12):
                story.append(KeepTogether([paragraph(' / '.join(labels),11), comparison(devices[offset:offset+12], fields, labels, unit, width, maximum)]))
        story += [PageBreak(), paragraph(f'生产明细 | {day} | {SHIFT_LABELS[shift]} | {machine or "全部设备"}', 13)]
        # Keep every original indicator, including per-record reported yield.
        headers = ['设备','班次','产品','计划\n卷','投入\n卷','合格\n卷','实际面积\nm²','合格面积\nm²','达成率','合格率','原报表\n综收']
        data = [[r['设备'],r['班次'],r['产品'],r['计划投入（卷）'],r['实际投入（卷）'],r['合格成品（卷）'],
                 f'{r["实际产出（m²）"]:,.1f}', f'{r["合格产出（m²）"]:,.1f}',r['投入计划达成率'],r['面积合格率'],r['原报表综收']] for r in detail_records(rows)]
        widths = [38,34,160,38,38,38,84,84,51,51,53]
        widths = [w*width/sum(widths) for w in widths]
        story += [table(headers, data, widths), Spacer(1,8),
                  paragraph('综收保留原报表值，不推导汇总综收；— 表示不可用。未计入合格产出的面积不直接认定为废料。',8,GRAY)]
    else:
        story.append(paragraph('当前范围暂无生产记录；缺失记录不代表零产量。'))
    return build(story, f'{day} 生产日报', landscape(A4))


def trend_drawing(rows, dates, field, unit, maximum, compare_plan, shift, width, *, show_changeovers=False):
    """Confirmed markers are always visible; retain the legacy keyword for callers."""
    drawing = Drawing(width, 215)
    left, right, bottom, top = 55, width-25, 36, 175
    for tick in range(5):
        y = bottom + (top-bottom)*tick/4
        drawing.add(Line(left,y,right,y,strokeColor=GRID,strokeWidth=.5))
        text(drawing,left-6,y-2,f'{maximum*tick/4:,.0f}',7,GRAY,'end')
    if compare_plan:
        drawing.add(Line(left,201,left+24,201,strokeColor=BLUE,strokeWidth=1.5))
        text(drawing,left+30,198,'实际投入',8)
        drawing.add(Line(left+135,201,left+159,201,strokeColor=GRAY,strokeWidth=1.5,strokeDashArray=[5,3]))
        text(drawing,left+165,198,'计划投入（标准线）',8)
    points = {r['production_date']:r for r in rows}
    previous = previous_plan = None
    for i, day in enumerate(dates):
        x = left + (right-left)*i/(len(dates)-1)
        if len(dates)==7 or i%5==0 or i==len(dates)-1:
            text(drawing,x,18,day[5:],7,GRAY,'middle')
        row = points.get(day)
        if row is None:
            # Keep the previous observation without inventing a missing-date value.
            continue
        y = bottom + row[field]/maximum*(top-bottom)
        if previous:
            drawing.add(Line(*previous,x,y,strokeColor=BLUE,strokeWidth=1.5))
        if compare_plan:
            py = bottom + row['planned_rolls']/maximum*(top-bottom)
            if previous_plan:
                drawing.add(Line(*previous_plan,x,py,strokeColor=GRAY,strokeWidth=1.5,strokeDashArray=[5,3]))
            drawing.add(Circle(x,py,2.5,fillColor=colors.white,strokeColor=GRAY))
            previous_plan = (x,py)
        incomplete = shift is None and row['shift_count']<2
        drawing.add(Circle(x,y,3,fillColor=ORANGE if incomplete else BLUE,strokeColor=None))
        if row.get('changeover'):
            drawing.add(Line(x,bottom,x,top+9,strokeColor=PURPLE,strokeDashArray=[3,3]))
            text(drawing,x,top+13,'换产',7,PURPLE,'end' if i==len(dates)-1 else 'start')
            drawing.add(Circle(x,y,6,fillColor=None,strokeColor=PURPLE,strokeWidth=1.25))
        previous = (x,y)
    text(drawing,left,1,f'单位：{unit} | 横轴：生产日期',7,GRAY)
    return drawing


def render_trend_pdf(rows, end_date, days, metric='合格产出面积', shift=None, machine=None, *, show_changeovers=False):
    """Always mark confirmed events; the legacy flag controls only detail paragraphs."""
    if days not in (7,30) or shift not in SHIFT_LABELS:
        raise ValueError('Unsupported period or shift.')
    field, unit = METRICS[metric]
    end = date.fromisoformat(end_date)
    dates = [(end-timedelta(days=days-1-i)).isoformat() for i in range(days)]
    # Apply the filter even when called independently from the Dashboard.
    rows = [r for r in rows if dates[0]<=r['production_date']<=end_date and (machine is None or r['machine_id']==machine)]
    names = sorted({r['machine_id'] for r in rows}, key=machine_sort)
    compare_plan = field=='input_rolls'
    fields = (field,'planned_rolls') if compare_plan else (field,)
    maximum = (max((r[f] for r in rows for f in fields),default=0) or 1)*1.1
    width = A4[0]-84
    gap_note = '按已有记录日期连线，未记录日期不补数据。'
    changeover_note = '紫色标记：已确认换产。'
    story = []
    for index, name in enumerate(names):
        if index: story.append(PageBreak())
        data = sorted([r for r in rows if r['machine_id']==name],key=lambda r:r['production_date'])
        story += [paragraph('Production Data Viewer Agent',16),
                  paragraph(f'{name} | 最近 {days} 天趋势 | {metric}',13),
                  paragraph(f'{dates[0]} 至 {end_date} | {SHIFT_LABELS[shift]} | 有记录 {len(data)} 天 / {days} 天',9),
                  paragraph(gap_note+'橙色点：仅一个班次记录。'+changeover_note,8,GRAY)]
        if len(data)==1:
            story.append(paragraph('目前只有一个日期的数据点，积累更多日期后显示趋势。',8,GRAY))
        story.append(trend_drawing(data,dates,field,unit,maximum,compare_plan,shift,width,show_changeovers=show_changeovers))
        for r in data:
            if show_changeovers and r.get('changeover'):
                story.append(paragraph(f'{r["production_date"]} | {r["changeover"]}',8,PURPLE))
        headers = ['日期',f'{"实际投入" if compare_plan else metric} ({unit})']
        if compare_plan: headers.append('计划投入 (卷)')
        headers.append('已记录班次数')
        values = [[r['production_date'],f'{r[field]:,.1f}']+([f'{r["planned_rolls"]:,.0f}'] if compare_plan else [])+[str(r['shift_count'])] for r in data]
        story += [Spacer(1,6),table(headers,values,[width/len(headers)]*len(headers))]
    if not names:
        story = [paragraph('Production Data Viewer Agent',16),paragraph(f'{dates[0]} 至 {end_date} | {SHIFT_LABELS[shift]} | {machine or "全部设备"} | {metric}'),paragraph('所选范围暂无生产记录；缺失记录不代表零产量。')]
    return build(story,f'{end_date} 最近{days}天趋势',A4)
