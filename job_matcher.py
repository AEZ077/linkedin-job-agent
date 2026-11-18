"""
وحدة مطابقة وتقييم الوظائف بالذكاء الاصطناعي (AI Job Matcher)
تستخدم Gemini لمقارنة الوصف الوظيفي الدقيق مع السيرة الذاتية وخبرات المرشح.
تمنح نسبة تطابق دقيقة وشرحاً توضيحياً باللغة العربية لأسباب الترشيح.
"""

import json
from typing import Dict, Any, Optional
from google import genai
from google.genai import types


class JobMatcher:
    def __init__(self, api_key: str, model_name: str = "gemini-2.5-flash", min_score: int = 75):
        self.api_key = api_key
        self.model_name = model_name
        self.min_score = min_score
        self.client = genai.Client(api_key=api_key) if api_key else None

    def evaluate_job(
        self,
        candidate_profile: Dict[str, Any],
        job_title: str,
        company: str,
        location: str,
        job_description: str
    ) -> Dict[str, Any]:
        """
        مقارنة السيرة الذاتية مع الوصف الوظيفي وإرجاع نتيجة التحليل بصيغة مهيكلة
        """
        if not self.client:
            print("⚠️ لم يتم توفير مفتاح GEMINI_API_KEY. سيتم تخطي التقييم الذكي.")
            return {
                "match_score": 50,
                "is_recommended": False,
                "arabic_summary": "لم يتم التقييم بالذكاء الاصطناعي لعدم توفر GEMINI_API_KEY",
                "matching_skills": [],
                "missing_skills": []
            }

        # اختصار الوصف الوظيفي إذا كان طويلاً جداً لتوفير الذاكرة والوقت
        trimmed_desc = job_description[:4000] if job_description else "لا يوجد وصف تفصيلي متوفر"

        prompt = f"""
أنت خبير توظيف تقني (Headhunter / Talent Matcher) بارع جداً ومحايد.
مهمتك تقييم مدى توافق هذه الوظيفة مع السيرة الذاتية وخبرات المرشح بدقة وواقعية.

--- بيانات المرشح (من السيرة الذاتية) ---
{json.dumps(candidate_profile, ensure_ascii=False, indent=2)}

--- بيانات الوظيفة المنشورة على LinkedIn ---
المسمى: {job_title}
الشركة: {company}
الموقع: {location}
الوصف الوظيفي والمتطلبات:
{trimmed_desc}

--- المطلوب منك ---
قم بتقييم التوافق وأجب بصيغة JSON حصراً بالحقول الآتية:
1. "match_score": رقم صحيح بين 0 و 100 يعبر عن النسبة الواقعية لتطابق المرشح مع المتطلبات الأساسية للوظيفة وسنوات الخبرة والتقنيات.
2. "is_recommended": boolean (true إذا كانت النسبة >= {self.min_score} والوظيفة تستحق التقديم فوراً، وإلا false).
3. "arabic_summary": ملخص مركز جداً ومشجع باللغة العربية (2 إلى 3 أسطر) يوضح سبب التوافق أو أهم النقاط المشتركة، بأسلوب موجه للمرشح مباشرة.
4. "matching_skills": قائمة بأهم المهارات المشتركة بين المرشح ومتطلبات الوظيفة.
5. "missing_skills": قائمة بالمهارات أو المتطلبات الناقصة أو التي قد يحتاج المرشح لمراجعتها قبل المقابلة (إن وجدت).

أجب بصيغة JSON فقط:
"""

        for attempt in range(2):
            try:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.2
                    )
                )

                result = json.loads(response.text)
                # التأكد من صحة الحقول
                score = int(result.get("match_score", 0))
                is_rec = result.get("is_recommended", score >= self.min_score)
                arabic_summary = result.get("arabic_summary", "")
                matching_skills = result.get("matching_skills", [])
                missing_skills = result.get("missing_skills", [])

                return {
                    "match_score": score,
                    "is_recommended": is_rec,
                    "arabic_summary": arabic_summary,
                    "matching_skills": matching_skills,
                    "missing_skills": missing_skills
                }

            except Exception as e:
                if attempt == 0:
                    import time
                    time.sleep(2)
                    continue
                print(f"❌ خطأ أثناء تقييم الوظيفة عبر Gemini ({job_title}): {e}")
                return {
                    "match_score": 0,
                    "is_recommended": False,
                    "arabic_summary": f"حدث خطأ أثناء التقييم: {e}",
                    "matching_skills": [],
                    "missing_skills": []
                }
            print(f"❌ خطأ أثناء تقييم الوظيفة عبر Gemini ({job_title}): {e}")
            return {
                "match_score": 0,
                "is_recommended": False,
                "arabic_summary": f"حدث خطأ أثناء التقييم: {e}",
                "matching_skills": [],
                "missing_skills": []
            }
