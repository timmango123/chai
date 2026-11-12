"""介面版型切換與投票：每台裝置一票、可改票、需要 CSRF、版型名稱白名單，頁面有載入版型檔。"""
import os
import tempfile
import unittest

_test_db = tempfile.NamedTemporaryFile(prefix="anla-test-", suffix=".db", delete=False)
_test_db.close()
os.environ["DATABASE_PATH"] = _test_db.name
os.environ["LLM_PROVIDER"] = "builtin"

from config import Config  # noqa: E402

Config.DATABASE_PATH = _test_db.name
Config.LLM_PROVIDER = "builtin"

import app as app_module  # noqa: E402
from models import database  # noqa: E402

app = app_module.app


class UiVoteTests(unittest.TestCase):
    def setUp(self):
        database.init_db()
        conn = database.get_connection()
        conn.execute("DELETE FROM ui_votes")
        conn.commit()
        conn.close()
        self.client = app.test_client()
        self.client.get("/")
        with self.client.session_transaction() as sess:
            self.token = sess["csrf_token"]

    def vote(self, layout, voter="device-aaaaaaaaaaaaaaaa", csrf=True):
        headers = {"X-UI-Voter": voter}
        if csrf:
            headers["X-CSRF-Token"] = self.token
        return self.client.post("/api/ui-vote", json={"layout": layout}, headers=headers)

    def test_page_loads_layout_switcher(self):
        html = self.client.get("/").get_data(as_text=True)
        self.assertIn("css/layouts.css", html)
        self.assertIn("js/layout.js", html)
        # 原有求助電話與按鈕仍在頁面上（版型只搬位置，不刪功能）
        for marker in ('href="tel:1925"', 'href="tel:119"', 'id="headerReferralButton"', 'id="userInput"'):
            self.assertIn(marker, html)

    def test_empty_tally_lists_every_layout(self):
        data = self.client.get("/api/ui-vote").get_json()
        self.assertEqual(data["counts"], {"classic": 0, "focus": 0, "rail": 0, "app": 0})
        self.assertEqual(data["total"], 0)
        self.assertIsNone(data["mine"])

    def test_one_vote_per_device_and_can_change(self):
        self.assertEqual(self.vote("focus").status_code, 200)
        data = self.vote("rail").get_json()
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["counts"]["rail"], 1)
        self.assertEqual(data["counts"]["focus"], 0)
        self.assertEqual(data["mine"], "rail")
        data = self.vote("rail", voter="device-bbbbbbbbbbbbbbbb").get_json()
        self.assertEqual(data["counts"]["rail"], 2)
        self.assertEqual(data["total"], 2)

    def test_requires_csrf(self):
        self.assertEqual(self.vote("focus", csrf=False).status_code, 403)
        self.assertEqual(self.client.get("/api/ui-vote").get_json()["total"], 0)

    def test_rejects_unknown_layout(self):
        self.assertEqual(self.vote("<script>").status_code, 400)
        self.assertEqual(self.vote(None).status_code, 400)

    def test_voter_id_is_not_stored_raw(self):
        self.vote("app", voter="device-cccccccccccccccc")
        conn = database.get_connection()
        rows = [r["voter_hash"] for r in conn.execute("SELECT voter_hash FROM ui_votes")]
        conn.close()
        self.assertEqual(len(rows), 1)
        self.assertNotIn("device-cccccccccccccccc", rows[0])

    def test_can_be_switched_off(self):
        original = app_module.UI_VOTE_ENABLED
        app_module.UI_VOTE_ENABLED = False
        try:
            self.assertEqual(self.client.get("/api/ui-vote").status_code, 404)
            self.assertIn('data-ui-vote="0"', self.client.get("/").get_data(as_text=True))
        finally:
            app_module.UI_VOTE_ENABLED = original


if __name__ == "__main__":
    unittest.main()
