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


st.title(
    "Production Data Viewer Agent"
)

st.write(
    "Daily Production Reports and Machine Trends"
)

st.divider()



page = st.sidebar.radio("功能", ["分切生产日报", "订单分析"],
                        key="page", bind="query-params")

if page == "分切生产日报":
    from contextlib import closing
    from datetime import date
    import sqlite3
    from database import DB_PATH
    from production import get_records
    from production_report import render_report
    from production_trends import METRICS, get_trend_data, render_trends

    st.subheader("分切生产报告")
    report_mode = st.selectbox(
        "报告类型", ["当日数据", "每台机一周趋势", "每台机一个月趋势"],
        index=None, placeholder="请选择报告类型",
        key="report", bind="query-params",
    )
    if report_mode is None:
        st.info("请选择报告类型后查看数据。")
        st.stop()
    is_daily = report_mode == "当日数据"
    st.caption("查看当天生产情况。" if is_daily else "以所选日期为结束日期，查看最近 7 天或 30 天的每台机数据点。")
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
        date_column, shift_column = st.columns(2)
        with date_column:
            selected_date = st.date_input(
                "生产日期" if is_daily else "截止日期",
                value=None,
                key="date", bind="query-params",
                min_value=date(2000, 1, 1),
                max_value=date(2100, 12, 31),
                format="YYYY-MM-DD",
                help="点击输入框打开日历，切换月份或年份后选择日期。",
            )
            if selected_date is None:
                st.info("请选择生产日期。")
                st.stop()
            day = selected_date.isoformat()
        with shift_column:
            shift_label = st.selectbox("班次", ["全部", "白班", "夜班"],
                                       key="shift", bind="query-params")
        selected_shift = {"全部": None, "白班": "Day", "夜班": "Night"}[shift_label]
        st.button("刷新数据")
        if not is_daily:
            days = 7 if report_mode == "每台机一周趋势" else 30
            with closing(get_connection()) as connection:
                trend_rows = get_trend_data(connection, day, days, selected_shift)
            if not trend_rows:
                st.info("所选日期范围、班次暂无生产记录。")
                st.stop()
            machine_column, metric_column = st.columns(2)
            with machine_column:
                machine = st.selectbox("设备", ["全部设备"] + sorted({r["machine_id"] for r in trend_rows}),
                                       key="machine", bind="query-params")
            with metric_column:
                metric = st.selectbox("趋势指标", list(METRICS),
                                      key="metric", bind="query-params")
            report = render_trends(trend_rows, day, days, metric, selected_shift,
                                   None if machine == "全部设备" else machine)
            st.download_button("下载当前趋势报告 HTML", report,
                               file_name=f"slitting-trend-{day}-{days}days-{selected_shift or 'all'}.html",
                               mime="text/html")
            st.iframe(report, height="content", alt="每台分切机的生产趋势图")
            st.stop()
        with closing(get_connection()) as connection:
            rows = get_records(connection, day)
        if selected_shift is not None:
            rows = [row for row in rows if row["shift"] == selected_shift]
        if not rows:
            st.info("该日期、班次暂无生产记录。")
            st.stop()
        report = render_report(rows, day, shift=selected_shift)
        st.download_button("下载当前日报 HTML", report,
                           file_name=f"slitting-{day}-{selected_shift or 'all'}.html", mime="text/html")
        st.iframe(report, height="content", alt="分切生产日报图表与明细")
    except sqlite3.Error as error:
        st.error(f"读取生产日报失败：{error}")
    st.stop()


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