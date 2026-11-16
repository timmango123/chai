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


MINDFUL = {"id": "mindful", "title": "正念呼吸", "sources": [
    {"publisher": "國立臺灣師範大學學生事務處學生輔導中心", "name": "正念減壓療法", "url": "https://www.ntnu.edu.tw/a"},
    {"publisher": "衛生福利部 心快活心理健康學習平台", "name": "正念的應用", "url": "https://wellbeing.mohw.gov.tw/b"},
    {"publisher": "NHS (UK)", "name": "Mindfulness", "url": "https://www.nhs.uk/c"}]}
HOSPITAL = {"id": "sleep", "title": "睡眠", "sources": [
    {"publisher": "國立臺灣大學醫學院附設醫院 護理部", "name": "睡眠衛教", "url": "https://www.ntuh.gov.tw/d"}]}


class ShortSourceNameTests(RouteBase):
    """The prompt asks for a short organisation name; the invented-source check must accept one."""

    def cite(self, name, cards=(MINDFUL,)):
        from engine import knowledge
        return knowledge.invented_source(f"可以先感覺肚子的起伏（資料來源：{name}）。", list(cards))

    def test_short_names_of_a_given_publisher_are_accepted(self):
        for name in ("臺師大學輔中心", "台師大學輔中心", "師大學生輔導中心", "國立臺灣師範大學學生輔導中心",
                     "心快活", "心快活心理健康學習平台", "衛福部心快活", "NHS", "英國國民保健署"):
            self.assertFalse(self.cite(name), name)

    def test_two_given_sources_in_one_label_are_accepted(self):
        self.assertFalse(self.cite("NHS、臺師大學輔中心"))
        self.assertFalse(self.cite("臺師大學輔中心〈正念減壓療法〉"))

    def test_the_hospital_short_name_matches_its_full_name(self):
        self.assertFalse(self.cite("臺大醫院", [HOSPITAL]))
        self.assertFalse(self.cite("台大醫院護理部", [HOSPITAL]))

    def test_sources_that_were_not_given_are_still_caught(self):
        from engine import knowledge
        for name in ("哈佛大學", "WHO", "董氏基金會", "臺大醫院", "某某心理診所", "NHS、哈佛大學"):
            self.assertTrue(self.cite(name), name)
        self.assertTrue(knowledge.invented_source("WHO 建議每天練習十分鐘", [MINDFUL]))
        self.assertTrue(knowledge.invented_source("臺大醫院的研究說這很有效", [MINDFUL]))

    def test_very_short_or_unrelated_fragments_do_not_match(self):
        for name in ("大學", "中心", "心理", "清華大學諮商中心"):
            self.assertTrue(self.cite(name), name)

    def test_an_unmatched_label_is_dropped_but_a_known_other_organisation_is_not(self):
        from engine import knowledge
        garbled = "可以先感覺肚子的起伏（資料來源：某某心理診所）。分心了再帶回來。"
        cleaned = knowledge.drop_unverified_citations(garbled, [MINDFUL])
        self.assertEqual(cleaned, "可以先感覺肚子的起伏。分心了再帶回來。")
        self.assertFalse(knowledge.invented_source(cleaned, [MINDFUL]))
        harvard = "可以先感覺肚子的起伏（資料來源：哈佛大學）。"
        self.assertEqual(knowledge.drop_unverified_citations(harvard, [MINDFUL]), harvard)
        kept = "可以先感覺肚子的起伏（資料來源：臺師大學輔中心）。"
        self.assertEqual(knowledge.drop_unverified_citations(kept, [MINDFUL]), kept)

    def test_a_short_name_gets_its_link_under_the_reply(self):
        from engine import knowledge
        shown = knowledge.public_sources("可以先感覺肚子的起伏（資料來源：臺師大學輔中心）。", [MINDFUL])
        self.assertEqual([s["url"] for s in shown], ["https://www.ntnu.edu.tw/a"])


class SourceLabelTests(RouteBase):
    """The link under a reply already starts with 「資料來源：」; the publisher must not repeat it."""

    def test_the_nested_label_is_folded_into_the_agency_name(self):
        from engine import knowledge
        card = {"id": "sleep", "title": "睡眠", "sources": [
            {"publisher": "衛生福利部（資料來源：國民健康署）", "name": "好眠秘笈", "url": "https://www.hpa.gov.tw/e"}]}
        shown = knowledge.public_sources("睡前一小時先放下手機（資料來源：國民健康署）。", [card])
        self.assertEqual([s["publisher"] for s in shown], ["衛生福利部國民健康署"])

    def test_other_publisher_names_are_shown_as_written(self):
        from engine import knowledge
        for name in ("NHS (UK)", "國立臺灣師範大學學生事務處學生輔導中心", "衛生福利部 心快活心理健康學習平台"):
            self.assertEqual(knowledge.display_name(name), name)

    def test_no_real_card_shows_the_label_twice(self):
        from engine import knowledge
        for card in knowledge.cards():
            for publisher in knowledge.publishers(card):
                self.assertNotIn("資料來源", knowledge.display_name(publisher), publisher)


from unittest.mock import patch  # noqa: E402

from engine.dialogue_ai import UNAVAILABLE_LABEL  # noqa: E402
from tests.test_ai_only_v259 import Base, single  # noqa: E402

CALM = {"id": "calm-breath", "topic": "breathing", "title": "放慢呼吸", "status": "pilot",
        "keywords": ["壓力好大", "喘不過氣", "緊張"], "summary": "慢慢吐氣能讓身體放鬆。",
        "steps": ["用鼻子吸氣數到四", "嘴巴慢慢吐氣數到六"], "cautions": ["頭暈就停下來正常呼吸"],
        "when_to_seek_help": "常常喘不過氣、影響生活，請找輔導老師或醫師。", "evidence": "official_guideline",
        "sources": [{"publisher": "國立臺灣師範大學學生事務處學生輔導中心", "name": "正念減壓療法",
                     "url": "https://www.ntnu.edu.tw/a"}]}
ASK_CALM = "最近壓力好大，有什麼方法可以放鬆嗎"


class ShortSourceNamePipelineTests(Base):
    def setUp(self):
        super().setUp()
        self.enterContext(patch("engine.knowledge.cards", return_value=[CALM]))

    def test_a_reply_citing_the_short_name_is_sent_with_its_link(self):
        reply = "壓力大的時候可以先試著放慢呼吸：吸氣數到四、吐氣數到六。（資料來源：臺師大學輔中心）"
        result, _, _ = self.turn(ASK_CALM, {"return_value": single(reply)})
        self.assertEqual(result["reply"], reply)
        self.assertEqual([s["url"] for s in result["sources"]], ["https://www.ntnu.edu.tw/a"])

    def test_a_garbled_label_is_dropped_and_the_reply_still_arrives(self):
        reply = "壓力大的時候可以先試著放慢呼吸：吸氣數到四、吐氣數到六。（資料來源：某某心理診所）"
        result, _, _ = self.turn(ASK_CALM, {"return_value": single(reply)})
        self.assertNotEqual(result["model_used"], UNAVAILABLE_LABEL)
        self.assertNotIn("資料來源", result["reply"])
        self.assertIn("吸氣數到四", result["reply"])
        self.assertEqual(result["sources"], [])
        self.assertIn("citation_dropped", result["diagnostics"]["issues"])

    def test_a_known_organisation_that_was_not_given_still_stops_the_reply(self):
        for reply in ("壓力大的時候可以先放慢呼吸。（資料來源：哈佛大學）", "WHO 建議每天練習十分鐘放慢呼吸。"):
            result, _, _ = self.turn(ASK_CALM, {"return_value": single(reply)})
            self.assertEqual(result["model_used"], UNAVAILABLE_LABEL, reply)


class ShortSourceNameRealCardsTests(RouteBase):
    """On the real card set, loosened matching must not make one organisation count as another."""

    def test_no_alias_group_is_attached_to_a_different_organisation(self):
        from engine import knowledge
        allowed = {("臺大醫院", "國立臺灣大學醫學院附設醫院"), ("臺大醫院", "國立臺灣大學醫學院附設醫院 護理部")}
        publishers = sorted({p for card in knowledge.cards() for p in knowledge.publishers(card)})
        attached = {(group[0], p) for group in knowledge.ORG_GROUPS for p in publishers
                    if knowledge._in_group(p, group) and not any(alias.lower() in p.lower() for alias in group)}
        self.assertEqual(attached, allowed)

    def test_letters_are_never_abbreviated(self):
        from engine import knowledge
        self.assertFalse(knowledge._short_for("APA", "American Academy of Pediatrics"))
        self.assertFalse(knowledge._short_for("AAP", "American Academy of Sleep Medicine (AASM)"))
        self.assertTrue(knowledge._short_for("AASM", "American Academy of Sleep Medicine (AASM)"))
