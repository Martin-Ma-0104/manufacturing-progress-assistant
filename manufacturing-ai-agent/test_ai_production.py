"""Assistant interaction regressions with synthetic SQLite and a mocked model."""
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

import ai_production_ui as ui
from ai_production_client import AgentError, DEFAULT_MODEL
from ai_production_data import query_facts
from production import import_records
from test_production import record


class AssistantUiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db_path = Path(self.temp.name) / "synthetic.db"
        with sqlite3.connect(self.db_path) as connection:
            import_records([record(machine_id="TEST1", planned_rolls=10, input_rolls=5),
                            record(machine_id="TEST2", planned_rolls=30, input_rolls=30)], connection)
        script = Path(self.temp.name) / "assistant_app.py"
        script.write_text("import ai_production_ui\nai_production_ui.render_agent(" + repr(str(self.db_path)) + ")\n")
        self.at = AppTest.from_file(str(script), default_timeout=10)

    def assert_clean(self):
        self.assertEqual(len(self.at.exception), 0)

    @staticmethod
    def fake_answer(question, snapshot, **kwargs):
        query = dict(view="overview", start_date=snapshot["scope"]["start_date"],
                     end_date=snapshot["scope"]["end_date"],
                     shift=snapshot["scope"]["shift"] or "All", machines=[],
                     metrics=["input_rolls", "attainment"])
        result = query_facts(snapshot, query)
        return dict(status="answered", model=DEFAULT_MODEL, **result,
                    usage=dict(requests=2, reported_requests=2, input_tokens=120,
                               output_tokens=30, reasoning_tokens=0, total_tokens=150))

    def test_unconfigured_keeps_local_facts_and_never_calls_model(self):
        with patch.object(ui, "_api_key", return_value=""), patch.object(ui, "ask_production") as ask:
            self.at.run()
            self.assert_clean()
            self.assertTrue(any("AI 未配置" in item.value for item in self.at.info))
            self.assertEqual(self.at.metric[1].value, "87.5%")
            self.assertTrue(self.at.chat_input[0].disabled)
            self.assertTrue(all(self.at.button(key="ai_quick_" + label).disabled for label, _ in ui.QUICK_QUESTIONS))
            self.at.checkbox(key="ai_allow_send").set_value(True).run()
            self.at.button(key="ai_refresh").click().run()
            self.assert_clean()
            ask.assert_not_called()

    def test_explicit_send_cache_and_scope_change_reset_permission(self):
        with patch.object(ui, "_api_key", return_value="synthetic-test-key"), \
                patch.object(ui, "ask_production", side_effect=self.fake_answer) as ask:
            self.at.run()
            self.assert_clean()
            self.assertFalse(self.at.checkbox(key="ai_allow_send").value)
            self.at.button(key="ai_refresh").click().run()
            ask.assert_not_called()
            self.at.checkbox(key="ai_allow_send").set_value(True).run()
            ask.assert_not_called()
            self.at.button(key="ai_quick_汇总当前范围").click().run()
            self.assert_clean()
            self.assertEqual(ask.call_count, 1)
            self.assertEqual(ask.call_args.kwargs, {"api_key": "synthetic-test-key", "consent": True})
            self.assertEqual(len(self.at.chat_message), 2)
            self.at.button(key="ai_quick_汇总当前范围").click().run()
            self.assertEqual(ask.call_count, 1)
            self.assertTrue(any("会话缓存" in item.value for item in self.at.caption))
            self.at.multiselect(key="ai_machines").set_value(["TEST1"]).run()
            self.assert_clean()
            self.assertFalse(self.at.checkbox(key="ai_allow_send").value)
            self.assertEqual(len(self.at.chat_message), 0)
            self.assertEqual(self.at.metric[1].value, "50.0%")
            self.at.multiselect(key="ai_machines").set_value([]).run()
            self.assertFalse(self.at.checkbox(key="ai_allow_send").value)
            self.assertEqual(ask.call_count, 1)

    def test_data_version_change_invalidates_answers_and_approval(self):
        with patch.object(ui, "_api_key", return_value="synthetic-test-key"), \
                patch.object(ui, "ask_production", side_effect=self.fake_answer) as ask:
            self.at.run()
            self.at.checkbox(key="ai_allow_send").set_value(True).run()
            self.at.button(key="ai_quick_汇总当前范围").click().run()
            self.assertEqual(ask.call_count, 1)
            with sqlite3.connect(self.db_path) as connection:
                import_records([record(machine_id="TEST1", shift="Night")], connection)
            self.at.button(key="ai_refresh").click().run()
            self.assert_clean()
            self.assertFalse(self.at.checkbox(key="ai_allow_send").value)
            self.assertEqual(len(self.at.chat_message), 0)
            self.assertEqual(ask.call_count, 1)

    def test_errors_are_explicit_and_not_cached(self):
        usage = dict(requests=1, reported_requests=0, input_tokens=0, output_tokens=0)
        failure = AgentError("timeout", "请求已超时，请稍后主动重试。", usage)
        with patch.object(ui, "_api_key", return_value="synthetic-test-key"), \
                patch.object(ui, "ask_production", side_effect=failure) as ask:
            self.at.run()
            self.at.checkbox(key="ai_allow_send").set_value(True).run()
            for _ in range(2):
                self.at.button(key="ai_quick_汇总当前范围").click().run()
                self.assert_clean()
            self.assertEqual(ask.call_count, 2)
            self.assertTrue(any("请求已超时" in item.value for item in self.at.error))
            self.assertTrue(any("可能产生费用" in item.value for item in self.at.caption))

    def test_new_entry_preserves_existing_navigation(self):
        with patch.object(ui, "ask_production") as ask:
            app = AppTest.from_file(str(Path(__file__).with_name("streamlit_app.py")), default_timeout=10).run()
            self.assertEqual(len(app.exception), 0)
            self.assertEqual(app.radio[0].options, ["分切生产日报", "订单分析", "数据导入", "生产分析"])
            self.assertIsNotNone(app.button(key="ai_launcher"))
            app.radio[0].set_value("订单分析").run()
            self.assertEqual(len(app.exception), 0)
            self.assertIsNotNone(app.button(key="ai_launcher"))
            ask.assert_not_called()


if __name__ == "__main__":
    unittest.main()
