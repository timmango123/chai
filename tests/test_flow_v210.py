# -*- coding: utf-8 -*-
"""v2.10：依 2026-10-31 流程圖與最終計畫書——開場心情分支、對話中的 BSRS-5、紅燈 113、AI 標記絕望線索、
「不知道」時給小方法並鼓勵找人、紅燈四按鈕與一鍵隱藏的頁面元素。暫存 SQLite、假 API，不連網。"""
from pathlib import Path

from engine.dialogue_ai import prepare_dialogue
from engine.dialogue_reply import local_reply
from engine.triage import perform_triage
from models import database
from tests.test_ai_only_v259 import Base, single
from tests.test_finals_v29 import RouteBase

ROOT = Path(__file__).resolve().parents[1]


class MoodAndCheckinTests(RouteBase):
    def chat(self, client, headers, message):
        return client.post("/api/chat", headers=headers, json={"message": message}).json

    def test_a_negative_opening_mood_leads_to_the_in_chat_check_without_an_alert(self):
        client, headers = self.student()
        first = self.chat(client, headers, "我今天的心情：😢 很難過")
        self.assertIsNone(first["safety_alert"])                       # a mood alone is not a safety signal
        self.assertFalse(first["offer_chat_checkin"])
        self.chat(client, headers, "最近跟朋友吵架")
        third = self.chat(client, headers, "就覺得很煩")
        self.assertTrue(third["offer_chat_checkin"])                    # offered once, after a few turns
        self.assertFalse(self.chat(client, headers, "嗯")["offer_chat_checkin"])
        self.assertEqual(database.get_all_cases(), [])

    def test_a_happy_mood_does_not_offer_the_check(self):
        client, headers = self.student()
        for message in ("我今天的心情：😃 超開心", "今天打球贏了", "晚上要吃火鍋"):
            data = self.chat(client, headers, message)
        self.assertFalse(data["offer_chat_checkin"])

    def test_orange_offers_the_check_after_the_safety_question(self):
        client, headers = self.student()
        self.chat(client, headers, "我現在沒有想傷害自己，但昨天真的有想過")
        data = self.chat(client, headers, "有")
        self.assertTrue(data["offer_chat_checkin"])

    def test_the_in_chat_answers_are_scored_like_the_form(self):
        client, headers = self.student()
        self.chat(client, headers, "最近睡不好")
        data = client.post("/api/assessment", headers=headers, json={
            "bsrs5": {"sleep": 2, "anxiety": 1, "anger": 1, "depression": 2, "inferiority": 1, "suicide": 1},
            "category": "對話中的身心檢核"}).json
        self.assertIn("result", data)
        self.assertNotIn("勾選", data["result"]["text"])
        self.assertNotIn("分", data["result"]["text"])                  # the student never sees a score

    def test_abuse_and_gender_cases_get_113_in_the_urgent_panel(self):
        client, headers = self.student()
        self.assertTrue(self.chat(client, headers, "我爸喝醉就打人")["show_protection_line"])
        other, headers2 = self.student()
        self.assertFalse(self.chat(other, headers2, "考試好多")["show_protection_line"])


class HopelessnessTests(Base):
    """Proposal: the AI marks 無望／無助／無價值感 with the student's words; the rules decide the level."""

    def hint(self, kind, evidence):
        return {"hopelessness": {"kind": kind, "evidence": evidence}}

    def test_one_kind_is_yellow_without_a_question(self):
        text = "反正以後也不會變好"
        _, _, state = self.turn(text, {"return_value": single("聽起來你很灰心。", self.hint("hopeless", text))})
        self.assertEqual(state["risk_level"], "yellow")
        self.assertFalse(state["safety_check_required"])

    def test_three_kinds_reach_orange(self):
        state = None
        for kind, text in (("hopeless", "反正以後也不會變好"), ("helpless", "怎麼做都沒用"), ("worthless", "我就是很沒用")):
            _, _, state = self.turn(text, {"return_value": single("我在。", self.hint(kind, text))}, state)
            state = {**state, "history": state.get("history", [])}
        self.assertEqual(state["risk_level"], "orange")

    def test_a_single_cue_keeps_the_ai_reply(self):
        # 2026-10-31 live test: the level rose green → yellow after the draft was written, the draft was dropped
        # and the student saw 「AI 暫時連不上」.
        text = "反正以後也不會變好"
        reply = "聽起來你對接下來很灰心，這種感覺很沉。是什麼讓你這樣想的？"
        result, _, state = self.turn(text, {"return_value": single(reply, self.hint("hopeless", text))})
        self.assertEqual(state["risk_level"], "yellow")
        self.assertEqual(result["reply"], reply)

    def test_a_quote_not_in_the_message_is_ignored(self):
        _, _, state = self.turn("今天好累", {"return_value": single("辛苦了。", self.hint("worthless", "我很沒用"))})
        self.assertEqual(state["risk_level"], "green")


class ClarifiedHyperboleTests(Base):
    def test_a_joke_said_as_a_joke_gets_no_safety_question(self):
        text = "數學考到我想死啦（開玩笑的）"
        _, state = prepare_dialogue(text, perform_triage(text), {}, use_model=False, hour=14)
        self.assertFalse(state["safety_check_required"])
        self.assertEqual(state["risk_level"], "yellow")                # still noted for staff
        plain = "數學考到我想死啦"
        _, state = prepare_dialogue(plain, perform_triage(plain), {}, use_model=False, hour=14)
        self.assertTrue(state["safety_check_required"])                 # without the clarification: one gentle check


class DontKnowTests(Base):
    def test_repeated_dont_know_gets_small_steps_and_a_person(self):
        state = {}
        for message in ("不知道", "不知道"):
            _, state = prepare_dialogue(message, perform_triage(message), state, use_model=False, hour=14)
            state = {**state, "history": state.get("history", [])}
        reply = local_reply("不知道", state)
        self.assertIn("輔導老師", reply)
        self.assertIn("走一走", reply)


class PageElementTests(RouteBase):
    def test_the_flow_chart_controls_are_on_the_page(self):
        page = self.student()[0].get("/").get_data(as_text=True)
        for marker in ('id="hideButton"', 'id="jokeButton"', 'id="musicToggle"', 'id="puzzleOverlay"',
                       'id="urgentActions"', 'id="urgent113"', "js/flow.js", 'class="puzzle-help"',
                       'class="urgent-hide"'):
            self.assertIn(marker, page)
        script = (ROOT / "static" / "js" / "flow.js").read_text(encoding="utf-8")
        for marker in ("你好嗎？今天心情如何？", "我需要幫助", "我很安全", "幫我整理狀況", "找真人聊聊",
                       "https://page.line.me/093wgvxu", "049-2202662"):
            self.assertIn(marker, script)
