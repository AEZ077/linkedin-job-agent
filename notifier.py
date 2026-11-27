"""
وحدة إرسال الإشعارات (Notifier)
تدعم تيليجرام (المجاني والفوري 100%) مع تنسيق HTML آمن، أزرار تقديم مباشر،
ودعم تقسيم الرسائل الطويلة لضمان وصول كل تفاصيل الوظيفة بدون أخطاء.
"""

import html
import os
import smtplib
import urllib.parse
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional
import requests
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_MAX_LEN = 4000


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

    @staticmethod
    def _esc(val: Any) -> str:
        return html.escape(str(val or ""), quote=False)

    def format_job_message(self, job: Dict[str, Any], evaluation: Dict[str, Any]) -> str:
        """
        تنسيق رسالة شاملة باللغة العربية تتضمن:
        اسم الوظيفة، الشركة، المكان، كل تفاصيلها، نسبة التوافق الحقيقية، ورابط التقديم المباشر.
        """
        title = self._esc(job.get("title", "وظيفة غير محددة"))
        company = self._esc(job.get("company", "شركة غير معلنة"))
        location = self._esc(job.get("location", "الموقع غير محدد"))
        company_industry = self._esc(job.get("company_industry") or evaluation.get("company_industry", ""))
        company_location = self._esc(job.get("company_location", ""))
        posted_time = self._esc(job.get("posted_time", ""))
        employment_type = self._esc(job.get("employment_type", ""))
        seniority_level = self._esc(job.get("seniority_level", ""))
        raw_desc = (job.get("description") or "").strip()
        url = job.get("job_url", "")
        is_tech = bool(job.get("is_tech", True))

        score = int(evaluation.get("match_score", 0))
        summary = self._esc(evaluation.get("arabic_summary", ""))
        raw_highlights = evaluation.get("job_highlights_ar", "")
        if isinstance(raw_highlights, list):
            highlights_ar = "\n".join(f"• {self._esc(h)}" for h in raw_highlights if h)
        else:
            highlights_ar = self._esc(raw_highlights)
        matching_skills = [self._esc(s) for s in (evaluation.get("matching_skills") or [])]
        missing_skills = [self._esc(s) for s in (evaluation.get("missing_skills") or [])]

        priority_badge = (
            "🔥 <b>أولوية قصوى: شركة في مجال التكنولوجيا (Tech)</b>\n"
            if is_tech
            else "📊 <b>فرصة في قطاع المحاسبة (Accounting)</b>\n"
        )

        meta_lines = []
        if company_industry:
            meta_lines.append(f"🏷️ <b>القطاع:</b> {company_industry}")
        if company_location:
            meta_lines.append(f"🏢 <b>مقر صفحة الشركة على LinkedIn:</b> {company_location}")
        meta_lines.append(f"📍 <b>مكان الوظيفة:</b> {location}")
        if employment_type or seniority_level:
            emp_parts = [p for p in [employment_type, seniority_level] if p]
            meta_lines.append(f"💼 <b>نوع الدوام والمستوى:</b> {' | '.join(emp_parts)}")
        if posted_time:
            meta_lines.append(f"🕒 <b>تاريخ النشر:</b> {posted_time}")

        skills_block = ""
        if matching_skills:
            skills_block += f"\n✅ <b>المهارات المتطابقة:</b> {', '.join(matching_skills[:8])}"
        if missing_skills:
            skills_block += f"\n📝 <b>مهارات يُنصح بإبرازها/مراجعتها:</b> {', '.join(missing_skills[:5])}"

        details_section = ""
        if highlights_ar:
            details_section += f"\n\n📋 <b>ملخص تفاصيل ومتطلبات الوظيفة:</b>\n{highlights_ar}"

        if raw_desc:
            # إرفاق النص الأصلي كاملاً قدر الإمكان داخل حد تيليجرام
            max_raw = 1400 if highlights_ar else 2100
            clipped = raw_desc[:max_raw]
            if len(raw_desc) > max_raw:
                clipped += "\n... (بقية التفاصيل في رابط الوظيفة)"
            details_section += f"\n\n📄 <b>النص الكامل للوصف الوظيفي:</b>\n{self._esc(clipped)}"

        header = (
            f"🎯 <b>فرصة وظيفية جديدة متطابقة على LinkedIn!</b>\n"
            f"{priority_badge}"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📌 <b>اسم الوظيفة:</b> {title}\n"
            f"🏢 <b>الشركة:</b> {company}\n"
            + "\n".join(meta_lines)
            + f"\n⭐ <b>نسبة التوافق مع الـ CV:</b> <b>{score}%</b>"
            + skills_block
            + f"\n\n💡 <b>تحليل التوافق مع سيرتك الذاتية:</b>\n{summary}"
            + details_section
            + f"\n\n🔗 <b>رابط التقديم المباشر:</b>\n{self._esc(url)}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🤖 <i>AI Job Agent • فحص فوري 24/7</i>"
        )
        return header

    def _split_message(self, message: str) -> List[str]:
        if len(message) <= TELEGRAM_MAX_LEN:
            return [message]
        chunks: List[str] = []
        remaining = message
        while remaining:
            if len(remaining) <= TELEGRAM_MAX_LEN:
                chunks.append(remaining)
                break
            split_idx = remaining.rfind("\n", 0, TELEGRAM_MAX_LEN)
            if split_idx <= 0:
                split_idx = TELEGRAM_MAX_LEN
            chunks.append(remaining[:split_idx])
            remaining = remaining[split_idx:].lstrip("\n")
        return chunks

    def send_telegram(self, message: str, job_url: str = "") -> bool:
        """
        إرسال إشعار فوري عبر Telegram Bot مع زر تقديم مباشر ودعم تقسيم الرسائل الطويلة.
        """
        if not self.telegram_token or not self.telegram_chat_id:
            print("⚠️ إعدادات تيليجرام غير مكتملة (TELEGRAM_BOT_TOKEN أو TELEGRAM_CHAT_ID مفقود).")
            return False

        url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
        chunks = self._split_message(message)

        try:
            for idx, chunk in enumerate(chunks):
                payload: Dict[str, Any] = {
                    "chat_id": self.telegram_chat_id,
                    "text": chunk,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": idx < len(chunks) - 1,
                }
                if job_url and idx == len(chunks) - 1:
                    payload["reply_markup"] = {
                        "inline_keyboard": [[{"text": "🚀 قدّم الآن على LinkedIn", "url": job_url}]]
                    }

                sent_chunk = False
                for attempt in range(3):
                    try:
                        resp = requests.post(url, json=payload, timeout=15)
                        if resp.status_code == 200 and resp.json().get("ok"):
                            sent_chunk = True
                            break
                        # إذا فشل تنسيق HTML لأي سبب، نعيد المحاولة كنص عادي
                        fallback_payload = dict(payload)
                        fallback_payload.pop("parse_mode", None)
                        resp2 = requests.post(url, json=fallback_payload, timeout=15)
                        if resp2.status_code == 200 and resp2.json().get("ok"):
                            sent_chunk = True
                            break
                        print(f"⚠️ فشل إرسال تليجرام ({resp2.status_code}): {resp2.text}")
                    except requests.RequestException as req_err:
                        if attempt < 2:
                            import time
                            time.sleep(2 * (attempt + 1))
                            continue
                        raise req_err

                if not sent_chunk:
                    return False

            print("📲 تم إرسال إشعار الوظيفة إلى تيليجرام بنجاح!")
            return True
        except Exception as e:
            print(f"❌ خطأ أثناء الاتصال بتليجرام: {e}")
            return False

    def send_callmebot(self, message: str) -> bool:
        """إرسال عبر CallMeBot WhatsApp"""
        if not self.callmebot_phone or not self.callmebot_api_key:
            return False

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

    def send_notification(self, message: str, job_url: str = "") -> bool:
        """إرسال الإشعار بالقناة المفضلة مع Fallback للكونسول"""
        if self.provider == "telegram" or (self.telegram_token and self.telegram_chat_id):
            return self.send_telegram(message, job_url=job_url)
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
