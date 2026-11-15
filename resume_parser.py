"""
وحدة قراءة وتحليل السيرة الذاتية (Resume Parser)
تقوم باستخراج النصوص من ملف الـ PDF وتحويلها إلى بروفايل مهني منظم باستخدام Gemini.
تستخدم نظام كاش (Cache) لتجنب استهلاك التوكنز في كل ساعة إذا لم يتغير ملف الـ CV.
"""

import os
import json
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional
import pypdf
from google import genai
from google.genai import types


class ResumeParser:
    def __init__(self, cv_path: str, cache_path: Optional[str] = None):
        self.cv_path = Path(cv_path)
        if not self.cv_path.is_absolute():
            self.cv_path = Path(__file__).parent / cv_path
            
        self.cache_path = Path(cache_path) if cache_path else Path(__file__).parent / "cv_profile.json"

    def _calculate_file_hash(self) -> str:
        """حساب البصمة الرقمية للملف لمعرفة ما إذا تم تحديث الـ CV أم لا"""
        if not self.cv_path.exists():
            return ""
        hasher = hashlib.md5()
        with open(self.cv_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def extract_raw_text(self) -> str:
        """استخراج النص من ملف السيرة الذاتية سواء كان PDF أو ملف نصي (TXT / MD)"""
        if not self.cv_path.exists():
            raise FileNotFoundError(
                f"ملف السيرة الذاتية غير موجود في المسار: {self.cv_path}\n"
                f"يرجى وضع ملف الـ CV الخاص بك وتسميته '{self.cv_path.name}' أو تعديل مساره في config.yaml."
            )

        suffix = self.cv_path.suffix.lower()
        if suffix in [".txt", ".md"]:
            with open(self.cv_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read().strip()
        elif suffix == ".pdf":
            reader = pypdf.PdfReader(str(self.cv_path))
            text_parts = []
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)
            return "\n".join(text_parts).strip()
        else:
            raise ValueError(f"صيغة الملف {suffix} غير مدعومة حالياً. يرجى استخدام PDF أو TXT أو MD.")

    def get_or_parse_profile(self, gemini_api_key: Optional[str] = None) -> Dict[str, Any]:
        """جلب البروفايل من الكاش أو تحليله عبر Gemini إذا كان جديداً"""
        current_hash = self._calculate_file_hash()
        
        # 1. فحص الكاش إذا كان صالحاً ومطابقاً لملف الـ CV الحالي
        if self.cache_path.exists():
            try:
                with open(self.cache_path, "r", encoding="utf-8") as f:
                    cached_data = json.load(f)
                    if cached_data.get("_file_hash") == current_hash and "profile" in cached_data:
                        print(f"✅ تم تحميل البروفايل المحفوظ مسبقاً من الكاش ({self.cache_path.name})")
                        return cached_data["profile"]
            except Exception as e:
                print(f"⚠️ تعذر قراءة الكاش، سيتم إعادة التحليل: {e}")

        # 2. استخراج النص من ملف الـ PDF
        print(f"📄 جاري قراءة ملف السيرة الذاتية: {self.cv_path.name}...")
        raw_text = self.extract_raw_text()
        if not raw_text:
            raise ValueError("لم يتم العثور على نصوص قابلة للقراءة داخل ملف الـ PDF.")

        # 3. إذا لم يتوفر مفتاح Gemini، نرجع بروفايل أولي بسيط
        if not gemini_api_key:
            print("⚠️ لم يتم تعيين مفتاح GEMINI_API_KEY، سيتم استخدام النص الخام.")
            return {
                "name": "Candidate",
                "summary": raw_text[:500],
                "skills": [],
                "raw_text": raw_text
            }

        # 4. تحليل السيرة الذاتية عبر Gemini وتحويلها إلى بروفايل منظم
        print("🤖 جاري تحليل الـ CV وفهم المهارات والخبرات بواسطة Gemini...")
        client = genai.Client(api_key=gemini_api_key)

        prompt = f"""
أنت خبير توظيف تقني ومراجع سير ذاتية محترف.
قم بقراءة السيرة الذاتية الآتية واستخرج بروفايل مهني دقيق وواضح للمرشح بصيغة JSON حصراً، يحتوي على الحقول الآتية:
- "name": اسم المرشح
- "headline": المسمى الوظيفي الأنسب لخبرته
- "years_of_experience": تقدير سنوات الخبرة كرقم
- "top_skills": قائمة بأهم المهارات والتقنيات (اللغات، أطر العمل، الأدوات، التقنيات)
- "domain_experience": المجالات والقطاعات التي عمل بها (مثل Fintech, E-commerce, SaaS...)
- "target_roles": قائمة بأفضل المسميات الوظيفية التي تناسب خبرته الحالية
- "seniority_level": المستوى المهني (Junior, Mid-Level, Senior, Lead...)
- "brief_summary": فقرة تلخيصية مركزة من 3-4 أسطر عن أبرز نقاط قوته

نص السيرة الذاتية:
{raw_text}
"""
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )

        try:
            profile = json.loads(response.text)
        except Exception:
            profile = {
                "raw_summary": response.text,
                "raw_text": raw_text
            }

        # حفظ النتيجة في الكاش
        try:
            with open(self.cache_path, "w", encoding="utf-8") as f:
                json.dump({
                    "_file_hash": current_hash,
                    "profile": profile,
                    "raw_text": raw_text
                }, f, ensure_ascii=False, indent=2)
            print("💾 تم حفظ بروفايل الـ CV بنجاح في ملف الكاش لاستخدامه في الفحص الدوري.")
        except Exception as e:
            print(f"⚠️ فشل حفظ الكاش: {e}")

        return profile
