"""Shared floating assistant shell; no production or credentials in layout code."""
from datetime import date, timedelta
from pathlib import Path

import streamlit as st

from database import DB_PATH
from ai_production_data import normalize_scope
from ai_production_ui import render_agent

ASSETS = Path(__file__).parent
PAGES = ("分切生产日报", "订单分析", "数据导入", "生产分析")
LEGACY_PAGE = "AI Production Assistant"


def migrate_legacy_page():
    """Translate old shared URLs before the new sidebar widget is registered."""
    if st.query_params.get("page") == LEGACY_PAGE or st.session_state.get("page") == LEGACY_PAGE:
        st.query_params["page"] = PAGES[0]
        st.session_state["page"] = PAGES[0]
        st.session_state["ai_panel_open"] = True


def production_scope_from_state(page, state):
    """Read only visible production filters, never orders or upload contents."""
    if page == '生产分析':
        try:
            def iso(value):return value.isoformat() if isinstance(value,date) else value
            return normalize_scope(iso(state.get('diagnostic_start')),iso(state.get('diagnostic_end')),
                {'全部':None,'白班':'Day','夜班':'Night'}[state.get('diagnostic_shift','全部')],state.get('diagnostic_machines',[]))
        except (ValueError,TypeError,KeyError):
            return None
    if page != PAGES[0]:
        return None
    mode = state.get("report")
    if mode not in ("当日数据", "每台机一周趋势", "每台机一个月趋势"):
        return None
    end = state.get("date")
    try:
        end = date.fromisoformat(end) if isinstance(end, str) else end
        if not isinstance(end, date):
            return None
        days = {"当日数据": 1, "每台机一周趋势": 7, "每台机一个月趋势": 30}[mode]
        shift = {"全部": None, "白班": "Day", "夜班": "Night"}[state.get("shift", "全部")]
        machine = state.get("machine", "全部设备")
        return normalize_scope((end - timedelta(days=days - 1)).isoformat(), end.isoformat(),
                               shift, [] if machine == "全部设备" else [machine])
    except (ValueError, TypeError, KeyError):
        return None


def _set_open(value):
    st.session_state["ai_panel_open"] = value
    if not value:
        st.session_state["ai_show_settings"] = False


def _toggle_settings():
    st.session_state["ai_show_settings"] = not st.session_state.get("ai_show_settings", False)


@st.fragment
def render_floating_assistant(page, db_path=DB_PATH):
    # Always mounted before any business-page st.stop(), including empty pages.
    st.html(ASSETS / "ai_floating_panel.css")
    with st.container(key="ai_floating_root", gap="small"):
        if not st.session_state.get("ai_panel_open", False):
            st.button("AI", icon=":material/chat:", key="ai_launcher", type="primary",
                      help="打开生产AI助手", on_click=_set_open, args=(True,))
        else:
            with st.container(horizontal=True, vertical_alignment="center", key="ai_panel_header"):
                st.html('<div class="ai-drag-handle" data-ai-drag-handle role="button" '
                        'tabindex="0" title="拖动标题可移动" aria-label="移动AI助手，可用方向键调整位置">'
                        '<strong>AI Chat</strong></div>')
                settings_open = st.session_state.get("ai_show_settings", False)
                st.button("返回" if settings_open else "设置", icon=":material/arrow_back:" if settings_open else ":material/settings:",
                          key="ai_settings", type="tertiary", on_click=_toggle_settings,
                          help="返回聊天" if settings_open else "查询范围和接入设置")
                st.button("关闭", icon=":material/close:", key="ai_close", type="tertiary",
                          on_click=_set_open, args=(False,))
            with st.container(key="ai_panel_body"):
                production_scope = None
                if page == "生产分析" or (page == PAGES[0] and st.session_state.get("report") in (
                        "当日数据", "每台机一周趋势", "每台机一个月趋势")):
                    production_scope = lambda: production_scope_from_state(page, st.session_state)
                render_agent(db_path, compact=True,
                             production_scope=production_scope, show_settings=settings_open)
    # Static, local layout behavior only; no user strings or model output are
    # interpolated into executable markup. Python remains the only API caller.
    st.html("<script>" + (ASSETS / "ai_floating_panel.js").read_text() + "</script>",
            unsafe_allow_javascript=True)
