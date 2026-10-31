# -*- coding: utf-8 -*-
"""v2.10：計畫書四類危機詞表擴充（自傷自殺、校園霸凌、性平、家暴兒虐）＋青少年常見寫法與防誤判句。
只看規則與對話政策（不靠 AI）。句子全部虛構，見 tests/crisis_lexicon_corpus.py。"""
import unittest

from engine.dialogue_ai import prepare_dialogue
from engine.school_referral import detect_topics
from engine.triage import perform_triage
from tests.crisis_lexicon_corpus import CASES, NO_CARD

WEIGHTS = {"green": 0, "yellow": 1, "orange": 2, "red": 3}


def judge(text):
    _, state = prepare_dialogue(text, perform_triage(text), {}, use_model=False, hour=14)
    return state["risk_level"], detect_topics(text)


class CrisisLexiconTests(unittest.TestCase):
    def test_every_crisis_wording_reaches_its_level(self):
        missed = []
        for text, topic, need in CASES:
            if topic == "none":
                continue
            level, topics = judge(text)
            card = topic not in ("bullying", "gender") or text in NO_CARD or topics
            if WEIGHTS[level] < WEIGHTS[need] or not card:
                missed.append(f"{topic}: {text} → {level} {topics}（需要 {need}）")
        self.assertEqual(missed, [])

    def test_look_alikes_raise_no_alarm(self):
        alarms = []
        for text, topic, _ in CASES:
            if topic != "none":
                continue
            level, topics = judge(text)
            if WEIGHTS[level] >= WEIGHTS["orange"] or topics:
                alarms.append(f"{text} → {level} {topics}")
        self.assertEqual(alarms, [])

    def test_the_corpus_covers_every_topic(self):
        counts = {}
        for _, topic, _ in CASES:
            counts[topic] = counts.get(topic, 0) + 1
        for topic, minimum in (("suicide", 50), ("bullying", 25), ("gender", 20), ("abuse", 20), ("none", 30)):
            self.assertGreaterEqual(counts.get(topic, 0), minimum, topic)

    def test_hitting_at_home_is_not_school_bullying(self):
        self.assertEqual(detect_topics("回家又要被揍了"), [])
        self.assertEqual(detect_topics("在學校被打"), ["bullying"])


if __name__ == "__main__":
    unittest.main()
