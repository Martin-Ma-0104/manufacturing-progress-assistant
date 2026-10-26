import math
import streamlit as st

from database import get_connection


def get_order(order_id):
    connection = get_connection()

    cursor = connection.execute(
        """
        SELECT order_id, product, quantity, due_date, priority
        FROM orders
        WHERE order_id = ?
        """,
        (order_id,)
    )

    order = cursor.fetchone()
    connection.close()

    return order


def get_material_requirements(product, order_quantity):
    connection = get_connection()

    cursor = connection.execute(
        """
        SELECT
            bom.material_id,
            inventory.material_name,
            bom.qty_per_unit,
            inventory.current_stock,
            inventory.safety_stock
        FROM bom
        JOIN inventory
            ON bom.material_id = inventory.material_id
        WHERE bom.product = ?
        """,
        (product,)
    )

    rows = cursor.fetchall()
    connection.close()

    results = []

    for row in rows:
        material_id = row[0]
        material_name = row[1]
        qty_per_unit = row[2]
        current_stock = row[3]
        safety_stock = row[4]

        required = math.ceil(
            order_quantity * qty_per_unit
        )

        available = max(
            current_stock - safety_stock,
            0
        )

        shortage = max(
            required - available,
            0
        )

        results.append(
            {
                "material_id": material_id,
                "material_name": material_name,
                "required": required,
                "available": available,
                "shortage": shortage,
            }
        )

    return results


st.set_page_config(
    page_title="Production Data Viewer Agent",
    page_icon="🏭",
    layout="wide"
)


st.html("""<style>
[data-testid="stMainBlockContainer"]{padding-top:4.5rem}
.app-header{padding:0 0 10px;margin:0 0 4px;border-bottom:1px solid #dce5ee}
.app-header h1{font-size:26px;line-height:1.25;font-weight:650;margin:0 0 4px;color:#19344f;overflow-wrap:anywhere}
.app-header p{font-size:13px;line-height:1.4;margin:0;color:#53677d}
</style><header class="app-header">
<h1>Production Data Viewer Agent</h1>
<p>Daily Production Reports and Machine Trends</p>
</header>""")

from ai_floating_panel import PAGES, migrate_legacy_page, render_floating_assistant

migrate_legacy_page()
page = st.sidebar.radio("功能", list(PAGES),
                        key="page", bind="query-params")

# This must precede every business branch, including its early st.stop().
render_floating_assistant(page)

if page == "生产分析":
    from production_diagnostics_ui import render_diagnostics
    render_diagnostics()
    st.stop()

if page == "数据导入":
    from cloud_import_ui import render_import
    render_import()
    st.stop()

if page == "分切生产日报":
    from contextlib import closing
    from datetime import date
    import sqlite3
    from database import DB_PATH
    from production import get_records
    from production_dashboard import (
        SHIFT_LABELS, aggregate_machines, coverage_text, detail_records,
        filter_records, machine_sort, summarize,
    )
    from functools import partial
    from production_pdf import render_daily_pdf, render_trend_pdf
    from production_report import chart, chart_document, render_report
    from production_trends import METRICS, get_trend_data, render_trends

    st.html('''<style>
    .stApp{background:#f4f7fb;color:#19344f}
    [data-testid="stMetric"]{background:white;border:1px solid #dce5ee;border-radius:10px;padding:16px}
    [data-testid="stMetricValue"]{font-size:clamp(22px,2.1vw,32px);white-space:normal;overflow-wrap:anywhere}
    [data-testid="stMetricLabel"]{font-size:14px}
    </style>''')
    st.subheader("生产 Dashboard")
    report_mode = st.selectbox(
        "报告类型", ["当日数据", "每台机一周趋势", "每台机一个月趋势"],
        index=None, placeholder="请选择报告类型", key="report", bind="query-params",
    )
    if report_mode is None:
        st.info("请选择报告类型后查看数据。")
        st.stop()
    is_daily = report_mode == "当日数据"
    if not DB_PATH.is_file():
        st.info("数据库尚未初始化，请先运行 python3 init_db.py。")
        st.stop()
    try:
        with closing(get_connection()) as connection:
            exists = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='slitting_records'"
            ).fetchone()
            dates = [row[0] for row in connection.execute(
                "SELECT DISTINCT production_date FROM slitting_records ORDER BY production_date DESC"
            )] if exists else []
        if not dates:
            st.info("还没有生产日报数据，请先使用 production.py 导入记录。")
            st.stop()
        if "date" not in st.session_state and "date" not in st.query_params:
            st.session_state["date"] = date.fromisoformat(dates[0])
        date_column, shift_column, machine_column = st.columns([1, 1, 1])
        with date_column:
            selected_date = st.date_input(
                "生产日期" if is_daily else "截止日期", value=None,
                key="date", bind="query-params", min_value=date(2000,1,1),
                max_value=date(2100,12,31), format="YYYY-MM-DD",
            )
        with shift_column:
            shift_label = st.selectbox("班次", ["全部", "白班", "夜班"],
                                       key="shift", bind="query-params")
        if selected_date is None:
            st.info("请选择生产日期。")
            st.stop()
        day = selected_date.isoformat()
        selected_shift = {"全部": None, "白班": "Day", "夜班": "Night"}[shift_label]
        with closing(get_connection()) as connection:
            daily_rows = get_records(connection, day)
            # Keep a stable historical device list even on dates with no data.
            machine_options = [r[0] for r in connection.execute(
                "SELECT DISTINCT machine_id FROM slitting_records"
            )]
        with machine_column:
            machine_label = st.selectbox("设备", ["全部设备"] + sorted(machine_options,key=machine_sort),
                                         key="machine", bind="query-params")
        machine = None if machine_label == "全部设备" else machine_label
        rows = filter_records(daily_rows, selected_shift, machine)
        summary = summarize(rows)
        st.caption(f"{'数据日期' if is_daily else '趋势截止日期'}：{day} · {SHIFT_LABELS[selected_shift]} · {machine_label}")
        refresh_column, download_column = st.columns([1,3])
        with refresh_column:
            st.button("刷新数据", width="stretch")
        if is_daily:
            with download_column:
                pdf_column, html_column = st.columns(2)
                with pdf_column:
                    st.download_button("导出日报 PDF",
                                       partial(render_daily_pdf, tuple(daily_rows), day, selected_shift, machine),
                                       file_name=f"slitting-{day}-{selected_shift or 'all'}-{machine or 'all'}.pdf",
                                       mime="application/pdf", on_click="ignore",
                                       key=f"daily_pdf_{day}_{selected_shift}_{machine}",
                                       help="下载当前日期、班次和设备的指标、图表及完整明细。")
                with html_column:
                    st.download_button("下载当前日报 HTML", render_report(daily_rows,day,selected_shift,machine),
                                       file_name=f"slitting-{day}-{selected_shift or 'all'}-{machine or 'all'}.html",
                                       mime="text/html")
            st.caption(coverage_text(rows,selected_shift))
            st.subheader("整体概况")
            values = [
                ("合格产出面积", f"{summary['qualified_output_m2']:,.1f} m²" if rows else '—', "合格成品的产出面积，单位 m²。"),
                ("投入计划达成率", summary['attainment'], "投入卷数合计 ÷ 计划卷数合计。"),
                ("面积合格率", summary['qualification'], "合格产出面积合计 ÷ 实际产出面积合计。"),
                ("已记录设备数", f"{summary['machine_count']} 台", "所选范围内按设备编号去重，不表示设备运行状态。"),
            ]
            for column, (label,value,help_text) in zip(st.columns(4),values):
                with column:
                    st.metric(label,value,help=help_text)
            if rows:
                st.caption(f"计划投入 {summary['planned_rolls']:,} 卷 · 实际投入 {summary['input_rolls']:,} 卷 · "
                           f"合格成品 {summary['qualified_rolls']:,} 卷 · 实际产出 {summary['actual_output_m2']:,.1f} m²")
                if selected_shift is None:
                    with st.expander("白班 / 夜班汇总"):
                        for shift in ('Day','Night'):
                            subset=filter_records(rows,shift)
                            if subset:
                                s=summarize(subset)
                                st.write(f"{SHIFT_LABELS[shift]} · 合格面积 {s['qualified_output_m2']:,.1f} m² · "
                                         f"投入计划达成率 {s['attainment']} · 面积合格率 {s['qualification']}")
                st.subheader("设备对比")
                devices=aggregate_machines(rows)
                st.markdown("**计划投入与实际投入**")
                st.iframe(chart_document(chart(devices,('planned_rolls','input_rolls'),('计划投入','实际投入'),'卷')),
                          height="content",alt="各设备计划和实际投入对比")
                st.markdown("**实际产出与合格产出**")
                st.iframe(chart_document(chart(devices,('actual_output_m2','qualified_output_m2'),('实际产出','合格产出'),'m²')),
                          height="content",alt="各设备实际和合格产出面积对比")
            else:
                st.info("当前日期、班次及设备范围暂无生产记录；缺失记录不表示零产量。")
        st.subheader("趋势分析")
        period_column, metric_column = st.columns(2)
        with period_column:
            if is_daily:
                period = st.selectbox("趋势范围", ["最近 7 天", "最近 30 天"],
                                      key="period",bind="query-params")
                days=7 if period=="最近 7 天" else 30
            else:
                days=7 if report_mode=="每台机一周趋势" else 30
                st.caption(f"最近 {days} 天（含截止日期）；与上方班次、设备选择联动。")
        with metric_column:
            metric=st.selectbox("趋势指标",list(METRICS),key="metric",bind="query-params")
        show_changeover_details = st.toggle("显示换产说明", value=False,
                                     key="show_changeovers", bind="query-params",
                                     help="仅控制图下方详细说明；图中的换产线、圆圈及标记始终保留。导出报告跟随此选择。")
        with closing(get_connection()) as connection:
            trend_rows=get_trend_data(connection,day,days,selected_shift)
        visible_trends=[r for r in trend_rows if machine is None or r['machine_id']==machine]
        if visible_trends:
            trend_report=render_trends(trend_rows,day,days,metric,selected_shift,machine,show_changeovers=show_changeover_details)
            pdf_column, html_column = st.columns(2)
            with pdf_column:
                st.download_button("导出趋势 PDF",
                                   partial(render_trend_pdf, tuple(trend_rows), day, days, metric, selected_shift, machine, show_changeovers=show_changeover_details),
                                   file_name=f"slitting-trend-{day}-{days}days-{selected_shift or 'all'}-{machine or 'all'}.pdf",
                                   mime="application/pdf", on_click="ignore",
                                   key=f"trend_pdf_{day}_{days}_{metric}_{selected_shift}_{machine}_{show_changeover_details}",
                                   help="下载当前趋势范围、指标、班次和设备的数据，图中换产标记始终保留，详细说明跟随上方开关。")
            with html_column:
                st.download_button("下载当前趋势报告 HTML",trend_report,
                                   file_name=f"slitting-trend-{day}-{days}days-{selected_shift or 'all'}-{machine or 'all'}.html",
                                   mime="text/html")
            st.iframe(trend_report,height="content",alt="每台分切机的生产趋势图")
        else:
            st.info("所选日期范围、班次及设备暂无趋势记录。")
        if is_daily:
            with st.expander(f"生产明细 · {len(rows)} 条记录"):
                if rows:
                    st.dataframe(detail_records(rows),hide_index=True,width="stretch")
                    st.caption("综收沿用原报表值；— 表示不可用。所有比例均按合计口径计算。")
                else:
                    st.write("暂无生产明细。")
    except sqlite3.Error as error:
        st.error(f"读取生产数据失败：{error}")
    st.stop()


demo_tab, original_tab = st.tabs(["订单进度 Demo", "原有订单分析"])
with demo_tab:
    from order_progress_demo import render_demo
    render_demo()

with original_tab:
    order_id = st.text_input(
        "Order ID",
        placeholder="Example: ORD001"
    )


    if st.button("Analyze Order"):

        if not order_id:
            st.warning(
                "Please enter an Order ID."
            )

        else:
            order = get_order(order_id)

            if order:
                st.success(
                    "Order found."
                )

                st.subheader(
                    "Order Information"
                )

                st.write(
                    "Order ID:",
                    order[0]
                )

                st.write(
                    "Product:",
                    order[1]
                )

                st.write(
                    "Quantity:",
                    order[2]
                )

                st.write(
                    "Due Date:",
                    order[3]
                )

                st.write(
                    "Priority:",
                    order[4]
                )

                materials = get_material_requirements(
                    product=order[1],
                    order_quantity=order[2]
                )

                st.subheader(
                    "Material Requirements"
                )

                if materials:
                    for material in materials:

                        st.write(
                            f"{material['material_name']} | "
                            f"Required: {material['required']} | "
                            f"Available: {material['available']} | "
                            f"Shortage: {material['shortage']}"
                        )

                else:
                    st.warning(
                        "No BOM data found for this product."
                    )

            else:
                st.error(
                    "Order not found."
                )
