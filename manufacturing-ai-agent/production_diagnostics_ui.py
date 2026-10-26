"""Local IE analysis page and honest readiness framework. No model calls."""
from datetime import date,timedelta
import sqlite3
import streamlit as st

from database import DB_PATH
from ai_production_data import catalog,normalize_scope,read_snapshot
from ai_production_charts import render_chart,render_presentation
from planning_data_contracts import blueprint,readiness,template_bytes
from production_diagnostics import CAUTION,analyze,presentation


def render_preparation():
    st.info('以下模块待接入真实资料；本版提供数据契约与关联框架，不生成产能、完工日期或缺料结论。')
    template=blueprint()
    for module in readiness():
        with st.expander(module['module']+' · '+module['status']):
            for entity in module['missing_entities']:
                st.markdown('**'+entity+'**')
                st.dataframe(template['entities'][entity]['fields'],hide_index=True,width='stretch')
    st.download_button('下载数据准备字段说明 JSON',template_bytes(),
                       file_name='planning-data-contracts.json',mime='application/json',key='planning_blueprint',on_click='ignore')
    st.caption('这是准备资料的字段说明模板，不能上传到现有生产数据导入器。后续真实资料接入需核对单位、关系和业务规则；不使用旧模拟订单、设备状态或库存代替。')


def render_diagnostics(db_path=DB_PATH):
    st.subheader('生产分析')
    st.caption('投入计划差距 · 异常证据 · 后续数据准备')
    analysis,preparation=st.tabs(['差距与异常','数据准备'])
    with preparation:
        render_preparation()
    with analysis:
        try:
            options=catalog(db_path)
            if not options['dates']:
                st.info('尚无生产或异常记录；可先在数据准备页查看后续资料要求。')
                return
            latest=date.fromisoformat(options['dates'][-1])
            for name,value in [('diagnostic_start',latest-timedelta(days=6)),('diagnostic_end',latest)]:
                if name not in st.session_state and name not in st.query_params:
                    st.session_state[name]=value
            a,b,c,d=st.columns([1,1,1,2])
            start=a.date_input('开始日期',value=None,key='diagnostic_start',bind='query-params',format='YYYY-MM-DD')
            end=b.date_input('结束日期',value=None,key='diagnostic_end',bind='query-params',format='YYYY-MM-DD')
            shift_label=c.selectbox('班次',['全部','白班','夜班'],key='diagnostic_shift',bind='query-params')
            machines=d.multiselect('设备',options['machines'],placeholder='全部设备',key='diagnostic_machines',bind='query-params')
            if start is None or end is None:
                st.info('请选择起止日期，最多30天。')
                return
            scope=normalize_scope(start.isoformat(),end.isoformat(),{'全部':None,'白班':'Day','夜班':'Night'}[shift_label],machines)
            snap=read_snapshot(scope,db_path)
        except (ValueError,OSError,sqlite3.Error):
            st.warning('请检查数据库与筛选：日期需先后有序、最多30天，设备需为已记录设备。')
            return
        result=analyze(snap)
        total=result['summary'];ab=total['abnormalities']
        st.caption(f"{scope['start_date']} 至 {scope['end_date']} · {shift_label} · "+('、'.join(machines) or '全部设备'))
        st.caption(f"生产 {total['record_count']} 条／{len(snap['coverage']['observed_dates'])} 个日期；异常 {ab['event_count']} 条／{len({e['production_date'] for e in snap['abnormalities']})} 个日期。两类记录覆盖独立，不代表完整采集。")
        st.button('刷新分析数据',key='diagnostic_refresh')
        def count(v,unit): return '—' if v is None else f'{v:,.0f} {unit}'
        for col,label,value in zip(st.columns(4),['未达计划（逐记录）','超额投入（逐记录）','面积合格率','已记录异常分钟'],
             [count(total['input_shortfall'],'母卷'),count(total['input_excess'],'母卷'),total['qualification'] or '—',count(ab['reported_minutes'],'分钟')]):
            col.metric(label,value)
        st.caption('未达计划和超额投入分别累计，不互相抵消；母卷投入不能等同于合格成品目标。')
        with st.expander('数据覆盖与计算口径'):
            for warning in result['warnings']:st.write(warning)
        left,right=st.columns(2)
        with left:
            st.markdown('**设备投入偏差（实际−计划）**')
            render_chart(presentation(snap,'machine','deviation')['chart'])
        with right:
            st.markdown('**异常类别已记录分钟**')
            render_chart(presentation(snap,'category','category')['chart'])
        with st.expander('异常类别占比与对应表'):
            render_presentation(presentation(snap,'category'),'diagnostic_category')
        with st.expander('待核查线索 · 仅并列事实，不作因果判断'):
            candidates=[r for r in result['rows'] if (r['未达计划（母卷，逐记录）'] or 0)>0 and r['异常记录数（条）']>0]
            for r in candidates[:10]:
                minutes=r['异常记录时长合计（分钟）']
                duration='分钟未记录' if minutes is None else f'原报{minutes:g}事件分钟'
                st.write(f"{r['生产日期']} · {r['设备']} · {r['班次']}：未达投入计划{r['未达计划（母卷，逐记录）']:g}母卷；同期录入异常{r['异常记录数（条）']}条／{duration}。可核查原事件处理、规格及记录覆盖，不能直接归因。")
            if len(candidates)>10:
                st.caption(f'共{len(candidates)}组，上列仅前10组；完整组见下方对照表。')
            if not candidates:
                st.caption('当前范围没有同时包含未达计划和已录入异常的记录组；不代表没有生产问题。')
        st.subheader('生产与异常证据对照')
        labels={'日期／设备／班次':'details','按设备':'machine','按日期':'date','按班次':'shift'}
        selected=st.selectbox('对照维度',list(labels),key='diagnostic_group',bind='query-params')
        render_presentation(presentation(snap,labels[selected]),'diagnostic_result')
        st.caption('无生产记录的字段留空；异常0条表示未录入异常，不等于没有发生。规格及确认换产见表格后列。')
        st.info(CAUTION)
        st.caption('AI总结请打开悬浮助手，在设置中显式使用当前筛选后提问；本分析页本身不调用模型。')
