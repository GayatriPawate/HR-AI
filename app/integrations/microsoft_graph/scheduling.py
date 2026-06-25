import uuid
import httpx
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.integrations.microsoft_graph.auth import get_graph_token
from app.db.models import InterviewSchedule, Interview, CandidateStatus
from config.settings import get_settings

settings = get_settings()
GRAPH_BASE = "https://graph.microsoft.com/v1.0"


class GraphSchedulingService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _headers(self) -> dict:
        token = await get_graph_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    async def find_meeting_times(
        self,
        attendee_emails: list[str],
        date_from: datetime,
        date_to: datetime,
        duration_minutes: int = 60,
        timezone: str = "UTC",
    ) -> list[dict]:
        headers = await self._headers()
        organizer_email = settings.graph_organizer_email

        payload = {
            "attendees": [
                {"emailAddress": {"address": email}, "type": "Required"}
                for email in attendee_emails
            ],
            "timeConstraint": {
                "activityDomain": "work",
                "timeslots": [{
                    "start": {"dateTime": date_from.strftime("%Y-%m-%dT%H:%M:%S"), "timeZone": timezone},
                    "end":   {"dateTime": date_to.strftime("%Y-%m-%dT%H:%M:%S"),   "timeZone": timezone},
                }],
            },
            "meetingDuration": f"PT{duration_minutes}M",
            "minimumAttendeePercentage": 100,
            "isOrganizerOptional": False,
            "returnSuggestionReasons": True,
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{GRAPH_BASE}/users/{organizer_email}/findMeetingTimes",
                    headers=headers,
                    json=payload,
                )
            if resp.status_code == 200:
                data = resp.json()
                slots = []
                for suggestion in data.get("meetingTimeSuggestions", []):
                    slot = suggestion.get("meetingTimeSlot", {})
                    slots.append({
                        "start": slot.get("start", {}).get("dateTime"),
                        "end":   slot.get("end",   {}).get("dateTime"),
                        "confidence": suggestion.get("confidence", 0),
                        "suggestion_reason": suggestion.get("suggestionReason", ""),
                    })
                return slots
            else:
                raise RuntimeError(f"Graph findMeetingTimes error: {resp.status_code} {resp.text[:300]}")
        except httpx.RequestError as e:
            raise RuntimeError(f"Network error calling MS Graph: {e}")

    async def create_calendar_event(
        self,
        candidate_id: str,
        jd_id: int,
        attendee_emails: list[str],
        subject: str,
        body_html: str,
        start: datetime,
        end: datetime,
        timezone: str = "UTC",
        create_teams_meeting: bool = True,
        organizer_id: str | None = None,
    ) -> dict:
        headers = await self._headers()
        organizer_email = settings.graph_organizer_email

        event_payload = {
            "subject": subject,
            "body": {"contentType": "HTML", "content": body_html},
            "start": {"dateTime": start.strftime("%Y-%m-%dT%H:%M:%S"), "timeZone": timezone},
            "end":   {"dateTime": end.strftime("%Y-%m-%dT%H:%M:%S"),   "timeZone": timezone},
            "attendees": [
                {"emailAddress": {"address": email}, "type": "required"}
                for email in attendee_emails
            ],
            "isOnlineMeeting": create_teams_meeting,
            "onlineMeetingProvider": "teamsForBusiness" if create_teams_meeting else None,
            "allowNewTimeProposals": True,
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{GRAPH_BASE}/users/{organizer_email}/calendar/events",
                    headers=headers,
                    json=event_payload,
                )

            if resp.status_code not in (200, 201):
                raise RuntimeError(f"Graph event creation failed: {resp.status_code} {resp.text[:300]}")

            event_data = resp.json()
            online_meeting = event_data.get("onlineMeeting") or {}

            # Store schedule in DB
            schedule = InterviewSchedule(
                id=str(uuid.uuid4()),
                candidate_id=candidate_id,
                jd_id=jd_id,
                organizer_id=organizer_id or "",
                attendees=[{"email": e} for e in attendee_emails],
                scheduled_start=start,
                scheduled_end=end,
                timezone=timezone,
                graph_event_id=event_data.get("id"),
                graph_meeting_id=online_meeting.get("conferenceId"),
                teams_join_url=online_meeting.get("joinUrl"),
                location="Microsoft Teams" if create_teams_meeting else "To be confirmed",
                status="scheduled",
            )
            self.db.add(schedule)

            # Update candidate status
            await self._upsert_status(candidate_id, jd_id, "Interview Scheduled")
            await self.db.commit()
            await self.db.refresh(schedule)

            return {
                "schedule_id": schedule.id,
                "graph_event_id": event_data.get("id"),
                "teams_join_url": online_meeting.get("joinUrl"),
                "graph_meeting_id": online_meeting.get("conferenceId"),
                "web_link": event_data.get("webLink"),
                "status": "scheduled",
            }

        except httpx.RequestError as e:
            raise RuntimeError(f"Network error creating calendar event: {e}")

    async def cancel_event(self, schedule_id: str, reason: str = "") -> bool:
        result = await self.db.execute(
            select(InterviewSchedule).where(InterviewSchedule.id == schedule_id)
        )
        schedule = result.scalar_one_or_none()
        if not schedule:
            return False

        if schedule.graph_event_id:
            try:
                headers = await self._headers()
                organizer_email = settings.graph_organizer_email
                async with httpx.AsyncClient(timeout=30.0) as client:
                    await client.post(
                        f"{GRAPH_BASE}/users/{organizer_email}/calendar/events/{schedule.graph_event_id}/cancel",
                        headers=headers,
                        json={"comment": reason},
                    )
            except Exception:
                pass  # Still mark as cancelled locally

        schedule.status = "cancelled"
        schedule.cancel_reason = reason
        await self.db.commit()
        return True

    async def get_schedules(
        self,
        candidate_id: str | None = None,
        status: str | None = None,
    ) -> list[dict]:
        query = select(InterviewSchedule)
        if candidate_id:
            query = query.where(InterviewSchedule.candidate_id == candidate_id)
        if status:
            query = query.where(InterviewSchedule.status == status)
        query = query.order_by(InterviewSchedule.scheduled_start)

        result = await self.db.execute(query)
        return [
            {
                "schedule_id": s.id,
                "candidate_id": s.candidate_id,
                "jd_id": s.jd_id,
                "scheduled_start": s.scheduled_start.isoformat() if s.scheduled_start else None,
                "scheduled_end": s.scheduled_end.isoformat() if s.scheduled_end else None,
                "teams_join_url": s.teams_join_url,
                "status": s.status,
                "location": s.location,
                "attendees": s.attendees,
            }
            for s in result.scalars().all()
        ]

    async def _upsert_status(self, candidate_id: str, jd_id: int, status: str):
        result = await self.db.execute(
            select(CandidateStatus).where(
                and_(
                    CandidateStatus.candidate_id == candidate_id,
                    CandidateStatus.jd_id == jd_id,
                )
            )
        )
        rec = result.scalar_one_or_none()
        if rec:
            rec.status = status
        else:
            self.db.add(CandidateStatus(candidate_id=candidate_id, jd_id=jd_id, status=status))
