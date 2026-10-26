"""Floating-shell regressions. All model traffic is mocked, data is synthetic."""
from datetime import date
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

import ai_production_ui as ui
from ai_floating_panel import production_scope_from_state
from production import import_records
from test_production import record
import test_ai_production as assistant_tests


class FloatingAssistantTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "synthetic.db"
        with sqlite3.connect(self.db) as con:
            import_records([record(), record(machine_id="TEST2", production_date="2026-01-02")], con)
        script = Path(self.temp.name) / "floating_app.py"
        script.write_text('''import streamlit as st
from datetime import date
from ai_floating_panel import PAGES, migrate_legacy_page, render_floating_assistant
migrate_legacy_page()
page=st.sidebar.radio("功能",list(PAGES),key="page",bind="query-params")
st.session_state.setdefault("report","当日数据")
st.session_state.setdefault("date",date(2026,1,1))
st.session_state.setdefault("shift","白班")
st.session_state.setdefault("machine","TEST1")
render_floating_assistant(page,''' + repr(str(self.db)) + ''')
st.info("主页面："+page)
st.stop()
''')
        self.app = AppTest.from_file(str(script), default_timeout=10)

    def clean(self):
        self.assertEqual(len(self.app.exception), 0)

    def test_scope_mapping_only_production_and_exact_period(self):
        state = dict(report="当日数据", date=date(2026, 1, 10), shift="夜班", machine="TEST1")
        self.assertIsNone(production_scope_from_state("订单分析", state))
        self.assertIsNone(production_scope_from_state("数据导入", state))
        for mode, start in (("当日数据", "2026-01-10"), ("每台机一周趋势", "2026-01-04"),
                            ("每台机一个月趋势", "2025-12-12")):
            state["report"] = mode
            result = production_scope_from_state("分切生产日报", state)
            self.assertEqual(result, dict(start_date=start, end_date="2026-01-10", shift="Night", machines=["TEST1"]))
        for changes in (dict(report=None), dict(date=None), dict(shift="invalid")):
            self.assertIsNone(production_scope_from_state("分切生产日报", dict(state, **changes)))

    def test_diagnostics_adoption_is_explicit_and_validated(self):
        state=dict(diagnostic_start=date(2026,1,1),diagnostic_end=date(2026,1,7),
                   diagnostic_shift='白班',diagnostic_machines=['TEST1'])
        self.assertEqual(production_scope_from_state('生产分析',state),
            dict(start_date='2026-01-01',end_date='2026-01-07',shift='Day',machines=['TEST1']))
        self.assertIsNone(production_scope_from_state('生产分析',{}))
        self.assertIsNone(production_scope_from_state('订单分析',state))

    def test_closed_all_pages_no_key_read_or_api_call(self):
        with patch.object(ui, "_api_key") as key, patch.object(ui, "ask_production") as ask:
            self.app.run()
            for page in ("订单分析", "数据导入", "分切生产日报", "生产分析"):
                self.app.radio(key="page").set_value(page).run()
                self.clean()
                self.assertIsNotNone(self.app.button(key="ai_launcher"))
                self.assertEqual(len(self.app.chat_input), 0)
            key.assert_not_called()
            ask.assert_not_called()

    def test_close_reopen_and_navigation_preserve_chat_scope_consent_cache(self):
        with patch.object(ui, "_api_key", return_value="synthetic-key"), \
                patch.object(ui, "ask_production", side_effect=assistant_tests.AssistantUiTests.fake_answer) as ask:
            self.app.run().button(key="ai_launcher").click().run()
            self.app.button(key="ai_settings").click().run()
            self.app.multiselect(key="ai_machines").set_value(["TEST1"]).run()
            self.app.checkbox(key="ai_allow_send").set_value(True).run()
            self.app.button(key="ai_quick_汇总当前范围").click().run()
            self.assertEqual(ask.call_count, 1)
            scope = dict(self.app.session_state["ai_scope_state"])
            self.app.button(key="ai_close").click().run()
            self.app.radio(key="page").set_value("订单分析").run()
            self.app.button(key="ai_launcher").click().run()
            self.app.button(key="ai_settings").click().run()
            self.clean()
            self.assertEqual(self.app.multiselect(key="ai_machines").value, ["TEST1"])
            self.assertTrue(self.app.checkbox(key="ai_allow_send").value)
            self.assertEqual(self.app.session_state["ai_scope_state"], scope)
            self.assertEqual(len(self.app.chat_message), 2)
            self.app.button(key="ai_quick_汇总当前范围").click().run()
            self.assertEqual(ask.call_count, 1)
            self.app.radio(key="page").set_value("数据导入").run()
            self.clean()
            self.assertEqual(len(self.app.chat_message), 4)
            self.assertEqual(len([b for b in self.app.button if b.key == "ai_adopt_scope"]), 0)
            self.assertEqual(ask.call_count, 1)

    def test_adopting_visible_filters_resets_context_and_consent_without_call(self):
        with patch.object(ui, "_api_key", return_value="synthetic-key"), \
                patch.object(ui, "ask_production", side_effect=assistant_tests.AssistantUiTests.fake_answer) as ask:
            self.app.run().button(key="ai_launcher").click().run()
            self.app.button(key="ai_settings").click().run()
            self.app.checkbox(key="ai_allow_send").set_value(True).run()
            self.app.button(key="ai_quick_汇总当前范围").click().run()
            self.app.button(key="ai_adopt_scope").click().run()
            self.clean()
            self.assertEqual(self.app.date_input(key="ai_start").value, date(2026, 1, 1))
            self.assertEqual(self.app.date_input(key="ai_end").value, date(2026, 1, 1))
            self.assertEqual(self.app.selectbox(key="ai_shift").value, "白班")
            self.assertEqual(self.app.multiselect(key="ai_machines").value, ["TEST1"])
            self.assertFalse(self.app.checkbox(key="ai_allow_send").value)
            self.assertEqual(len(self.app.chat_message), 0)
            self.assertEqual(ask.call_count, 1)

    def test_data_changes_while_closed_reset_approval_and_answers(self):
        with patch.object(ui, "_api_key", return_value="synthetic-key"), \
                patch.object(ui, "ask_production", side_effect=assistant_tests.AssistantUiTests.fake_answer) as ask:
            self.app.run().button(key="ai_launcher").click().run()
            self.app.button(key="ai_settings").click().run()
            self.app.checkbox(key="ai_allow_send").set_value(True).run()
            self.app.button(key="ai_quick_汇总当前范围").click().run()
            self.app.button(key="ai_close").click().run()
            with sqlite3.connect(self.db) as con:
                import_records([record(shift="Night")], con)
            self.app.button(key="ai_launcher").click().run()
            self.app.button(key="ai_settings").click().run()
            self.clean()
            self.assertFalse(self.app.checkbox(key="ai_allow_send").value)
            self.assertEqual(len(self.app.chat_message), 0)
            self.assertEqual(ask.call_count, 1)

    def test_legacy_url_redirects_to_dashboard_and_opens_panel_without_call(self):
        with patch.object(ui, "_api_key", return_value=""), patch.object(ui, "ask_production") as ask:
            self.app.query_params["page"] = "AI Production Assistant"
            self.app.run()
            self.clean()
            self.assertEqual(self.app.radio(key="page").value, "分切生产日报")
            self.assertIsNotNone(self.app.button(key="ai_close"))
            self.assertTrue(self.app.chat_input[0].disabled)
            ask.assert_not_called()

    def test_empty_database_still_opens_and_closes_without_model(self):
        with sqlite3.connect(self.db) as con:
            con.execute("DELETE FROM slitting_records")
        with patch.object(ui, "ask_production") as ask:
            self.app.run().button(key="ai_launcher").click().run()
            self.clean()
            self.assertTrue(any("还没有生产或异常记录" in message.value for message in self.app.info))
            self.app.button(key="ai_close").click().run()
            self.clean()
            self.assertIsNotNone(self.app.button(key="ai_launcher"))
            ask.assert_not_called()

    def test_simple_default_only_chat_and_optional_settings_no_model_call(self):
        with patch.object(ui, "_api_key", return_value="synthetic-key"), patch.object(ui, "ask_production") as ask:
            self.app.run().button(key="ai_launcher").click().run()
            self.clean()
            self.assertEqual(len(self.app.date_input), 0)
            self.assertEqual(len(self.app.multiselect), 0)
            self.assertEqual(len(self.app.checkbox), 0)
            self.assertFalse(self.app.chat_input[0].disabled)
            self.assertEqual(len(self.app.metric), 0)
            self.assertFalse(any(button.key.startswith("ai_quick_") for button in self.app.button))
            self.app.button(key="ai_settings").click().run()
            self.assertEqual(len(self.app.date_input), 2)
            self.app.button(key="ai_settings").click().run()
            self.clean()
            self.assertEqual(len(self.app.date_input), 0)
            ask.assert_not_called()

    def test_first_question_stays_local_until_confirmed_then_uses_cache(self):
        with patch.object(ui, "_api_key", return_value="synthetic-key"), \
                patch.object(ui, "ask_production", side_effect=assistant_tests.AssistantUiTests.fake_answer) as ask:
            self.app.run().button(key="ai_launcher").click().run()
            self.app.chat_input[0].set_value("汇总当前范围").run()
            self.clean()
            ask.assert_not_called()
            self.assertFalse(self.app.session_state["ai_consent_saved"])
            self.assertIsNotNone(self.app.button(key="ai_confirm_send"))
            self.app.button(key="ai_confirm_send").click().run()
            self.clean()
            self.assertEqual(ask.call_count, 1)
            self.assertTrue(ask.call_args.kwargs["consent"])
            self.assertEqual(len(self.app.chat_message), 2)
            self.app.chat_input[0].set_value("汇总当前范围").run()
            self.clean()
            self.assertEqual(ask.call_count, 1)
            self.assertEqual(len(self.app.chat_message), 4)
            self.assertEqual(len(self.app.checkbox), 0)

    def test_cancel_and_data_change_discard_unapproved_question(self):
        with patch.object(ui, "_api_key", return_value="synthetic-key"), patch.object(ui, "ask_production") as ask:
            self.app.run().button(key="ai_launcher").click().run()
            self.app.chat_input[0].set_value("比较设备").run()
            self.app.button(key="ai_cancel_send").click().run()
            self.clean()
            self.assertFalse(self.app.chat_input[0].disabled)
            self.assertNotIn("ai_pending_question",self.app.session_state)
            self.app.chat_input[0].set_value("比较设备").run()
            with sqlite3.connect(self.db) as con:
                import_records([record(shift="Night")], con)
            self.app.run()
            self.clean()
            self.assertNotIn("ai_pending_question",self.app.session_state)
            self.assertFalse(self.app.session_state["ai_consent_saved"])
            ask.assert_not_called()

    def test_pending_question_survives_close_and_navigation_without_sending(self):
        with patch.object(ui, "_api_key", return_value="synthetic-key"), patch.object(ui, "ask_production") as ask:
            self.app.run().button(key="ai_launcher").click().run()
            self.app.chat_input[0].set_value("汇总当前范围").run()
            self.app.button(key="ai_close").click().run()
            self.app.radio(key="page").set_value("订单分析").run()
            self.app.button(key="ai_launcher").click().run()
            self.clean()
            self.assertIsNotNone(self.app.button(key="ai_cancel_send"))
            self.app.button(key="ai_cancel_send").click().run()
            self.assertFalse(self.app.chat_input[0].disabled)
            ask.assert_not_called()


if __name__ == "__main__":
    unittest.main()
