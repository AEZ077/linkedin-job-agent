/**
 * Cloudflare Worker مجاني (100,000 طلب/يوم مجاناً) لتشغيل GitHub Actions
 * كل 5 دقائق بالثانية بدون تأخير سيرفرات GitHub Schedule.
 *
 * خطوات التفعيل في 2 دقيقة:
 * 1. أنشئ Worker مجاني على https://dash.cloudflare.com
 * 2. الصق هذا الكود وأضف Secret باسم GITHUB_TOKEN (صلاحية repo / actions)
 * 3. أضف Cron Trigger: */5 * * * *
 */
export default {
  async scheduled(event, env, ctx) {
    const resp = await fetch(
      "https://api.github.com/repos/AEZ077/linkedin-job-agent/dispatches",
      {
        method: "POST",
        headers: {
          "Accept": "application/vnd.github+json",
          "Authorization": `Bearer ${env.GITHUB_TOKEN}`,
          "User-Agent": "cloudflare-job-hunter-trigger",
          "X-GitHub-Api-Version": "2022-11-28",
        },
        body: JSON.stringify({ event_type: "run-hunter" }),
      }
    );
    if (!resp.ok) {
      throw new Error(`GitHub dispatch failed: ${resp.status} ${await resp.text()}`);
    }
  },
};
