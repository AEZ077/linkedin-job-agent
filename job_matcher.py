"""
وحدة مطابقة وتقييم الوظائف بالذكاء الاصطناعي (AI Job Matcher)
تستخدم Gemini لمقارنة الوصف الوظيفي الدقيق مع السيرة الذاتية وخبرات المرشح.
تمنح نسبة تطابق حقيقية وشرحاً وتلخيصاً شاملاً لتفاصيل الوظيفة باللغة العربية.
"""

import json
import time
from typing import Dict, Any, List
from google import genai
from google.genai import types


class JobMatcher:
    def __init__(
        self,
        api_key: str,
        model_name: str = "gemini-3.5-flash-lite",
        min_score: int = 65,
    ):
        self.api_key = api_key
        self.model_name = model_name
        self.min_score = min_score
        self.client = genai.Client(api_key=api_key) if api_key else None

    def _fallback_evaluate(
        self,
        candidate_profile: Dict[str, Any],
        job_title: str,
        job_description: str,
        reason: str = "",
    ) -> Dict[str, Any]:
        """تقييم احتياطي موضوعي عند تعذر الاتصال بـ Gemini يعتمد على تطابق المهارات والمجالات."""
        text_blob = f"{job_title} {job_description}".lower()
        skills: List[str] = candidate_profile.get("top_skills", []) + [
            "saas", "erp", "account management", "customer success",
            "retention", "crm", "b2b", "kpi", "onboarding", "sales",
            "team lead", "business development", "customer experience",
        ]
        matched = []
        for s in skills:
            s_clean = s.strip()
            if s_clean and s_clean.lower() in text_blob and s_clean not in matched:
                matched.append(s_clean)

        # حساب نسبة واقعية بين 55 و 92 بناءً على تطابق المهارات والمسمى
        score = min(92, 55 + len(matched) * 5)
        summary = (
            f"تتطابق الوظيفة ({job_title}) مع خبرتك في إدارة الحسابات ونجاح العملاء والـ B2B SaaS/ERP."
            if matched
            else f"المسمى الوظيفي ({job_title}) ضمن تخصصك المستهدف."
        )
        if reason:
            summary += f" (تقييم تلقائي: {reason})"

        return {
            "match_score": score,
            "is_recommended": score >= self.min_score,
            "arabic_summary": summary,
            "job_highlights_ar": "",
            "matching_skills": matched[:8],
            "missing_skills": [],
        }

    def evaluate_job(
        self,
        candidate_profile: Dict[str, Any],
        job_title: str,
        company: str,
        location: str,
        job_description: str,
        company_industry: str = "",
    ) -> Dict[str, Any]:
        """
        مقارنة السيرة الذاتية مع الوصف الوظيفي وإرجاع نتيجة التحليل بصيغة مهيكلة.
        """
        if not self.client:
            return self._fallback_evaluate(
                candidate_profile,
                job_title,
                job_description,
                reason="لم يتم توفير GEMINI_API_KEY",
            )

        trimmed_desc = job_description[:5000] if job_description else "لا يوجد وصف تفصيلي متوفر"

        prompt = f"""
أنت خبير توظيف (Headhunter / Talent Matcher) دقيق وموضوعي جداً.
مهمتك تقييم مدى توافق هذه الوظيفة مع السيرة الذاتية للمرشح بدقة وواقعية (بدون مجاملة أو تثبيت رقم عشوائي).

--- بيانات المرشح (من السيرة الذاتية) ---
{json.dumps(candidate_profile, ensure_ascii=False, indent=2)}

--- بيانات الوظيفة المنشورة على LinkedIn ---
المسمى: {job_title}
الشركة: {company}
القطاع: {company_industry or 'غير محدد'}
الموقع: {location}
الوصف الوظيفي والمتطلبات:
{trimmed_desc}

--- المطلوب ---
أجب بصيغة JSON حصراً بالحقول الآتية:
1. "match_score": رقم صحيح بين 0 و 100 يعبر بصدق ودقة عن نسبة التوافق بين خبرات المرشح (7+ سنوات B2B SaaS/ERP، إدارة الحسابات، نجاح العملاء، قيادة فرق المبيعات، CRM، الاحتفاظ بالعملاء) ومتطلبات هذه الوظيفة.
2. "is_recommended": boolean (true إذا كانت النسبة >= {self.min_score}، وإلا false).
3. "arabic_summary": ملخص واضح ومباشر بالعربية (2 إلى 3 أسطر) يشرح سبب نسبة التوافق وأقوى نقاط التلاقي أو الفجوات.
4. "job_highlights_ar": تلخيص شامل ومنظم بالعربية لأهم تفاصيل الوظيفة (المسؤوليات الرئيسية + الشروط والمتطلبات + المزايا إن وجدت) في نقاط واضحة.
5. "matching_skills": قائمة بأهم المهارات المشتركة بين المرشح والوظيفة.
6. "missing_skills": قائمة بالمهارات أو الشروط المطلوبة في الوظيفة وغير واضحة في السيرة الذاتية (إن وجدت).

أجب بصيغة JSON فقط:
"""

        last_err = ""
        for attempt in range(2):
            try:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.2,
                    ),
                )
                result = json.loads(response.text)
                score = max(0, min(100, int(result.get("match_score", 0))))
                return {
                    "match_score": score,
                    "is_recommended": bool(result.get("is_recommended", score >= self.min_score)),
                    "arabic_summary": result.get("arabic_summary", ""),
                    "job_highlights_ar": result.get("job_highlights_ar", ""),
                    "matching_skills": result.get("matching_skills", []) or [],
                    "missing_skills": result.get("missing_skills", []) or [],
                }
            except Exception as e:
                last_err = str(e)
                if attempt == 0:
                    time.sleep(2)
                    continue

        print(f"⚠️ تعذر التقييم عبر Gemini ({job_title}): {last_err}")
        return self._fallback_evaluate(candidate_profile, job_title, job_description)
