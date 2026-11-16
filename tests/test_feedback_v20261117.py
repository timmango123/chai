# -*- coding: utf-8 -*-
"""2026-11-17 試用回饋：
1. 輸入框上方的「目前先以安全為優先」提示列移除。
2. 「真人求助」展開成生命線 LINE、真人專線、求救小卡，原本的轉介單保留。
3. 「這些心事不用一個人扛」不再出現在打招呼的回覆下面。
4. 語音、主題、風格、手機安裝收進頁首「更多」。
5. 頁尾競賽名稱與左下角浮動鈕移除。
6. 自殺危險辨識太遲鈍：補上漏判的說法；同一段對話第二次出現隱晦說法就升到橙色。
句子皆為虛構；暫存 SQLite、不連網。"""
import re
import unittest
from pathlib import Path

from engine.dialogue_policy import build_state, observe_safety, raise_triage
from engine.rules import analyze_crisis_rules
from engine.triage import RISK_LEVEL_WEIGHTS, perform_triage
from tests.test_finals_v29 import RouteBase

ROOT = Path(__file__).resolve().parents[1]


def level(message, previous=None):
    triage = perform_triage(text=message)
    return raise_triage(triage, observe_safety(message, triage, previous or {}))["level"]


# Wordings that were green (no reaction at all) before this round.
DIRECT = [
    "不想活", "活不下去了", "我活不下去", "不想存在了", "希望自己沒有出生", "要是沒被生下來就好了", "我不該存在",
    "想消失", "想從這個世界消失", "想離開這個世界", "活著好痛苦", "死掉就不用煩了", "死了就解脫了", "死了比較輕鬆",
    "我死了你們會不會後悔", "想一了百了", "沒有活下去的理由", "找不到活下去的理由", "希望一覺不醒", "我想結束這一切",
    "我在查怎麼死比較不痛", "在查安眠藥要吃幾顆才會死", "吃幾顆藥會死", "從幾樓跳下去會死", "我在想要怎麼死",
    "已經想好要怎麼死了", "想跳下去", "好想從這裡跳下去", "看到車子就想衝出去", "站在月台邊會想跳下去",
    "最近一直想到死", "腦中一直有死的念頭", "常常想如果死了會怎樣", "我想自我了斷", "想尋短", "謝謝你，永別了",
    "我想傷害我自己", "想打自己", "我又割了", "自殺", "想suicide", "我要去死", "去死好了", "乾脆死掉算了", "我想要死",
    "我是不是死掉比較好", "我是不是不該活著", "我不配活著", "我不值得活著", "像我這種人死了最好", "我這種人不該存在",
    "大家都希望我去死", "死給你看", "我要死給他們看", "希望有車撞我", "希望生病死掉", "得癌症死掉就好了",
    "睡覺時死掉就好了",
]
IMPLICIT = [
    "活著幹嘛", "活著到底要幹嘛", "活著有什麼意義", "覺得活著沒意思", "生無可戀", "了無生趣", "萬念俱灰",
    "不想再撐了", "我真的撐不住了", "希望明天不要來", "沒有明天就好了", "想永遠睡下去", "想睡了就不要起來",
    "好想結束這種生活", "我不想再這樣下去了", "人生沒希望了", "沒人會在意我死活", "我消失了也沒人發現",
    "世界少我一個也沒差", "反正我也活不久了", "我想去找過世的阿嬤", "想去陪天上的媽媽", "下輩子不要當人了",
    "重新投胎算了", "想重開", "我想登出人生", "我想從人生畢業", "想讓痛苦停止",
]
# Look-alikes: none may reach orange (a yellow check is allowed for none of these either).
SAFE = [
    "哈囉，今天好嗎？", "今天好嗎", "我今天很開心", "作業好多寫不完", "想消失一下，去露營", "手機快沒電了，要死了",
    "這遊戲我死了好幾次", "笑死", "想登出遊戲了", "我要下線了，晚安", "想重開一局", "我想畢業了，高三好累",
    "謝謝你陪我，我要去睡了", "想休息了", "活著的意義是什麼，老師出的作文題目", "我阿嬤過世了，好想她",
    "我在橋上看風景", "我現在在頂樓曬衣服", "想跳下去游泳", "我想結束這段感情", "想結束這個話題", "我吃了感冒藥",
    "明天不要來學校了，放假", "希望明天不要下雨", "我想走了，補習要遲到了", "下輩子想當貓", "我沒救了，數學完全不會",
    "人生好難", "沒有手機我活不下去", "這題要怎麼死背", "下課想衝出去買飲料", "想打自己的電動", "我又割了草",
    "不該活在過去", "我不是不想活動，只是很累", "尷尬到想原地消失", "阿公生病死掉了，我很難過",
]


class LexiconTests(unittest.TestCase):
    def test_direct_wordings_that_were_missed_now_reach_orange(self):
        missed = [s for s in DIRECT if RISK_LEVEL_WEIGHTS[level(s)] < RISK_LEVEL_WEIGHTS["orange"]]
        self.assertEqual(missed, [])

    def test_implicit_wordings_that_were_missed_now_get_a_gentle_check(self):
        missed = [s for s in IMPLICIT if RISK_LEVEL_WEIGHTS[level(s)] < RISK_LEVEL_WEIGHTS["yellow"]]
        self.assertEqual(missed, [])
        triage = perform_triage(text="生無可戀")
        self.assertTrue(observe_safety("生無可戀", triage, {})["pending_safety_check"])

    def test_look_alikes_stay_calm(self):
        raised = [(s, level(s)) for s in SAFE if level(s) != "green"]
        self.assertEqual(raised, [])

    def test_a_reversed_will_sentence_is_red(self):
        self.assertEqual(level("我寫好遺書了"), "red")

    def test_asking_is_not_denying(self):
        # 「是不是」 was read as the negation 「不是」 and the sentence dropped.
        self.assertTrue(analyze_crisis_rules("我是不是死掉比較好")["has_self_harm_signal"])
        # A real denial is still a denial.
        self.assertFalse(analyze_crisis_rules("我沒有不想活")["has_self_harm_signal"])
        self.assertFalse(analyze_crisis_rules("我不是想自殺")["has_self_harm_signal"])

    def test_someone_elses_words_are_still_third_party(self):
        self.assertFalse(analyze_crisis_rules("新聞說他不想活了")["has_self_harm_signal"])


class RepeatedImplicitCueTests(unittest.TestCase):
    def test_second_implicit_wording_in_one_conversation_goes_to_orange(self):
        first = "活著有什麼意義"
        triage = raise_triage(perform_triage(text=first), observe_safety(first, perform_triage(text=first), {}))
        self.assertEqual(triage["level"], "yellow")
        state = build_state(first, triage, {}, history=[])
        self.assertEqual(state["implicit_cues"], 1)
        # An unrelated turn in between does not reset the count.
        middle = "今天段考考完了"
        state = build_state(middle, perform_triage(text=middle, previous_level="yellow"), state)
        second = "生無可戀"
        safety = observe_safety(second, perform_triage(text=second), state)
        self.assertEqual(safety["minimum_level"], "orange")
        self.assertIn("SIG-02", safety["theoretical_basis"])

    def test_one_implicit_wording_alone_stays_a_gentle_check(self):
        self.assertEqual(level("好想解脫"), "yellow")

    def test_hyperbole_does_not_count_as_an_implicit_cue(self):
        first = "熱到想死"
        state = build_state(first, perform_triage(text=first), {}, history=[])
        self.assertEqual(state.get("implicit_cues", 0), 0)


class TrustedNudgeTimingTests(RouteBase):
    def chat(self, client, headers, message):
        return client.post("/api/chat", headers=headers, json={"message": message}).json

    def test_a_greeting_never_gets_the_nudge(self):
        client, headers = self.student()
        self.chat(client, headers, "我今天的心情：😢 很難過")
        self.assertFalse(self.chat(client, headers, "哈囉，今天好嗎？")["encourage_trusted_people"])

    def test_an_early_worry_waits_until_the_third_message(self):
        client, headers = self.student()
        self.assertFalse(self.chat(client, headers, "最近都睡不著")["encourage_trusted_people"])
        self.assertFalse(self.chat(client, headers, "一直在想段考的事")["encourage_trusted_people"])
        self.assertTrue(self.chat(client, headers, "爸媽也一直唸我")["encourage_trusted_people"])

    def test_a_calm_conversation_never_gets_it(self):
        client, headers = self.student()
        for message in ("哈囉", "今天打球贏了", "晚上要吃火鍋", "明天要去校外教學"):
            self.assertFalse(self.chat(client, headers, message)["encourage_trusted_people"])

    def test_a_new_conversation_starts_the_wait_again(self):
        client, headers = self.student()
        for message in ("最近都睡不著", "一直在想段考的事", "爸媽也一直唸我"):
            self.chat(client, headers, message)
        self.assertEqual(client.post("/api/chat/reset", headers=headers, json={}).status_code, 200)
        self.assertFalse(self.chat(client, headers, "哈囉，今天好嗎？")["encourage_trusted_people"])


class PageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
        cls.app_js = (ROOT / "static" / "js" / "app.js").read_text(encoding="utf-8")
        cls.layout_js = (ROOT / "static" / "js" / "layout.js").read_text(encoding="utf-8")

    def test_safety_style_note_is_gone(self):
        self.assertNotIn("styleSafetyNote", self.html)
        self.assertNotIn("目前先以安全為優先", self.app_js)
        self.assertNotIn("styleSafetyNote", self.app_js)

    def test_header_settings_are_inside_the_more_menu(self):
        more = re.search(r'<details class="header-more" id="headerMore">(.*?)</details>\s*</div>\s*</div>\s*</nav>',
                         self.html, re.S)
        self.assertIsNotNone(more)
        for control in ('id="ttsToggleBtn"', 'id="voiceSettingsBtn"', 'id="themeSelect"', 'id="replyStyleMenu"',
                        'id="installButton"', 'id="layoutSwitchButton"'):
            self.assertIn(control, more.group(1))
            self.assertEqual(self.html.count(control), 1)
        # The nickname badge and the main links stay in the header itself.
        self.assertNotIn('id="studentIdentityBadge"', more.group(1))
        self.assertNotIn('id="newConversationButton"', more.group(1))

    def test_help_tile_offers_line_phones_card_and_keeps_the_referral(self):
        fold = re.search(r'<details class="[^"]*side-tile-help[^"]*" id="helpFold">(.*?)</details>', self.html, re.S)
        self.assertIsNotNone(fold)
        body = fold.group(1)
        self.assertIn("https://line.me/R/ti/p/%40taiwanlifeline1995", body)
        self.assertIn('rel="noopener noreferrer"', body)
        for phone in ("tel:1995", "tel:1925", "tel:1980"):
            self.assertIn(phone, body)
        self.assertIn('id="sosCardButton"', body)
        self.assertIn('id="sidebarHelpButton"', body)
        self.assertIn("window.AnlaNextSteps.openHelp()", body)          # the existing referral flow is kept
        self.assertLess(body.index("lifelineLineLink"), body.index("help-option-phones"))
        self.assertLess(body.index("help-option-phones"), body.index("sosCardButton"))

    def test_sos_card_is_made_on_the_device_only(self):
        self.assertIn('id="sosDialog"', self.html)
        script = (ROOT / "static" / "js" / "sos_card.js").read_text(encoding="utf-8")
        self.assertNotIn("fetch(", script)
        self.assertNotIn("XMLHttpRequest", script)
        self.assertIn("119", script)
        self.assertIn("/static/js/sos_card.js", (ROOT / "static" / "sw.js").read_text(encoding="utf-8"))

    def test_footer_and_floating_button(self):
        self.assertNotIn("山城數位黑客松暨第四屆麥克松科技競賽", self.html)
        self.assertIn("團隊名稱：AI 來尬聊", self.html)
        self.assertNotIn("document.body.appendChild(voteToggle)", self.layout_js)
        css = (ROOT / "static" / "css" / "layouts.css").read_text(encoding="utf-8")
        self.assertIn(".ui-vote-toggle, .layout-drawer-vote { display: none !important; }", css)


if __name__ == "__main__":
    unittest.main()
