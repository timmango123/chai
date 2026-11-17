# -*- coding: utf-8 -*-
"""2026-11-17 使用者反饋（對話步調）：
1. 不固定問「以前有類似經驗嗎」，也不立即問「打算怎麼處理」；先了解最掛心的部分，之後才簡短問一次要不要一起想辦法。
2. 「不知道」「嗯」「有啊」不等於同意接受建議；出現一次或多次「不知道」都不自動改成給建議。
3. 學生明確問做法時可以直接協助；說只想說說就繼續聽。
4. 「有過」不接「你很堅強」「你一路走過來」。
5. 安全訊號優先；安全提醒另起一段。
句子皆為虛構；不連網、不呼叫模型。"""
import unittest

from engine.dialogue_ai import REVIEWED_FALLBACK_GOALS, REWRITE_PROBLEMS, SYSTEM_PROMPT, unavailable_reply
from engine.dialogue_policy import build_state
from engine.dialogue_reply import local_reply, response_violations
from engine.triage import perform_triage

STORY = ["我今天在學校被老師當全班的面罵，覺得很丟臉", "因為我作業沒交，可是我前一天在照顧生病的妹妹",
         "最難受的是全班都在看我", "回家以後還是一直想到那個畫面"]
REMOVED_GOALS = ("explore_past", "explore_plan", "suggest_after_unknown")


def run(turns, assistant="嗯，我在聽。"):
    """Rule-only replay. `assistant=None` feeds the local reply back as the assistant turn."""
    state, steps = {}, []
    for message in turns:
        history = state.get("history", [])
        state = build_state(message, perform_triage(text=message, previous_level="green"), state, history=history)
        reply = local_reply(message, state)
        steps.append((state["current_goal"], state["ask_question"], reply))
        said = assistant or reply
        state["history"] = history + [{"role": "user", "text": message}, {"role": "assistant", "text": said}]
        state["last_reply"] = said
    return state, steps


class PacingTests(unittest.TestCase):
    def test_no_fixed_past_or_plan_questions(self):
        _, steps = run(STORY + ["有過", "還沒想到", "不知道"])
        for goal, _, reply in steps:
            self.assertNotIn(goal, REMOVED_GOALS)
            for phrase in ("以前有遇過", "怎麼撐過來", "打算怎麼處理"):
                self.assertNotIn(phrase, reply)

    def test_concern_first_then_one_offer(self):
        _, steps = run(STORY)
        goals = [(goal, ask) for goal, ask, _ in steps]
        self.assertNotIn(goals[0][0], ("explore_concern", "offer_next_step"))   # not on the very first message
        self.assertEqual(goals[1:], [("explore_concern", True), ("explore_concern", False), ("offer_next_step", True)])
        self.assertIn("最讓你掛心的是哪一部分", steps[1][2])
        self.assertNotIn("？", steps[2][2])                                     # the answer gets a response, no new question
        self.assertIn("只想先說說也可以", steps[3][2])
        self.assertEqual(steps[3][2].count("？"), 1)
        _, later = run(STORY + ["就覺得很不公平", "老師根本沒問我原因"])
        self.assertEqual([goal for goal, _, _ in later].count("offer_next_step"), 1)   # asked once only

    def test_offer_waits_after_two_questioning_replies(self):
        _, steps = run(STORY[:3], assistant="聽起來很不好受。你願意多說一點嗎？")
        self.assertFalse(steps[-1][1])                                         # rest turn: no third question in a row

    def test_a_plain_yes_to_the_offer_gets_one_small_step(self):
        for yes in ("好啊", "要", "可以啊", "想聽", "幫我想"):
            state, steps = run(STORY + [yes])
            self.assertEqual(steps[-1][0], "support_choice", yes)
            self.assertNotIn("give_advice", state["forbidden_actions"])

    def test_short_answers_are_not_consent_to_advice(self):
        for answer in ("不知道", "嗯", "有啊", "還好", "有過"):
            state, steps = run(STORY + [answer])
            self.assertNotEqual(steps[-1][0], "support_choice", answer)
            self.assertIn("give_advice", state["forbidden_actions"], answer)
            self.assertFalse(state["advice_request"], answer)

    def test_yes_counts_only_right_after_the_offer(self):
        state, steps = run(STORY[:2] + ["好啊"])
        self.assertNotEqual(steps[-1][0], "support_choice")
        self.assertIn("give_advice", state["forbidden_actions"])

    def test_explicit_request_is_helped_without_exploring_first(self):
        state, steps = run(["我跟我媽吵架了，我該怎麼跟她道歉？"])
        self.assertEqual(steps[0][0], "support_choice")
        self.assertNotIn("give_advice", state["forbidden_actions"])

    def test_good_news_is_not_asked_what_weighs_most(self):
        _, steps = run(["我今天的心情：😃 開心（程度 5/5）", "羽球比賽拿到第二名", "教練還稱讚我"])
        for goal, _, reply in steps:
            self.assertNotIn(goal, ("explore_concern", "offer_next_step"))
            self.assertNotIn("掛心", reply)

    def test_just_talking_keeps_listening_and_is_not_offered_help(self):
        state, steps = run(STORY[:3] + ["我只是想說說而已", "然後今天回家我媽又唸我", "她每次都這樣"])
        self.assertEqual(steps[3][0], "keep_listening")
        self.assertNotIn("？", steps[3][2])
        self.assertTrue(state["just_talk"])
        self.assertNotIn("offer_next_step", [goal for goal, _, _ in steps])
        self.assertIn("give_advice", state["forbidden_actions"])


class UnknownTests(unittest.TestCase):
    def test_unknown_never_switches_to_advice(self):
        state, steps = run(STORY + ["不知道", "不知道", "不知道", "不知道"])
        last = steps[-4:]
        self.assertEqual([(goal, ask) for goal, ask, _ in last],
                         [("ease_unknown", False), ("ease_unknown", True), ("respect_boundary", False),
                          ("respect_boundary", False)])
        self.assertIn("都不是也可以", last[1][2])                                # two tentative readings, once
        for _, _, reply in last:
            for advice in ("輔導老師", "走一走", "喝點水", "寫下", "可以試"):
                self.assertNotIn(advice, reply)
        self.assertIn("give_advice", state["forbidden_actions"])

    def test_longer_ways_of_saying_unknown_are_eased_too(self):
        for answer in ("還沒想到", "我也不知道耶", "沒頭緒"):
            state, steps = run(STORY[:2] + [answer])
            self.assertEqual(steps[-1][:2], ("ease_unknown", False), answer)
            self.assertIn("give_advice", state["forbidden_actions"])

    def test_blocked_model_reply_on_these_turns_uses_the_reviewed_text(self):
        for goal in ("ease_unknown", "keep_listening"):
            self.assertIn(goal, REVIEWED_FALLBACK_GOALS)


class OutputCheckTests(unittest.TestCase):
    def test_having_been_there_is_not_praised_as_overcoming(self):
        state, _ = run(STORY[:2])
        state = build_state("有過", perform_triage(text="有過", previous_level="green"), state, history=state["history"])
        for reply in ("原來以前也有過，你很堅強。", "你一路走過來，真的不容易。", "那次你也撐過來了。"):
            self.assertIn("unearned_praise", response_violations(reply, state, "有過"), reply)
        self.assertNotIn("unearned_praise", response_violations("原來以前也遇過類似的事。", state, "有過"))
        self.assertIn("unearned_praise", REWRITE_PROBLEMS)

    def test_the_students_own_words_may_be_reflected(self):
        message = "上次我也是自己撐過來的"
        state = build_state(message, perform_triage(text=message), {})
        self.assertNotIn("unearned_praise", response_violations("那次是你自己撐過來的。", state, message))


class OneQuestionTests(unittest.TestCase):
    """Replies below are from the 2026-11-18 live rounds (fictional students)."""

    def trim(self, reply, budget=1):
        from engine.dialogue_reply import one_question
        return one_question(reply, budget)

    def test_an_option_list_after_the_question_is_dropped(self):
        reply = ("生氣，又夾著一點難過，兩種都在，很可以理解。\n\n這整件事裡，哪一部分最讓你放不下？"
                 "是那句「只會滑手機」，還是吵起來的那個當下，或是別的？都不是也可以，照你的感覺說就好。")
        self.assertEqual(self.trim(reply), "生氣，又夾著一點難過，兩種都在，很可以理解。\n\n這整件事裡，哪一部分最讓你放不下？")

    def test_an_earlier_guess_becomes_a_statement_and_the_real_question_stays(self):
        reply = "昨天吵得那麼兇，媽媽還那樣說你，會不會有點不被看見？不知道我有沒有猜對。現在想起這件事，心裡比較像是什麼感覺？"
        fixed = self.trim(reply)
        self.assertEqual(fixed.count("？"), 1)
        self.assertIn("也許有點不被看見。", fixed)
        self.assertTrue(fixed.endswith("心裡比較像是什麼感覺？"))

    def test_any_other_earlier_question_is_dropped(self):
        reply = "這件事聽起來不太好受。你當時有跟誰說嗎？後來心裡比較明顯的是什麼感覺？"
        self.assertEqual(self.trim(reply), "這件事聽起來不太好受。後來心裡比較明顯的是什麼感覺？")

    def test_left_alone_when_there_is_nothing_to_fix(self):
        one = "被罵的當下，你心裡比較像是什麼感覺？"
        options = "這整件事裡，是便當被弄掉、他笑的樣子，還是別的地方讓你最不舒服？"
        quoted = "他問你「你到底在幹嘛？」的時候，會不會有點被嚇到？那時候你怎麼回？"
        short = "嗯？怎麼了？"
        for reply in (one, options, quoted, short):
            self.assertEqual(self.trim(reply), reply)
        two = "會不會有點累？要不要先停一下？"
        self.assertEqual(self.trim(two, budget=0), two)                       # budget 0 keeps its own trimming

    def test_the_reply_path_applies_it_except_for_the_rational_format(self):
        from pathlib import Path
        source = (Path(__file__).resolve().parents[1] / "engine" / "dialogue_ai.py").read_text(encoding="utf-8")
        self.assertIn('model["reply"] = one_question(model["reply"], state["max_questions"])', source)
        self.assertIn('single = state.get("effective_style") != "rational"', source)
        safety = source.split('if state["safety_check_required"]:\n        # The reviewed text is the reference')[1]
        self.assertNotIn("one_question", safety.split("    if model:\n        model[\"reply\"] = tidy_surface")[0])


class SafetyTests(unittest.TestCase):
    def test_a_safety_signal_interrupts_the_exploration(self):
        state, steps = run(STORY[:2] + ["我把藥存好了，今晚就全部吞掉"])
        self.assertEqual(steps[-1][0], "safety_support")
        self.assertTrue(state["safety_override"])
        self.assertIn("119", steps[-1][2])

    def test_a_low_mood_strength_does_not_lower_safety(self):
        state, steps = run(["我今天的心情：😢 難過（程度 1/5）", "我不想活了"])
        self.assertTrue(state["safety_check_required"])
        self.assertEqual(steps[-1][0], "safety_support")

    def test_the_safety_reminder_is_its_own_paragraph(self):
        _, steps = run(["熱到想死", "沒有啦我開玩笑的"], assistant=None)
        reply = steps[-1][2]
        general, reminder = reply.split("\n\n")
        self.assertNotIn("1925", general)
        self.assertIn("1925", reminder)
        notice, numbers = unavailable_reply("timeout").split("\n\n")
        self.assertNotIn("119", notice)
        self.assertIn("119", numbers)
        for reply in (reply, unavailable_reply("timeout")):
            for promise in ("絕對保密", "已通知", "已經通知"):
                self.assertNotIn(promise, reply)


class PromptTests(unittest.TestCase):
    def test_prompt_carries_the_feedback(self):
        for phrase in ("不進行諮商、輔導或診斷", "照自己的步調", "2–4 個短句、約 40–100 字",
                       "不立即問他打算怎麼處理，也不固定問以前有沒有類似經驗", "不重問學生已經回答過的內容",
                       "只回應、不提問也可以", "不必先完成情緒探索", "願不願意一起想辦法",
                       "不一次列出好幾種方法，不說這樣做一定有用", "不等於同意接受建議",
                       "都不自動改成給建議", "都不是", "不把猜測當成事實", "持續時間",
                       "不代表某種行為或安全程度", "不推論他已經成功克服", "不每輪加鼓勵口號或制式安慰",
                       "不等情緒探索完成", "安全提醒或求助資訊要另起一段",
                       "整則回覆最多一個問號", "不替學生補上他沒說的前情或細節", "只挑最貼近他問題的一個做法", "不承諾絕對保密、不說已通知任何人"):
            self.assertIn(phrase, SYSTEM_PROMPT, phrase)

    def test_prompt_no_longer_carries_the_old_flow(self):
        for phrase in (*REMOVED_GOALS, "那時候是怎麼撐過來的", "這一輪一定要問", "給一兩個貼合他說過的事",
                       "再次不知道就停止深入", "也可提供最多兩個簡單選項", "你撐了好幾天"):
            self.assertNotIn(phrase, SYSTEM_PROMPT, phrase)


if __name__ == "__main__":
    unittest.main()
