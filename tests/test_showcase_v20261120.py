# -*- coding: utf-8 -*-
"""2026-11-20：展示後台（/showcase）。學生頁有「學生端／展示後台」切換；展示後台免密碼、唯讀，
只用 data/mock_cases.json 的虛構案例，絕不讀出真實個案，也不寫資料庫或操作紀錄。"""
from app import MOCK_CASES, app
from models import database
from tests.test_finals_v29 import RouteBase


class ShowcaseTests(RouteBase):
    def test_student_page_has_the_switch(self):
        html = app.test_client().get("/").get_data(as_text=True)
        self.assertIn('class="view-switch"', html)
        self.assertIn('href="/showcase"', html)

    def test_showcase_opens_without_login_and_is_marked(self):
        res = app.test_client().get("/showcase")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn("展示用後台", html)
        self.assertIn("window.ANLA_SHOWCASE = true", html)
        self.assertNotIn('action="/logout"', html)
        self.assertNotIn('id="staffPanel"', html)  # no admin panels in the showcase

    def test_only_fictional_cases_never_real_ones(self):
        client, headers = self.student()
        client.post("/api/chat", headers=headers, json={"message": "我想自殺，今晚就想結束"})
        real = {c["case_id"] for c in database.get_all_cases()}
        data = app.test_client().get("/api/showcase/cases").get_json()
        self.assertEqual(data["count"], len(MOCK_CASES))
        ids = {c["case_id"] for c in data["cases"]}
        self.assertTrue(all(i.startswith("DEMO-") for i in ids))
        self.assertFalse(ids & real)
        self.assertEqual(app.test_client().get(f"/api/showcase/cases/{next(iter(real))}").status_code, 404) if real else None

    def test_filters_detail_and_stats(self):
        c = app.test_client()
        reds = c.get("/api/showcase/cases?risk=red").get_json()["cases"]
        self.assertTrue(reds and all(x["risk_level"] == "red" for x in reds))
        pending = c.get("/api/showcase/cases?status=pending").get_json()["cases"]
        self.assertTrue(pending and all(x["status"] not in ("reviewing", "contacted", "completed") for x in pending))
        detail = c.get(f"/api/showcase/cases/{reds[0]['case_id']}").get_json()["case"]
        self.assertEqual(detail["case_id"], reds[0]["case_id"])
        stats = c.get("/api/showcase/stats").get_json()
        self.assertEqual(stats["total"], len(MOCK_CASES))
        self.assertTrue(c.get("/api/showcase/stats/breakdown").get_json()["groups"])

    def test_showcase_writes_nothing_and_real_apis_stay_locked(self):
        c = app.test_client()
        c.get("/api/showcase/cases")
        c.get("/api/showcase/cases/DEMO-R01")
        self.assertEqual(database.get_all_cases(), [])
        self.assertEqual(database.recent_audit_logs(100), [])
        self.assertEqual(c.get("/api/cases").status_code, 401)
        self.assertIn(c.post("/api/showcase/cases/DEMO-R01/status", json={}).status_code, (404, 405))
