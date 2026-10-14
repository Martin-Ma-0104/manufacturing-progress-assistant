"""Manual admin-only import of already verified JSON. No image recognition."""
import hmac
import sqlite3
from contextlib import closing

import streamlit as st
from database import get_connection
from cloud_data import decode_payload, import_payload


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
        st.write(f'生产记录：{len(payload["records"])} 条 · 已确认换型：{len(payload["changeover_events"])} 条')
        st.dataframe([{k:r[k] for k in ('production_date','shift','machine_id','product','input_rolls','qualified_output_m2')}
                      for r in payload['records']],hide_index=True,width='stretch')
        if st.button('确认导入',type='primary'):
            with closing(get_connection()) as connection:
                records,events=import_payload(payload,connection)
            st.success(f'新增 {records} 条生产记录、{events} 条换型；相同数据跳过。')
            st.info('切换至生产 Dashboard 查看。')
    except (ValueError,TypeError,KeyError,UnicodeError,sqlite3.Error) as error:
        st.error(f'导入失败：{error}')
