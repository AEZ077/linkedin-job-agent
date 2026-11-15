"""
وحدة إرسال الإشعارات (Notifier)
تدعم تيليجرام (الأكثر استقراراً ومجاني 100%)، واتساب، والإيميل.
"""

import os
import smtplib
import urllib.parse
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, Optional
import requests


class JobNotifier:
    def __init__(
        self,
        provider: str = "telegram",
        telegram_token: Optional[str] = None,
        telegram_chat_id: Optional[str] = None,
        callmebot_phone: Optional[str] = None,
        callmebot_api_key: Optional[str] = None,
    ):
        self.provider = provider.lower()
        self.telegram_token = telegram_token or os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        self.telegram_chat_id = telegram_chat_id or os.getenv("TELEGRAM_CHAT_ID", "").strip()
        self.callmebot_phone = callmebot_phone or os.getenv("CALLMEBOT_PHONE", "").strip()
        self.callmebot_api_key = callmebot_api_key or os.getenv("CALLMEBOT_API_KEY", "").strip()
        self.email_to = os.getenv("EMAIL_TO", "ahmed.eidibrahimali@gmail.com").strip()
        self.email_from = os.getenv("EMAIL_FROM", "").strip()
        self.email_password = os.getenv("EMAIL_APP_PASSWORD", "").strip()

    def format_job_message(self, job: Dict[str, Any], evaluation: Dict[str, Any]) -> str:
        """
        تنسيق رسالة جذابة ومنظمة باللغة العربية مع رابط التقديم المباشر
        """
        title = job.get("title", "وظيفة غير محددة")
        company = job.get("company", "شركة غير معلنة")
        location = job.get("location", "الموقع غير محدد")
        posted_time = job.get("posted_time", "")
        url = job.get("job_url", "")
        score = evaluation.get("match_score", 0)
        summary = evaluation.get("arabic_summary", "")
        matching_skills = evaluation.get("matching_skills", [])

        time_line = f"🕒 <b>تاريخ النشر:</b> {posted_time}\n" if posted_time else ""
        skills_text = ""
        if matching_skills:
            skills_text = f"\n✅ <b>المهارات المتطابقة:</b> {', '.join(matching_skills[:5])}"

        message = (
            f"🎯 <b>فرصة وظيفية جديدة متطابقة على LinkedIn!</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📌 <b>المسمى الوظيفي:</b> {title}\n"
            f"🏢 <b>الشركة:</b> {company}\n"
            f"📍 <b>الموقع:</b> {location}\n"
            f"{time_line}"
            f"⭐ <b>نسبة التطابق مع الـ CV:</b> {score}%\n"
            f"{skills_text}\n\n"
            f"💡 <b>رأي الذكاء الاصطناعي:</b>\n"
            f"{summary}\n\n"
            f"🔗 <b>رابط التقديم المباشر على لينكدإن:</b>\n"
            f"{url}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🤖 <i>تم الفحص والإرسال تلقائياً بواسطة AI Job Agent</i>"
        )
        return message

    def send_telegram(self, message: str) -> bool:
        """
        إرسال إشعار فوري عبر Telegram Bot (الخيار الأفضل والمجاني الرسمي)
        """
        if not self.telegram_token or not self.telegram_chat_id:
            print("⚠️ إعدادات تيليجرام غير مكتملة (TELEGRAM_BOT_TOKEN أو TELEGRAM_CHAT_ID مفقود).")
            return False

        url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
        payload = {
            "chat_id": self.telegram_chat_id,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": False
        }

        try:
            resp = requests.post(url, json=payload, timeout=15)
            if resp.status_code == 200 and resp.json().get("ok"):
                print("📲 تم إرسال إشعار الوظيفة إلى تليجرام بنجاح!")
                return True
            else:
                print(f"⚠️ فشل إرسال تليجرام ({resp.status_code}): {resp.text}")
                return False
        except Exception as e:
            print(f"❌ خطأ أثناء الاتصال بتليجرام: {e}")
            return False

    def send_callmebot(self, message: str) -> bool:
        """إرسال عبر CallMeBot WhatsApp"""
        if not self.callmebot_phone or not self.callmebot_api_key:
            return False

        # تحويل وسوم HTML إلى تنسيق واتساب العادي
        wa_text = message.replace("<b>", "*").replace("</b>", "*")
        wa_text = wa_text.replace("<i>", "_").replace("</i>", "_")

        phone = self.callmebot_phone.replace(" ", "").replace("-", "")
        encoded_text = urllib.parse.quote(wa_text)
        url = f"https://api.callmebot.com/whatsapp.php?phone={phone}&text={encoded_text}&apikey={self.callmebot_api_key}"

        try:
            resp = requests.get(url, timeout=20)
            if resp.status_code == 200 and "Message" in resp.text:
                print(f"📲 تم إرسال رسالة واتساب بنجاح ({phone})")
                return True
            else:
                return False
        except Exception as e:
            print(f"❌ خطأ واتساب: {e}")
            return False

    def send_email(self, message: str, subject: str = "🎯 وظيفة جديدة متطابقة على LinkedIn") -> bool:
        """إرسال إشعار عبر البريد الإلكتروني (Gmail)"""
        if not self.email_from or not self.email_password:
            return False

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.email_from
            msg["To"] = self.email_to

            html_content = f"""
            <div dir="rtl" style="font-family: Arial, sans-serif; line-height: 1.6; color: #222; max-width: 600px; padding: 20px; border: 1px solid #ddd; border-radius: 8px;">
                {message.replace(chr(10), '<br>')}
            </div>
            """
            msg.attach(MIMEText(html_content, "html", "utf-8"))

            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(self.email_from, self.email_password)
                server.sendmail(self.email_from, self.email_to, msg.as_string())

            print(f"📧 تم إرسال إشعار الوظيفة إلى بريدك الإلكتروني ({self.email_to})")
            return True
        except Exception as e:
            print(f"❌ خطأ أثناء إرسال الإيميل: {e}")
            return False

    def send_notification(self, message: str) -> bool:
        """إرسال الإشعار بالقناة المفضلة مع Fallback للكونسول"""
        if self.provider == "telegram" or (self.telegram_token and self.telegram_chat_id):
            return self.send_telegram(message)
        elif self.provider == "email" or (self.email_from and self.email_password):
            return self.send_email(message)
        elif self.provider == "callmebot" and self.callmebot_api_key:
            return self.send_callmebot(message)
        else:
            self._print_console_fallback(message)
            return True

    def _print_console_fallback(self, message: str):
        clean_text = message.replace("<b>", "").replace("</b>", "").replace("<i>", "").replace("</i>", "")
        print("\n" + "=" * 60)
        print("📢 [معاينة إشعار الوظيفة]")
        print("=" * 60)
        print(clean_text)
        print("=" * 60 + "\n")


WhatsAppNotifier = JobNotifier

