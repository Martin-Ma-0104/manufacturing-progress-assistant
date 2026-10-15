"""Isolated, in-memory order progress demonstration. No production data access."""
from collections import defaultdict


DEMO_ORDERS = (
    dict(order_id='DEMO-001', product='Demo Film A · 88.8 mm × 2,000 m', target=1000,
         rows=(('2026-10-12', 'FX1', '白班', 150),
               ('2026-10-13', 'FX1', '白班', 120),
               ('2026-10-13', 'FX2', '夜班', 80),
               ('2026-10-14', 'FX2', '白班', 300))),
    dict(order_id='DEMO-002', product='Demo Film B · 93.7 mm × 2,000 m', target=500,
         rows=(('2026-10-12', 'FX4', '白班', 200),
               ('2026-10-13', 'FX4', '夜班', 300))),
    dict(order_id='DEMO-003', product='Demo Film C · 88.8 mm × 2,000 m', target=800,
         rows=()),
    dict(order_id='DEMO-004', product='Demo Film D · 93.7 mm × 2,000 m', target=500,
         rows=(('2026-10-13', 'FX7', '白班', 250),
               ('2026-10-14', 'FX7', '夜班', 300))),
)


def progress_summary(target, rows):
    """Count qualified finished rolls allocated to one simulated order only."""
    if type(target) is not int or target < 0:
        raise ValueError('订单要求卷数必须是非负整数')
    daily = defaultdict(int)
    for day, machine, shift, rolls in rows:
        if type(rolls) is not int or rolls < 0:
            raise ValueError('合格成品卷数必须是非负整数')
        daily[day] += rolls
    completed = sum(daily.values())
    running = 0
    points = []
    for day, rolls in sorted(daily.items()):
        running += rolls
        points.append({'日期': day, '当日合格成品卷数': rolls,
                       '累计合格成品卷数': running, '订单目标卷数': target})
    return dict(completed=completed, remaining=max(target-completed, 0),
                excess=max(completed-target, 0) if target else None,
                ratio=completed/target if target else None, points=points)


def render_demo():
    import streamlit as st

    st.subheader('订单完成进度')
    st.info('演示数据 · 订单、产品规格和分切明细均为模拟，不代表真实订单进度。')
    labels = ('DEMO-001 · Film A', 'DEMO-002 · Film B',
              'DEMO-003 · Film C', 'DEMO-004 · Film D')
    left, right = st.columns([2, 1])
    with left:
        order_id = st.selectbox('模拟订单', [o['order_id'] for o in DEMO_ORDERS],
                               format_func=lambda value: labels[next(i for i, o in enumerate(DEMO_ORDERS) if o['order_id'] == value)],
                               key='demo_order')
    order = next(o for o in DEMO_ORDERS if o['order_id'] == order_id)
    # A separate session value for each order preserves edits while switching orders.
    target_key = f'demo_target_{order_id}'
    if target_key not in st.session_state:
        st.session_state[target_key] = st.session_state.get(f'saved_{target_key}', order['target'])
    def save_target():
        st.session_state[f'saved_{target_key}'] = st.session_state[target_key]
    with right:
        target = st.number_input('订单要求卷数（可试改）', min_value=0,
                                 step=50, key=target_key, on_change=save_target)
    st.caption(f"模拟产品：{order['product']} · 计数单位：合格成品卷")
    st.caption('修改目标仅用于本次会话演示；不会保存到数据库。')
    summary = progress_summary(target, order['rows'])
    ratio = summary['ratio']
    metrics = st.columns(4)
    for col, label, value in zip(metrics,
            ['订单要求', '已完成合格卷数', '还需生产', '完成率'],
            [f'{target:,} 卷', f"{summary['completed']:,} 卷",
             f"{summary['remaining']:,} 卷" if target else '—',
             f'{ratio:.1%}' if ratio is not None else '—']):
        col.metric(label, value)
    if ratio is None:
        st.info('订单要求为 0，完成率和剩余需求不可用。请设置大于 0 的目标卷数。')
    else:
        if summary['excess']:
            status = f"已超出目标 {summary['excess']:,} 卷 · 完成率 {ratio:.1%}"
        elif ratio >= 1:
            status = '已达到订单目标 · 完成率 100.0%'
        else:
            status = f"已完成 {ratio:.1%} · 还需生产 {summary['remaining']:,} 卷"
        st.progress(min(ratio, 1.0), text=status)
    st.caption('完成率 = 该模拟订单累计合格成品卷数 ÷ 订单要求卷数。投入母卷不计入；达到生产目标不表示已发货。')

    st.subheader('累计生产进度')
    if summary['points']:
        points = summary['points']
        series = ['累计合格成品卷数', '订单目标卷数'] if target else ['累计合格成品卷数']
        chart_rows = [{'日期': p['日期'], '指标': name, '卷数': p[name]}
                      for p in points for name in series]
        st.vega_lite_chart(chart_rows, {
            'mark': {'type': 'line'},
            'encoding': {
                'x': {'field': '日期', 'type': 'ordinal', 'sort': 'ascending',
                      'title': '生产日期',
                      'axis': {'labelAngle': 0, 'labelOverlap': True, 'labelPadding': 8}},
                'y': {'field': '卷数', 'type': 'quantitative', 'title': '卷',
                      'scale': {'zero': True}},
                'color': {'field': '指标', 'type': 'nominal',
                          'scale': {'domain': series,
                                    'range': ['#2563a6', '#94a3b8'][:len(series)]},
                          'legend': {'orient': 'bottom', 'title': None}},
                'tooltip': [{'field': '日期'}, {'field': '指标'},
                            {'field': '卷数', 'type': 'quantitative', 'format': ',.0f'}],
            },
        }, width='stretch', height=260)
        st.caption('蓝线：累计合格成品卷数；灰线：订单目标。仅包含该模拟订单的记录日期。')
    else:
        st.info('此模拟订单暂无分切记录，累计完成为 0 卷。')
    with st.expander('模拟分切明细', expanded=True):
        if order['rows']:
            st.dataframe([{'日期': day, '设备': machine, '班次': shift,
                           '合格成品卷数（卷）': rolls}
                          for day, machine, shift, rolls in order['rows']],
                         hide_index=True, width='stretch')
        else:
            st.caption('暂无模拟分切明细。')
