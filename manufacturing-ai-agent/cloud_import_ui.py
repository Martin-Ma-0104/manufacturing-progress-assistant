"""Manual admin-only import of already verified JSON. No image recognition."""
import hmac
import sqlite3
from contextlib import closing

import streamlit as st
from database import get_connection
from cloud_data import decode_payload, import_payload
import abnormality


def render_import():
    st.subheader('导入已核对的数据')
    st.caption('仅上传已核对的生产 JSON 或恢复包。云端文件可能在重启后丢失，请保留本机原始资料。')
    try:
        configured=st.secrets.get('admin_import_password','')
    except (FileNotFoundError, st.errors.StreamlitSecretNotFoundError):
        configured=''
    if not configured:
        st.info('导入暂未启用。网站所有者需在 Streamlit Secrets 设置 admin_import_password。')
        return
    provided=st.text_input('导入密码',type='password',key='import_password')
    if not hmac.compare_digest(provided,str(configured)):
        if provided:
            st.error('导入密码不正确。')
        return
    uploaded=st.file_uploader('已核对 JSON / 恢复包',type=['json'])
    if uploaded is None:
        return
    try:
        if uploaded.size>10*1024*1024:
            raise ValueError('File exceeds 10 MB.')
        payload=decode_payload(uploaded.getvalue())
        st.write(f'生产记录：{len(payload["records"])} 条 · 已确认换型：{len(payload["changeover_events"])} 条 · '
                 f'异常记录：{len(payload.get("abnormality_events", []))} 条')
        st.dataframe([{k:r[k] for k in ('production_date','shift','machine_id','product','input_rolls','qualified_output_m2')}
                      for r in payload['records']],hide_index=True,width='stretch')
        if payload.get('abnormality_events'):
            st.caption('异常仅为已核对记录；未确认班次留空，分钟合计不等于实际停机。')
            st.dataframe([{k:r[k] for k in abnormality.PUBLIC_FIELDS} for r in payload['abnormality_events']],
                         hide_index=True,width='stretch')
            st.caption(abnormality.coverage(payload['abnormality_events']))
        if st.button('确认导入',type='primary'):
            with closing(get_connection()) as connection:
                counts=import_payload(payload,connection)
            st.success(f'新增 {counts[0]} 条生产记录、{counts[1]} 条换型、{counts[2] if len(counts)>2 else 0} 条异常；相同数据跳过，冲突整批拒绝。')
            st.info('切换至生产 Dashboard 查看。')
    except (ValueError,TypeError,KeyError,UnicodeError,sqlite3.Error) as error:
        st.error(f'导入失败：{error}')
