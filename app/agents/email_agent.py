"""
EmailInviteAgent — composes a professional interview invitation email
and sends it via Microsoft Graph (Outlook) on behalf of the organizer.
"""
import httpx
from groq import AsyncGroq
from app.integrations.microsoft_graph.auth import get_graph_token
from config.settings import get_settings

settings = get_settings()
GRAPH_BASE = "https://graph.microsoft.com/v1.0"


class EmailInviteAgent:
    def __init__(self, groq_client: AsyncGroq):
        self.client = groq_client

    # ── LLM: compose the email body ───────────────────────────────
    async def compose_email(
        self,
        candidate_name: str,
        position_title: str,
        interview_date: str,
        interview_time: str,
        duration_minutes: int,
        interviewer_names: list[str],
        teams_join_url: str | None,
        company_name: str = "HR Platform",
        extra_notes: str = "",
    ) -> dict:
        interviewers = ", ".join(interviewer_names) if interviewer_names else "the interview panel"
        join_section = (
            f"\n\nMicrosoft Teams Meeting Link: {teams_join_url}"
            if teams_join_url
            else "\n\nThe meeting details will be shared separately."
        )

        prompt = f"""You are an HR coordinator. Write a professional, warm interview invitation email.

Details:
- Candidate Name: {candidate_name}
- Position: {position_title}
- Date: {interview_date}
- Time: {interview_time}
- Duration: {duration_minutes} minutes
- Interviewers: {interviewers}
- Teams Join URL: {teams_join_url or 'TBD'}
- Company: {company_name}
- Extra notes from HR: {extra_notes or 'None'}

Return ONLY a JSON object with two keys:
{{
  "subject": "<email subject line>",
  "body_html": "<full HTML email body — use <p>, <b>, <br> tags, include all details, Teams link, and a professional sign-off>"
}}"""

        response = await self.client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
            max_tokens=1024,
            response_format={"type": "json_object"},
        )

        import json
        content = response.choices[0].message.content.strip()
        return json.loads(content)

    # ── Graph: send email via Outlook ─────────────────────────────
    async def send_email(
        self,
        to_email: str,
        subject: str,
        body_html: str,
        cc_emails: list[str] | None = None,
    ) -> dict:
        token = await get_graph_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        organizer_email = settings.graph_organizer_email

        message = {
            "message": {
                "subject": subject,
                "body": {"contentType": "HTML", "content": body_html},
                "toRecipients": [
                    {"emailAddress": {"address": to_email}}
                ],
                "ccRecipients": [
                    {"emailAddress": {"address": e}} for e in (cc_emails or [])
                ],
            },
            "saveToSentItems": True,
        }

        async with httpx.AsyncClient(timeout=30.0) as http:
            resp = await http.post(
                f"{GRAPH_BASE}/users/{organizer_email}/sendMail",
                headers=headers,
                json=message,
            )

        if resp.status_code == 202:
            return {"status": "sent", "to": to_email}
        raise RuntimeError(
            f"Graph sendMail failed: {resp.status_code} — {resp.text[:300]}"
        )

    # ── Convenience: compose + send in one call ───────────────────
    async def compose_and_send(
        self,
        to_email: str,
        candidate_name: str,
        position_title: str,
        interview_date: str,
        interview_time: str,
        duration_minutes: int,
        interviewer_names: list[str],
        teams_join_url: str | None = None,
        company_name: str = "HR Platform",
        extra_notes: str = "",
        cc_emails: list[str] | None = None,
    ) -> dict:
        composed = await self.compose_email(
            candidate_name=candidate_name,
            position_title=position_title,
            interview_date=interview_date,
            interview_time=interview_time,
            duration_minutes=duration_minutes,
            interviewer_names=interviewer_names,
            teams_join_url=teams_join_url,
            company_name=company_name,
            extra_notes=extra_notes,
        )
        result = await self.send_email(
            to_email=to_email,
            subject=composed["subject"],
            body_html=composed["body_html"],
            cc_emails=cc_emails,
        )
        return {**result, "subject": composed["subject"], "body_html": composed["body_html"]}
