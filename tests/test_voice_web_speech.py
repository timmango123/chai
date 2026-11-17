# -*- coding: utf-8 -*-
"""朗讀只用瀏覽器內建的 Web Speech API：雲端語音的端點、設定與前端路徑都已移除，AI 回覆文字不再傳給語音服務。
暫存 SQLite、不連網。"""
import unittest
from pathlib import Path

from config import Config
from tests.test_finals_v29 import RouteBase

ROOT = Path(__file__).resolve().parents[1]


class CloudVoiceRemovedTests(RouteBase):
    def test_cloud_voice_endpoints_are_gone(self):
        client, headers = self.student()
        self.assertEqual(client.get("/api/tts/voices").status_code, 404)
        self.assertEqual(client.post("/api/tts", headers=headers, json={"text": "你好", "voice": "x"}).status_code, 404)

    def test_no_cloud_voice_settings_remain(self):
        self.assertFalse((ROOT / "engine" / "tts.py").exists())
        for name in ("TTS_ENABLED", "AZURE_SPEECH_KEY", "AZURE_SPEECH_REGION", "TTS_CALLS_PER_MINUTE"):
            self.assertFalse(hasattr(Config, name), name)


class PageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
        cls.app_js = (ROOT / "static" / "js" / "app.js").read_text(encoding="utf-8")

    def test_voice_dialog_stays(self):
        for control in ('id="voiceDialog"', 'id="voiceSettingsBtn"', 'id="voiceSelect"', 'id="voiceRate"',
                        'id="voicePreview"'):
            self.assertIn(control, self.html)

    def test_page_reads_aloud_with_the_browser_voice_only(self):
        self.assertIn("SpeechSynthesisUtterance", self.app_js)
        self.assertIn("speechChunks(text)", self.app_js)  # long replies are queued as short sentences
        for gone in ("/api/tts", "playCloud", "cloudVoices", "new Audio("):
            self.assertNotIn(gone, self.app_js)
        self.assertNotIn("雲端語音", self.html)


if __name__ == "__main__":
    unittest.main()
