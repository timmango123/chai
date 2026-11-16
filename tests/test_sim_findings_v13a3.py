# -*- coding: utf-8 -*-
"""2026-11-16 線上模擬回饋：檢核答得很輕時不說「不太好受」、字條主題認得「我弟／我媽」、
重新整理後告知對話仍保留。暫存 SQLite、本機回覆，不連網。"""
from app import assessment_feedback, draft_topics
from tests.test_finals_v29 import RouteBase

LIGHT = {"sleep": 0, "anxiety": 1, "anger": 2, "depression": 0, "inferiority": 0, "suicide": 0}


class LightCheckinWordingTests(RouteBase):
    def test_a_light_score_at_yellow_is_not_told_it_looks_unwell(self):
        feedback = assessment_feedback({"bsrs_details": {"total_score": 3, "suicide_score": 0}}, "yellow")
        self.assertNotIn("不太好受", feedback["text"])
        self.assertIn("困擾還算輕", feedback["text"])
        self.assertFalse(feedback["ask_safety"])

    def test_a_moderate_score_at_yellow_keeps_the_original_wording(self):
        feedback = assessment_feedback({"bsrs_details": {"total_score": 8, "suicide_score": 0}}, "yellow")
        self.assertIn("不太好受", feedback["text"])

    def test_a_suicide_answer_still_asks_about_safety_even_with_a_light_total(self):
        feedback = assessment_feedback({"bsrs_details": {"total_score": 3, "suicide_score": 1}}, "yellow")
        self.assertIn("你現在安全嗎", feedback["text"])
        self.assertTrue(feedback["ask_safety"])

    def test_other_levels_are_unchanged_by_a_light_total(self):
        for level, phrase in (("green", "撐得住"), ("orange", "不是你一個人要扛"), ("red", "119")):
            text = assessment_feedback({"bsrs_details": {"total_score": 3, "suicide_score": 0}}, level)["text"]
            self.assertIn(phrase, text)

    def test_the_route_never_shows_a_score_for_light_answers(self):
        client, headers = self.student()
        data = client.post("/api/assessment", headers=headers, json={"bsrs5": LIGHT, "category": "家裡"}).json
        self.assertNotIn("分", data["result"]["text"])
        self.assertNotIn("不太好受", data["result"]["text"])
        self.assertIsNone(data["safety_alert"])


class NoteTopicTests(RouteBase):
    @staticmethod
    def context(*messages):
        return {"dialogue_state": {"history": [{"role": "user", "text": m} for m in messages]}, "draft": {}}

    def test_a_brother_and_mother_make_the_note_about_family_first(self):
        topics = draft_topics(self.context("我弟又偷用我的平板還把我的遊戲存檔蓋掉，我媽只會叫我讓他，超不公平"))
        self.assertEqual(topics.split("、")[0], "家人")
        self.assertIn("遊戲", topics)

    def test_family_is_not_added_twice_when_already_named(self):
        topics = draft_topics(self.context("我媽和爸媽都要我讀護理，可是我想讀設計"))
        self.assertNotIn("家人", topics)
        self.assertIn("爸媽", topics)

    def test_no_family_topic_without_family_words(self):
        self.assertEqual(draft_topics(self.context("下禮拜段考，數學都看不懂")), "段考、數學")


class ResumeNoticeTests(RouteBase):
    def test_state_reports_whether_a_conversation_is_kept(self):
        client, headers = self.student()
        self.assertFalse(client.get("/api/chat/state").json["has_conversation"])
        client.post("/api/chat", headers=headers, json={"message": "最近和同學吵架，心情有點悶"})
        self.assertTrue(client.get("/api/chat/state").json["has_conversation"])


class NotFoundAndIconTests(RouteBase):
    def test_a_mistyped_page_gets_a_way_back_and_the_help_lines(self):
        client, _ = self.student()
        res = client.get("/no-such-page")
        html = res.get_data(as_text=True)
        self.assertEqual(res.status_code, 404)
        self.assertIn("找不到這個頁面", html)
        self.assertIn('href="/"', html)
        self.assertIn("tel:1925", html)
        self.assertIn("tel:119", html)
        self.assertNotIn("The requested URL", html)

    def test_an_unknown_api_path_answers_in_json(self):
        client, _ = self.student()
        res = client.get("/api/no-such-thing")
        self.assertEqual(res.status_code, 404)
        self.assertIn("error", res.get_json())

    def test_the_site_icon_is_served(self):
        client, _ = self.student()
        res = client.get("/favicon.ico")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.mimetype, "image/png")
        res.close()
