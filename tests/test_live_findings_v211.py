# -*- coding: utf-8 -*-
"""v2.11：2026-11-01 線上試用回饋——開場改為心情＋程度 1–5、拿掉長開場白與角色說明、喘口氣卡片、
輕微同儕摩擦第二次提到才出現輔導室卡片、紅燈再次出現時重新打開四個按鈕、對話會問「以前有類似經驗嗎」「打算怎麼處理」。"""
from pathlib import Path

from engine.dialogue_policy import build_state
from engine.triage import perform_triage
from tests.test_finals_v29 import RouteBase

ROOT = Path(__file__).resolve().parents[1]


class MoodStrengthTests(RouteBase):
    def chat(self, client, headers, message):
        return client.post("/api/chat", headers=headers, json={"message": message}).json

    def test_a_mood_with_strength_takes_the_negative_branch(self):
        client, headers = self.student()
        first = self.chat(client, headers, "我今天的心情：😢 難過（程度 4/5）")
        self.assertIsNone(first["safety_alert"])
        self.chat(client, headers, "最近跟朋友吵架")
        self.assertTrue(self.chat(client, headers, "就覺得很煩")["offer_chat_checkin"])

    def test_a_happy_mood_with_strength_does_not(self):
        client, headers = self.student()
        for message in ("我今天的心情：😃 開心（程度 5/5）", "今天打球贏了", "晚上要吃火鍋"):
            data = self.chat(client, headers, message)
        self.assertFalse(data["offer_chat_checkin"])


class UrgentAgainTests(RouteBase):
    def test_only_a_message_that_is_red_by_itself_reopens_the_panel(self):
        client, headers = self.student()
        post = lambda m: client.post("/api/chat", headers=headers, json={"message": m}).json
        red = post("我把藥存好了，今晚就全部吞掉")
        self.assertTrue(red["show_urgent_help"] and red["urgent_new"])
        calm = post("我現在是安全的，只是需要有人陪我聊聊")
        self.assertTrue(calm["show_urgent_help"])                        # the level stays red
        self.assertFalse(calm["urgent_new"])                             # but 「我很安全」 is not reopened


class PastAndPlanQuestionTests(RouteBase):
    def test_after_the_story_it_asks_about_before_and_then_the_plan(self):
        state = {}
        goals = []
        turns = ["我今天在學校被老師當全班的面罵，覺得很丟臉", "因為我作業沒交，可是我前一天在照顧生病的妹妹",
                 "我覺得很委屈", "有啊國小的時候也有一次", "還沒想到"]
        for message in turns:
            triage = perform_triage(text=message, previous_level="green")
            history = state.get("history", [])
            state = build_state(message, triage, state, history=history)
            goals.append(state["current_goal"])
            state["history"] = history + [{"role": "user", "text": message}, {"role": "assistant", "text": "嗯，我在聽。"}]
            state["last_reply"] = "嗯，我在聽。"
        self.assertNotEqual(goals[0], "explore_past")                   # not on the very first message
        self.assertIn("explore_past", goals)
        self.assertIn("explore_plan", goals)
        self.assertLess(goals.index("explore_past"), goals.index("explore_plan"))
        self.assertEqual(goals.count("explore_past"), 1)


class PageTests(RouteBase):
    def test_the_page_opens_with_the_mood_question_only(self):
        page = self.student()[0].get("/").get_data(as_text=True)
        self.assertNotIn("哈囉少年仔", page)
        self.assertNotIn("請當一位耐心的學長陪我聊", page)
        self.assertNotIn("雙向語音對答支援", page)
        self.assertIn('id="companionRoleNote" hidden', page)
        self.assertIn("喘口氣", page)
        header = page.split('class="nav-links"')[1].split("</div>")[0]
        self.assertNotIn("hideButton", header)                         # moved to the side card
        script = (ROOT / "static" / "js" / "flow.js").read_text(encoding="utf-8")
        for marker in ("askStrength", "（程度 ${n}/5）", "1 一點點", "5 非常強烈"):
            self.assertIn(marker, script)
        themes = (ROOT / "static" / "css" / "themes.css").read_text(encoding="utf-8")
        self.assertIn("html[data-theme] .mood-chip", themes)
        referral = (ROOT / "static" / "js" / "referral.js").read_text(encoding="utf-8")
        self.assertIn("showUrgentHelp(Boolean(data.urgent_new))", referral)


class SimulationFindingsTests(RouteBase):
    """2026-11-01 Render 擬真模擬（175 則）發現的問題。"""

    def test_a_second_mention_in_other_words_shows_the_card(self):
        from engine.school_referral import detect_topics
        for message in ("今天他們又在笑我", "今天又被取笑了", "他們笑我很胖", "被同學嘲笑"):
            self.assertEqual(detect_topics(message), ["bullying"], message)
        for message in ("笑死我了", "我們又在笑那部影片", "爸爸又在罵我", "媽媽又在笑我胖"):
            self.assertEqual(detect_topics(message), [], message)

    def test_unknown_after_the_plan_question_gets_small_steps_and_a_person(self):
        from engine.dialogue_reply import local_reply
        state = {}
        for message in ["今天在學校被老師當全班的面罵，覺得很丟臉", "因為我作業沒交，可是我前一天在照顧生病的妹妹",
                        "有啊國小的時候也有一次", "我也覺得很委屈", "不知道"]:
            history = state.get("history", [])
            state = build_state(message, perform_triage(text=message, previous_level="green"), state, history=history)
            state["history"] = history + [{"role": "user", "text": message}, {"role": "assistant", "text": "嗯。"}]
            state["last_reply"] = "嗯。"
        self.assertTrue(state["asked_plan"])
        self.assertEqual(state["current_goal"], "suggest_after_unknown")
        self.assertNotIn("give_advice", state["forbidden_actions"])
        reply = local_reply("不知道", state)
        self.assertIn("輔導老師", reply)
        state["history"] += [{"role": "user", "text": "不知道"}]
        again = build_state("不知道", perform_triage(text="不知道", previous_level="green"), state, history=state["history"])
        self.assertEqual(again["current_goal"], "respect_boundary")      # once; then it stops pushing

    def test_a_blocked_privacy_reply_sends_the_reviewed_text(self):
        from engine import dialogue_ai
        state = build_state("你會跟我爸媽講嗎", perform_triage(text="你會跟我爸媽講嗎"), {})
        self.assertEqual(state["current_goal"], "establish_safety")
        self.assertIn("establish_safety", dialogue_ai.REVIEWED_FALLBACK_GOALS)
        source = (ROOT / "engine" / "dialogue_ai.py").read_text(encoding="utf-8")
        self.assertIn('"model_used": "對話規則回覆", "fallback_reason": status', source)
