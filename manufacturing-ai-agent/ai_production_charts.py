"""Local result tables, CSV and chart specs. No model-generated code or images."""
import csv
import io


def safe_cell(value):
    if isinstance(value,str) and value.lstrip().startswith(('=','+','-','@')):
        return "'"+value
    return value


def csv_bytes(presentation):
    rows = presentation['rows']
    if not rows:
        return b''
    stream = io.StringIO(newline='')
    writer = csv.writer(stream)
    writer.writerow([safe_cell(k) for k in rows[0]])
    for row in rows:
        writer.writerow([safe_cell(row.get(k)) for k in rows[0]])
    return stream.getvalue().encode('utf-8-sig')


def bar_spec(chart, expanded=False):
    rows = chart['rows']
    if chart.get('kind')=='deviation':
        encoding=dict(x=dict(field='label',type='nominal',sort=None,title='设备',axis=dict(labelAngle=0)),
                      y=dict(field='value',type='quantitative',title='投入偏差（实际−计划，母卷）',scale=dict(zero=True)),
                      tooltip=[dict(field='label',title='设备'),dict(field='value',type='quantitative',title='偏差（母卷）')])
        return dict(data=dict(values=rows),height=270 if expanded else 230,padding=dict(top=25,bottom=25),
                    layer=[dict(mark=dict(type='bar',color='#3979AB',size=28),encoding=encoding),
                           dict(mark=dict(type='text',dy={'expr':'datum.value >= 0 ? -9 : 15'},color='#244764'),
                                encoding={**encoding,'text':dict(field='value',type='quantitative',format='+,.0f')})],
                    config=dict(view=dict(stroke=None)))
    horizontal = len(rows)>8 or any(len(r['label'])>10 for r in rows)
    label = dict(field='label',type='nominal',sort=None,
                 title=chart['group'],axis=dict(labelAngle=0,labelLimit=280 if expanded else 140))
    value = dict(field='value',type='quantitative',title='异常记录时长合计（分钟）',
                 scale=dict(zero=True,domainMin=0),axis=dict(tickCount=5))
    encoding = dict(x=value if horizontal else label,y=label if horizontal else value,
                    tooltip=[dict(field='label',type='nominal',title=chart['group']),
                             dict(field='value',type='quantitative',title='累计异常记录分钟',format=',.1f')])
    text = dict(type='text',align='left' if horizontal else 'center',
                dx=6 if horizontal else 0,dy=0 if horizontal else -9,color='#244764',fontSize=12)
    return dict(data=dict(values=rows),height=max(240,len(rows)*32) if horizontal else 270 if expanded else 230,
                padding=dict(left=10,right=80 if horizontal else 24,top=22,bottom=10),
                layer=[dict(mark=dict(type='bar',color='#3979AB',size=22 if horizontal else 28),encoding=encoding),
                       dict(mark=text,encoding={**encoding,'text':dict(field='value',type='quantitative',format=',.1f')})],
                config=dict(view=dict(stroke=None),axis=dict(labelFontSize=12,titleFontSize=12,
                            titlePadding=14,gridColor='#e7edf3')))


def render_chart(chart, expanded=False):
    import streamlit as st
    if not chart or not chart['rows']:
        st.info('没有可绘制的生产投入记录；未补零。' if chart and chart.get('kind')=='deviation' else '没有可绘制的已知异常分钟；未把缺失数据补成零。')
        return
    spec = bar_spec(chart,expanded)
    if chart.get('partial_groups'):
        labels='、'.join(f"{r['label']}（{r['missing_count']}条）" for r in chart['partial_groups'][:10])
        st.caption('部分记录缺分钟：'+labels+'；这些柱高仅包含已知原报分钟，完整数量见表格。')
    if spec['height']>420:
        with st.container(height=420):
            st.vega_lite_chart(spec=spec,width='stretch')
    else:
        st.vega_lite_chart(spec=spec,width='stretch')
    st.caption('单位：母卷 · 正值为超计划，负值为未达计划 · 按设备编号，不是优劣排名' if chart.get('kind')=='deviation' else '单位：分钟 · 按分组顺序展示 · 异常记录时长合计，不代表实际净停机时长')
    if chart['omitted_groups']:
        st.caption(f"{chart['omitted_groups']} 组缺少对应生产或分钟记录，保留在表格中，未绘制为零柱。")


def render_presentation(presentation, key):
    import streamlit as st
    st.caption(presentation['title'])
    chart = presentation.get('chart')
    if chart is not None:
        render_chart(chart)
        if chart['rows']:
            @st.dialog('投入计划偏差' if chart.get('kind')=='deviation' else '异常累计时长',width='large')
            def enlarged():
                st.caption(presentation['title'])
                render_chart(chart,expanded=True)
                for warning in presentation['warnings']:
                    st.caption(warning)
            if st.button('放大图表',key=key+'_enlarge'):
                enlarged()
    rows = presentation['rows']
    if rows:
        # Protect the native dataframe CSV download as well as our own button.
        display_rows=[{k:safe_cell(v) for k,v in row.items()} for row in rows]
        st.dataframe(display_rows,hide_index=True,width='stretch',height=min(320,38+35*len(rows)))
        shown = len(rows)
        st.caption(f"结果表 {shown} 行／共 {presentation['total_rows']} 行"+
                   ('；仅显示并下载前1000行，请缩小范围查看剩余记录。' if presentation['truncated'] else '；未因摘要条数而省略设备。'))
        st.download_button('下载结果表 CSV',data=csv_bytes(presentation),mime='text/csv',
                           file_name='production-analysis.csv',key=key+'_csv',on_click='ignore')
    else:
        st.info('所选范围暂无对应记录；没有补零或生成空设备柱。')
    if presentation['warnings']:
        with st.expander('数据完整性与时间口径'):
            for warning in presentation['warnings']:
                st.caption(warning)
