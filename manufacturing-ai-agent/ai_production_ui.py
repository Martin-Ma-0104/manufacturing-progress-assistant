"""Production assistant UI. Local facts stay available without a model or consent."""
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
import hashlib
import json
import os
import sqlite3
import uuid

import streamlit as st

from database import DB_PATH
from production_dashboard import SHIFT_LABELS, detail_records
from ai_production_data import catalog, export_preview, normalize_scope, read_snapshot, query_analysis
from ai_production_client import AgentError, DEFAULT_MODEL, ask_production
from ai_production_charts import render_presentation


QUICK_QUESTIONS = (
    ("汇总当前范围", "请汇总当前筛选范围的合格产出面积、投入计划达成率和面积合格率。"),
    ("比较所选设备", "请按设备并列比较当前筛选范围的实际投入卷数、投入计划达成率和合格产出面积，不做优劣排名。"),
    ("生成生产总结", "请根据当前范围生成生产总结，包含合格产出、投入计划达成率、面积合格率和数据覆盖，不推断原因或未来产量。"),
)


def _api_key():
    """Read server-side configuration without displaying or logging its contents."""
    value = os.environ.get("OPENAI_API_KEY", "").strip()
    if not value:
        try:
            value = str(st.secrets.get("OPENAI_API_KEY", "")).strip()
        except (FileNotFoundError, st.errors.StreamlitSecretNotFoundError):
            value = ""
    return value


def _digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def _business_today():
    return datetime.now(ZoneInfo("America/New_York")).date().isoformat()


def _scope_label(scope):
    devices = "、".join(scope["machines"]) or "全部设备"
    return (f"{scope['start_date']} 至 {scope['end_date']} · "
            f"{SHIFT_LABELS[scope['shift']]} · {devices}")


def _table(rows, identity=None):
    result = []
    for row in rows:
        item = {}
        if identity:
            item["设备" if identity == "machine_id" else "生产日期"] = row[identity]
        item.update({
            "计划投入（卷）": row["planned_rolls"],
            "实际投入（卷）": row["input_rolls"],
            "合格成品（卷）": row["qualified_rolls"],
            "实际产出（m²）": row["actual_output_m2"],
            "合格产出（m²）": row["qualified_output_m2"],
            "投入计划达成率": row["attainment"],
            "面积合格率": row["qualification"],
        })
        result.append(item)
    return result


def _usage(usage, cached=False):
    if not usage:
        return
    if cached:
        st.caption("使用当前会话缓存，本次没有新模型请求；下方用量为原请求回执。")
    requests = usage.get("requests", 0)
    reported = usage.get("reported_requests", requests)
    st.caption(f"模型请求 {requests} 次 · 已回执输入 {usage.get('input_tokens', 0):,} token · "
               f"已回执输出 {usage.get('output_tokens', 0):,} token")
    if reported < requests:
        st.caption("部分请求未返回用量；失败或超时也可能产生费用，以 API 账单为准。")


def _answer(item, compact=False, slot=0):
    result = item["result"]
    if result["status"] == "answered":
        st.caption("回答采用的范围：" + _scope_label(result["scope"]))
        if not compact:
            st.caption("AI 选择查询与回答重点；数字和事实句由程序核对生成。")
        coverage = result.get("coverage", {})
        for fact in result["facts"]:
            # Coverage stays available below the table; don't repeat the same
            # long caution three times before the chart in a small chat window.
            if not coverage.get('text') or not fact['text'].endswith(coverage['text']):
                st.write("• " + fact["text"])
        if result.get('presentation'):
            render_presentation(result['presentation'],key='ai_result_'+str(slot))
        if coverage.get('text') and not result.get('presentation',{}).get('warnings'):
            st.caption(coverage['text'])
    elif result["status"] == "clarification":
        st.info(result["message"])
    else:
        st.error(result["message"])
    if not compact:
        _usage(result.get("usage"), item.get("cached", False))
    elif result["status"] == "error" and result.get("usage", {}).get("requests"):
        st.caption("失败或超时仍可能产生调用费用，以 API 账单为准。")


def _remember_filters():
    # Durable values are separate from widget keys, which Streamlit cleans up
    # when the floating panel is closed or not rendered.
    st.session_state["ai_scope_state"] = {
        name: st.session_state[name] for name in ("ai_start", "ai_end", "ai_shift", "ai_machines")
    }


def _remember_permission():
    st.session_state["ai_consent_saved"] = bool(st.session_state.get("ai_allow_send", False))


def _restore_filters(latest, machines):
    saved = st.session_state.get("ai_scope_state")
    if saved is None:
        def day(key, default):
            try:
                parsed = date.fromisoformat(st.query_params.get(key, default.isoformat()))
                return parsed if date(2000, 1, 1) <= parsed <= date(2100, 12, 31) else default
            except (ValueError, TypeError):
                return default
        saved = dict(ai_start=day("ai_start", latest - timedelta(days=6)),
                     ai_end=day("ai_end", latest),
                     ai_shift=st.query_params.get("ai_shift", "全部"),
                     ai_machines=[m for m in st.query_params.get_all("ai_machines") if m in machines])
        if saved["ai_shift"] not in ("全部", "白班", "夜班"):
            saved["ai_shift"] = "全部"
        st.session_state["ai_scope_state"] = saved
    for name, value in saved.items():
        # Rehydrate before widget registration even if an old widget key is
        # still present: settings can disappear for one or more fragment runs.
        st.session_state[name] = list(value) if isinstance(value, list) else value


def _adopt_scope(scope):
    values = dict(ai_start=date.fromisoformat(scope["start_date"]),
                  ai_end=date.fromisoformat(scope["end_date"]),
                  ai_shift={None: "全部", "Day": "白班", "Night": "夜班"}[scope["shift"]],
                  ai_machines=list(scope["machines"]))
    st.session_state["ai_scope_state"] = values
    for key, value in values.items():
        st.session_state[key] = value


def _filter_controls():
    start_col, end_col = st.columns(2)
    with start_col:
        start = st.date_input("开始日期", value=None, key="ai_start", on_change=_remember_filters,
                              min_value=date(2000, 1, 1), max_value=date(2100, 12, 31), format="YYYY-MM-DD")
    with end_col:
        end = st.date_input("结束日期", value=None, key="ai_end", on_change=_remember_filters,
                            min_value=date(2000, 1, 1), max_value=date(2100, 12, 31), format="YYYY-MM-DD")
    shift_label = st.selectbox("班次范围", ["全部", "白班", "夜班"],
                              key="ai_shift", on_change=_remember_filters)
    return start, end, shift_label


def render_agent(db_path=DB_PATH, *, compact=False, production_scope=None, show_settings=False):
    simple = compact and not show_settings
    if not compact:
        st.subheader("AI Production Assistant")
        st.caption("生产问答 · 设备对比 · 生产总结。先选择范围，再提问；每次问题均以当前筛选为准。")
    try:
        options = catalog(db_path)
    except (OSError, ValueError, sqlite3.Error):
        st.info("还没有可读取的生产数据库，请先按原流程导入已核对的数据。")
        return
    if not options["dates"]:
        st.info("还没有生产或异常记录；AI 不会补造数据。请先按原流程导入已核对的数据。")
        return
    latest = date.fromisoformat(options["dates"][-1])
    _restore_filters(latest, options["machines"])
    if not simple and production_scope is not None:
        if st.button("使用当前生产筛选", key="ai_adopt_scope", width="stretch",
                     help="采用当前日报日期或趋势区间、班次和设备；范围变化将清空旧回答并重置许可。"):
            # The shell mounts before the business page. Resolve at click time
            # so first-render defaults and the latest page filters are present.
            adopted = production_scope() if callable(production_scope) else production_scope
            if adopted is not None:
                _adopt_scope(adopted)
            else:
                st.info("请先在生产页面选择报告日期、班次和设备。")
    if simple:
        saved = st.session_state["ai_scope_state"]
        start, end, shift_label, machines = (saved[name] for name in (
            "ai_start", "ai_end", "ai_shift", "ai_machines"))
    else:
        filters = st.expander("查询范围 · 日期 / 班次 / 设备", expanded=not compact)
        with filters:
            start, end, shift_label = _filter_controls()
            machines = st.multiselect("设备范围", options["machines"], key="ai_machines",
                                      placeholder="全部设备，可选择多台", on_change=_remember_filters,
                                      help="留空表示全部历史设备；未记录设备不视为零产量。")
        _remember_filters()
    if start is None or end is None:
        st.info("请选择开始和结束日期。")
        return
    shift = {"全部": None, "白班": "Day", "夜班": "Night"}[shift_label]
    try:
        scope = normalize_scope(start.isoformat(), end.isoformat(), shift, machines)
        snapshot = read_snapshot(scope, db_path)
    except (ValueError, OSError, sqlite3.Error) as error:
        # Query failures never show raw database errors or file paths.
        if isinstance(error, ValueError):
            st.warning("日期范围需按先后顺序选择，且最多包含 30 天；设备和班次需为有效选项。")
        else:
            st.error("本机生产记录暂时无法读取，请刷新后重试。")
        return
    if not simple:
        st.caption("生产问答范围：" + _scope_label(scope))
    key = _api_key()
    # Secrets participate only through a one-way in-memory fingerprint.
    context = _digest(['PLAN-022-v1',scope, snapshot["version"], DEFAULT_MODEL, _business_today(),
                       hashlib.sha256(key.encode()).hexdigest()])
    if st.session_state.get("ai_context") != context:
        previous = st.session_state.get("ai_context")
        st.session_state["ai_context"] = context
        st.session_state["ai_history"] = []
        st.session_state["ai_answers"] = {}
        # A single widget key avoids restoring an old approval when returning to a scope.
        st.session_state["ai_allow_send"] = False
        st.session_state["ai_consent_saved"] = False
        st.session_state.pop("ai_pending_question", None)
        st.session_state.pop("ai_pending_approved", None)
        if previous and not simple:
            st.caption("筛选、数据或模型配置已变化，已开始新对话并重置发送许可。")
    if key and not simple:
        st.caption(f"模型：{DEFAULT_MODEL} · 已读取本机 API 配置 · 仅主动提问时调用")
    elif not key:
        st.info("AI 未配置，请在右上角设置中查看接入说明。" if simple
                else "AI 未配置，暂时无法生成回答。下方本地事实仍可查看。")
    if not key and not simple:
        with st.expander("配置 AI 接入"):
            st.write("在本机 Streamlit Secrets 或环境变量中设置 OPENAI_API_KEY，保存后重新加载网站。")
            st.code('OPENAI_API_KEY = "在本机填写你的 API 密钥"', language="toml")
            st.caption("保留已有导入密码配置。密钥不要发到聊天、放入网址或提交 GitHub。")
            st.link_button("OpenAI 官方接入说明", "https://developers.openai.com/api/docs/quickstart")

    st.session_state["ai_allow_send"] = st.session_state.get("ai_consent_saved", False)

    consent = bool(st.session_state.get("ai_consent_saved", False))
    question = None
    if not simple:
        evidence = st.expander("本机数据依据与明细", expanded=not compact)
        with evidence:
            st.button("刷新本机数据", key="ai_refresh", help="重新读取本机记录，不调用模型。")
            _render_evidence(snapshot, compact)
        with st.expander("发送预览与说明"):
            st.caption("仅发送当前问题和必要生产／异常／投入差距事实；不发送截图、数据库、来源备注、原始明细或历史聊天全文。")
            st.json(export_preview(snapshot), expanded=False)
            st.caption("API 按用量收费；默认不用于模型训练，监测日志可能保留至多 30 天。")
        consent = st.checkbox("允许发送当前问题和范围内必要数字至 OpenAI", key="ai_allow_send",
                              on_change=_remember_permission)
        with st.expander("快捷问题", expanded=not compact):
            for label, prompt in QUICK_QUESTIONS:
                if st.button(label, disabled=not (key and consent), width="stretch", key="ai_quick_" + label):
                    question = prompt
    pending = st.session_state.get("ai_pending_question")
    if st.session_state.pop("ai_pending_approved", False) and pending and consent and pending["context"] == context:
        question = pending["question"]
        st.session_state.pop("ai_pending_question", None)
        pending = None
    history = st.container(height=(420 if simple else 240) if compact else "content",
                           key="ai_chat_history", autoscroll=True)
    with history:
        if not st.session_state["ai_history"]:
            st.caption("你好，直接输入你想了解的生产问题即可。")
        for index,item in enumerate(st.session_state["ai_history"]):
            _chat_item(item, compact=simple,slot=item.get('id',index))
        if pending and pending["context"] == context:
            with st.chat_message("user"):
                st.write(pending["question"])
            with st.chat_message("assistant"):
                st.write("发送前请确认：允许将这个问题及以下范围的必要生产数字发送给 OpenAI？")
                st.caption(_scope_label(scope) + "。API 按用量收费。")
                with st.expander("查看发送内容"):
                    st.json(export_preview(snapshot), expanded=False)
                    st.caption("不发送截图、数据库、来源备注、原始明细或历史聊天全文。默认不用于训练，监测日志可能保留至多30天。")
                allow, cancel = st.columns(2)
                allow.button("允许并发送", key="ai_confirm_send", on_click=_approve_pending, type="primary")
                cancel.button("取消", key="ai_cancel_send", on_click=_cancel_pending)
    enabled = bool(key) and (simple or consent) and not pending
    typed = st.chat_input("输入你的问题…", max_chars=1000, disabled=not enabled, key="ai_question")
    if typed:
        question = typed
    if question is None:
        return
    if not question.strip():
        return
    if not consent:
        st.session_state["ai_pending_question"] = {"question": question, "context": context}
        # Simple chat is hosted by the floating fragment. Staging a question is
        # local only; the next explicit confirmation is the sole send trigger.
        st.rerun()
    cache_key = _digest([context, question.strip()])
    cache = st.session_state["ai_answers"]
    cached = cache_key in cache
    if cached:
        result = cache[cache_key]
    else:
        try:
            with st.spinner("正在核对生产事实…"):
                result = ask_production(question, snapshot, api_key=key, consent=consent)
            cache[cache_key] = result
            while len(cache) > 20:
                cache.pop(next(iter(cache)))
        except AgentError as error:
            result = {"status": "error", "message": error.message, "usage": error.usage}
        except Exception:
            result = {"status": "error", "message": "AI 回答生成失败，本地事实仍可查看；请稍后主动重试。"}
    item = {"id":uuid.uuid4().hex,"question": question, "result": result, "cached": cached}
    st.session_state["ai_history"].append(item)
    st.session_state["ai_history"] = st.session_state["ai_history"][-20:]
    with history:
        _chat_item(item, compact=simple,slot=item['id'])


def _approve_pending():
    pending = st.session_state.get("ai_pending_question")
    if pending and pending["context"] == st.session_state.get("ai_context"):
        st.session_state["ai_consent_saved"] = True
        st.session_state["ai_allow_send"] = True
        st.session_state["ai_pending_approved"] = True


def _cancel_pending():
    st.session_state.pop("ai_pending_question", None)
    st.session_state.pop("ai_pending_approved", None)


def _chat_item(item, compact=False,slot=0):
    with st.chat_message("user"):
        st.write(item["question"])
    with st.chat_message("assistant"):
        _answer(item, compact=compact,slot=slot)


def _render_evidence(snapshot, compact):
    summary = snapshot["summary"]
    has_rows = bool(snapshot["rows"])
    indicators = (
        ("合格产出面积", f"{summary['qualified_output_m2']:,.1f} m²" if has_rows else "—"),
        ("投入计划达成率", summary["attainment"]),
        ("面积合格率", summary["qualification"]),
        ("已记录设备数", f"{summary['machine_count']} 台"),
    )
    for index, (label, value) in enumerate(indicators):
        if index % (2 if compact else 4) == 0:
            cols = st.columns(2 if compact else 4)
        cols[index % len(cols)].metric(label, value)
    st.caption(snapshot["coverage"]["text"])
    with st.expander("查看设备、日期和原始明细"):
        devices_tab, days_tab, details_tab = st.tabs(["设备合计", "逐日合计", "原始明细（仅本机）"])
        if has_rows:
            with devices_tab:
                st.dataframe(_table(snapshot["machines"], "machine_id"), hide_index=True, width="stretch")
            with days_tab:
                st.dataframe(_table(snapshot["daily"], "production_date"), hide_index=True, width="stretch")
            with details_tab:
                rows = [{"生产日期": row["production_date"], **detail_records([row])[0]}
                        for row in snapshot["rows"]]
                st.dataframe(rows, hide_index=True, width="stretch")
                st.caption("原报表综收仅保留原值；未计入合格产出的面积不直接认定为废料。")
        else:
            st.write("所选范围暂无生产记录；缺失记录不表示零产量。")
    with st.expander('异常记录（仅本机，不调用模型）'):
        query = {**snapshot['scope'],'shift':'All' if snapshot['scope']['shift'] is None else snapshot['scope']['shift'],
                 'domain':'abnormalities','group_by':'machine','metrics':['reported_minutes','event_count'],
                 'categories':[],'status':'All','chart':'bar'}
        _,presentation = query_analysis(snapshot,query)
        render_presentation(presentation,key='ai_local_abnormalities')

