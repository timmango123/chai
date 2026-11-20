# -*- coding: utf-8 -*-
"""2026-11-20：轉介單寄信。預設關閉；主機設定 SMTP 後學生才能請系統代寄，收件人只由伺服器決定
（核對過的輔導室信箱，或標示清楚的展示用信箱 DEMO_COUNSELING_EMAIL）。
smtplib 全部以假物件取代：不連網、不寄出任何信。"""
import json
import os
import smtplib
import tempfile
from pathlib import Path
from unittest.mock import patch

from engine import mailer, school_referral
from models import database
from tests.test_finals_v29 import RouteBase
from tests.test_school_referral_v29 import SCHOOLS

MAIL_ENV = ("SMTP_USER", "SMTP_PASSWORD", "SMTP_HOST", "SMTP_PORT", "SMTP_FROM", "DEMO_COUNSELING_EMAIL")
NOTE = "輔導室老師您好：我想約時間談談。可以聯絡我的方式：午休到輔導室找我。"


class MailBase(RouteBase):
    def setUp(self):
        super().setUp()
        path = Path(self.enterContext(tempfile.TemporaryDirectory())) / "schools.json"
        path.write_text(json.dumps(SCHOOLS, ensure_ascii=False), encoding="utf-8")
        self.enterContext(patch.object(school_referral, "DATA", str(path)))
        self.enterContext(patch.dict(os.environ))  # restored afterwards; the tests never see the host's settings
        for name in MAIL_ENV:
            os.environ.pop(name, None)
        self.smtp = self.enterContext(patch.object(mailer.smtplib, "SMTP"))
        self.smtp_ssl = self.enterContext(patch.object(mailer.smtplib, "SMTP_SSL"))

    def enable(self, **extra):
        os.environ.update(SMTP_USER="sender.test@example.com", SMTP_PASSWORD="app-pass-for-tests", **extra)

    def student_with_card(self):
        client, headers = self.student()
        client.post("/api/chat", headers=headers, json={"message": "我被霸凌了"})
        return client, headers

    def school(self, client, headers, name):
        return client.post("/api/school-referral", headers=headers, json={"school": name}).json["school_referral"]["school"]

    def send(self, client, headers, code, **body):
        return client.post("/api/school-referral/send", headers=headers,
                           json={"code": code, "note": NOTE, "confirmed": True, **body})

    def sent(self, server=None):
        return [call.args[0] for call in (server or self.smtp).return_value.send_message.call_args_list]


class OffByDefaultTests(MailBase):
    def test_without_settings_nothing_is_offered_or_sent(self):
        client, headers = self.student_with_card()
        verified = self.school(client, headers, "南投高中")
        self.assertEqual((verified["email"], verified["demo"], verified["can_send"]), ("counsel.test@gmail.com", False, False))
        plain = self.school(client, headers, "埔里國中")
        self.assertEqual((plain["email"], plain["mailto"], plain["demo"], plain["can_send"]), ("", "", False, False))
        self.assertEqual(self.send(client, headers, verified["code"]).status_code, 503)
        self.smtp.assert_not_called()
        self.smtp_ssl.assert_not_called()

    def test_half_a_setting_is_not_enough(self):
        for env in ({"SMTP_USER": "sender.test@example.com"}, {"SMTP_PASSWORD": "x"},
                    {"SMTP_USER": "not-an-address", "SMTP_PASSWORD": "x"}):
            with patch.dict(os.environ, env):
                self.assertFalse(mailer.configured(), env)
        with patch.dict(os.environ, {"SMTP_USER": "apikey", "SMTP_PASSWORD": "x", "SMTP_FROM": "sender.test@example.com"}):
            self.assertTrue(mailer.configured())  # a service whose login name is not an address


class DemoRecipientTests(MailBase):
    def test_an_unverified_school_shows_the_labelled_demo_mailbox(self):
        os.environ["DEMO_COUNSELING_EMAIL"] = "demo.inbox@example.com"
        client, headers = self.student_with_card()
        plain = self.school(client, headers, "埔里國中")
        self.assertEqual((plain["email"], plain["demo"], plain["can_send"]), ("demo.inbox@example.com", True, False))
        self.assertTrue(plain["mailto"].startswith("mailto:demo.inbox@example.com?subject="))
        self.assertNotIn("email_source_url", plain)                 # never presented as the school's own page
        verified = self.school(client, headers, "南投高中")
        self.assertEqual((verified["email"], verified["demo"]), ("counsel.test@gmail.com", False))

    def test_a_malformed_demo_address_is_ignored(self):
        os.environ["DEMO_COUNSELING_EMAIL"] = "not-an-address"
        client, headers = self.student_with_card()
        self.assertEqual(self.school(client, headers, "埔里國中")["email"], "")

    def test_the_page_labels_the_demo_mailbox(self):
        script = (Path(__file__).resolve().parents[1] / "static" / "js" / "school_referral.js").read_text(encoding="utf-8")
        self.assertIn("展示用信箱（不是", script)
        self.assertIn("confirm(", script)                           # the student confirms before the system sends


class SendTests(MailBase):
    def test_the_note_goes_to_the_verified_office_and_is_not_stored(self):
        self.enable()
        client, headers = self.student_with_card()
        school = self.school(client, headers, "南投高中")
        self.assertTrue(school["can_send"])
        result = self.send(client, headers, school["code"])
        self.assertEqual((result.status_code, result.json), (200, {"sent": True, "demo": False, "school": "國立南投高中"}))
        self.smtp.assert_called_once()
        self.assertEqual(self.smtp.call_args.args, ("smtp.gmail.com", 587))
        server = self.smtp.return_value
        server.starttls.assert_called_once()
        server.login.assert_called_once_with("sender.test@example.com", "app-pass-for-tests")
        (message,) = self.sent()
        self.assertEqual((message["To"], message["From"]), ("counsel.test@gmail.com", "sender.test@example.com"))
        self.assertEqual(message["Subject"], "想跟輔導室約時間談談")
        self.assertIsNone(message["Reply-To"])
        body = message.get_content()
        self.assertIn(NOTE, body)
        self.assertIn("代為寄出", body)
        self.assertIn("沒有驗證學生的身分", body)
        self.assertEqual(database.get_all_cases(), [])
        audit = json.dumps(self.admin().get("/api/audit").json, ensure_ascii=False)
        self.assertIn("school_referral_mail_sent", audit)
        self.assertIn("國立南投高中", audit)
        self.assertNotIn("counsel.test@gmail.com", audit)
        self.assertNotIn("午休到輔導室", audit)

    def test_the_recipient_never_comes_from_the_page(self):
        self.enable()
        client, headers = self.student_with_card()
        verified = self.school(client, headers, "南投高中")
        self.send(client, headers, verified["code"], email="evil@example.com", to="evil@example.com")
        self.assertEqual(self.sent()[0]["To"], "counsel.test@gmail.com")
        plain = self.school(client, headers, "埔里國中")
        self.assertFalse(plain["can_send"])
        self.assertEqual(self.send(client, headers, plain["code"], email="evil@example.com").status_code, 400)
        self.assertEqual(len(self.sent()), 1)

    def test_the_demo_mailbox_gets_a_mail_marked_as_a_demo(self):
        self.enable(DEMO_COUNSELING_EMAIL="demo.inbox@example.com")
        client, headers = self.student_with_card()
        plain = self.school(client, headers, "埔里國中")
        self.assertTrue(plain["can_send"])
        self.assertEqual(self.send(client, headers, plain["code"]).json["demo"], True)
        (message,) = self.sent()
        self.assertEqual(message["To"], "demo.inbox@example.com")
        self.assertTrue(message["Subject"].startswith("【展示】"))
        self.assertIn("不是真實的學校輔導室", message.get_content())
        self.assertIn("展示用信箱", json.dumps(self.admin().get("/api/audit").json, ensure_ascii=False))

    def test_replies_go_to_the_address_the_student_left(self):
        self.enable()
        client, headers = self.student_with_card()
        client.post("/api/onboarding", headers=headers,
                    json={"privacy_acknowledged": True, "student_email": "kid@example.com"})
        self.send(client, headers, self.school(client, headers, "南投高中")["code"])
        self.assertEqual(self.sent()[0]["Reply-To"], "kid@example.com")

    def test_what_is_refused(self):
        self.enable()
        client, headers = self.student_with_card()
        code = self.school(client, headers, "南投高中")["code"]
        for body in ({"confirmed": False}, {"confirmed": "yes"}, {"note": ""}, {"note": "   "}, {"note": 5},
                     {"note": "x" * 2001}, {"code": "../x"}, {"code": None}):
            self.assertEqual(self.send(client, headers, body.pop("code", code), **body).status_code, 400, body)
        self.assertEqual(self.send(client, headers, "ZZZZ99").status_code, 404)
        self.assertEqual(client.post("/api/school-referral/send",
                                     json={"code": code, "note": NOTE, "confirmed": True}).status_code, 403)  # no CSRF
        other, other_headers = self.student()                       # never saw the counseling card
        self.assertEqual(self.send(other, other_headers, code).status_code, 403)
        self.assertEqual(self.sent(), [])

    def test_two_mails_an_hour_for_one_conversation(self):
        self.enable()
        client, headers = self.student_with_card()
        code = self.school(client, headers, "南投高中")["code"]
        self.assertEqual([self.send(client, headers, code).status_code for _ in range(3)], [200, 200, 429])
        self.assertEqual(len(self.sent()), 2)
        other, other_headers = self.student_with_card()             # another student is not held back
        self.assertEqual(self.send(other, other_headers, code).status_code, 200)

    def test_a_failed_send_says_so_and_can_be_tried_again(self):
        self.enable()
        client, headers = self.student_with_card()
        code = self.school(client, headers, "南投高中")["code"]
        self.smtp.return_value.send_message.side_effect = smtplib.SMTPException("refused")
        failed = self.send(client, headers, code)
        self.assertEqual(failed.status_code, 502)
        self.assertIn("沒有寄出去", failed.json["error"])
        self.assertNotIn("school_referral_mail_sent", json.dumps(self.admin().get("/api/audit").json))
        self.smtp.side_effect = OSError("unreachable")              # cannot even connect
        self.assertEqual(self.send(client, headers, code).status_code, 502)
        self.smtp.side_effect = None
        self.smtp.return_value.send_message.side_effect = None
        self.assertEqual([self.send(client, headers, code).status_code for _ in range(2)], [200, 200])

    def test_port_465_uses_ssl(self):
        self.enable(SMTP_HOST="smtp.example.com", SMTP_PORT="465", SMTP_FROM="office@example.com")
        client, headers = self.student_with_card()
        self.send(client, headers, self.school(client, headers, "南投高中")["code"])
        self.smtp.assert_not_called()
        self.assertEqual(self.smtp_ssl.call_args.args, ("smtp.example.com", 465))
        self.smtp_ssl.return_value.starttls.assert_not_called()
        self.assertEqual(self.sent(self.smtp_ssl)[0]["From"], "office@example.com")
