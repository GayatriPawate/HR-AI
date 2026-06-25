"""
Panel availability & candidate slot-booking service.

Atomic booking uses a UPDATE … WHERE status='available' AND version=<n>
pattern so two concurrent requests for the same slot result in exactly
one success and one "slot already taken" error — no separate lock table
needed, works with SQLite and PostgreSQL.
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_

from app.db.models import (
    PanelAvailabilitySlot, SlotBooking,
    Candidate, User, Interview, CandidateStatus,
)


class AvailabilityService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ── Admin: create slots ───────────────────────────────────

    async def create_slots(
        self,
        panel_user_id: str,
        slots: list[dict],
        jd_id: Optional[int],
        created_by: str,
    ) -> list[dict]:
        created = []
        for s in slots:
            slot = PanelAvailabilitySlot(
                id=str(uuid.uuid4()),
                panel_user_id=panel_user_id,
                jd_id=jd_id,
                slot_start=datetime.fromisoformat(s["slot_start"]),
                slot_end=datetime.fromisoformat(s["slot_end"]),
                status="available",
                created_by=created_by,
            )
            self.db.add(slot)
            created.append(slot)
        await self.db.commit()
        return [self._slot_dict(s) for s in created]

    # ── Admin: list slots for a panel member ─────────────────

    async def list_slots(
        self,
        panel_user_id: Optional[str] = None,
        jd_id: Optional[int] = None,
        status: Optional[str] = None,
    ) -> list[dict]:
        query = select(PanelAvailabilitySlot, User).join(
            User, PanelAvailabilitySlot.panel_user_id == User.id
        )
        if panel_user_id:
            query = query.where(PanelAvailabilitySlot.panel_user_id == panel_user_id)
        if jd_id:
            query = query.where(PanelAvailabilitySlot.jd_id == jd_id)
        if status:
            query = query.where(PanelAvailabilitySlot.status == status)
        query = query.order_by(PanelAvailabilitySlot.slot_start)
        result = await self.db.execute(query)
        rows = result.all()
        return [
            {**self._slot_dict(row[0]), "panel_name": row[1].full_name}
            for row in rows
        ]

    # ── Admin: delete an unbooked slot ───────────────────────

    async def delete_slot(self, slot_id: str) -> bool:
        result = await self.db.execute(
            select(PanelAvailabilitySlot).where(PanelAvailabilitySlot.id == slot_id)
        )
        slot = result.scalar_one_or_none()
        if not slot:
            return False
        if slot.status == "booked":
            raise ValueError("Cannot delete a booked slot")
        await self.db.delete(slot)
        await self.db.commit()
        return True

    # ── Candidate (or admin on behalf): book a slot ──────────

    async def book_slot(
        self,
        slot_id: str,
        candidate_id: str,
        jd_id: int,
        booked_by: str,
        interview_id: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> dict:
        # Read current slot to get version
        result = await self.db.execute(
            select(PanelAvailabilitySlot).where(PanelAvailabilitySlot.id == slot_id)
        )
        slot = result.scalar_one_or_none()
        if not slot:
            raise ValueError("Slot not found")
        if slot.status != "available":
            raise ValueError("Slot is no longer available")

        # Atomic update: only succeeds if status is still 'available' AND version unchanged
        update_result = await self.db.execute(
            update(PanelAvailabilitySlot)
            .where(
                and_(
                    PanelAvailabilitySlot.id == slot_id,
                    PanelAvailabilitySlot.status == "available",
                    PanelAvailabilitySlot.version == slot.version,
                )
            )
            .values(status="booked", version=slot.version + 1)
        )
        if update_result.rowcount == 0:
            raise ValueError("Slot was just taken by another booking — please choose a different slot")

        booking = SlotBooking(
            id=str(uuid.uuid4()),
            slot_id=slot_id,
            candidate_id=candidate_id,
            jd_id=jd_id,
            interview_id=interview_id,
            booked_by=booked_by,
            notes=notes,
        )
        self.db.add(booking)

        # Update candidate status to "Interview Scheduled"
        await self._upsert_candidate_status(candidate_id, jd_id, "Interview Scheduled")

        # Stamp scheduled_at on the interview if linked
        if interview_id:
            int_result = await self.db.execute(
                select(Interview).where(Interview.id == interview_id)
            )
            interview = int_result.scalar_one_or_none()
            if interview:
                interview.scheduled_at = slot.slot_start
                interview.status = "scheduled"

        await self.db.commit()

        # Return enriched booking
        cand = await self.db.get(Candidate, candidate_id)
        return {
            "id": booking.id,
            "slot_id": slot_id,
            "candidate_id": candidate_id,
            "candidate_name": cand.full_name if cand else None,
            "jd_id": jd_id,
            "slot_start": slot.slot_start.isoformat(),
            "slot_end": slot.slot_end.isoformat(),
            "booked_at": booking.booked_at.isoformat(),
            "notes": booking.notes,
        }

    # ── List bookings ─────────────────────────────────────────

    async def list_bookings(
        self,
        panel_user_id: Optional[str] = None,
        jd_id: Optional[int] = None,
        candidate_id: Optional[str] = None,
    ) -> list[dict]:
        query = (
            select(SlotBooking, PanelAvailabilitySlot, Candidate)
            .join(PanelAvailabilitySlot, SlotBooking.slot_id == PanelAvailabilitySlot.id)
            .join(Candidate, SlotBooking.candidate_id == Candidate.id)
        )
        if panel_user_id:
            query = query.where(PanelAvailabilitySlot.panel_user_id == panel_user_id)
        if jd_id:
            query = query.where(SlotBooking.jd_id == jd_id)
        if candidate_id:
            query = query.where(SlotBooking.candidate_id == candidate_id)
        query = query.order_by(PanelAvailabilitySlot.slot_start)
        result = await self.db.execute(query)
        return [
            {
                "booking_id": row[0].id,
                "slot_id": row[1].id,
                "slot_start": row[1].slot_start.isoformat(),
                "slot_end": row[1].slot_end.isoformat(),
                "panel_user_id": row[1].panel_user_id,
                "candidate_id": row[2].id,
                "candidate_name": row[2].full_name,
                "jd_id": row[0].jd_id,
                "booked_at": row[0].booked_at.isoformat(),
                "notes": row[0].notes,
            }
            for row in result.all()
        ]

    # ── Cancel a booking (frees the slot) ────────────────────

    async def cancel_booking(self, booking_id: str) -> bool:
        result = await self.db.execute(
            select(SlotBooking).where(SlotBooking.id == booking_id)
        )
        booking = result.scalar_one_or_none()
        if not booking:
            return False

        # Free the slot
        await self.db.execute(
            update(PanelAvailabilitySlot)
            .where(PanelAvailabilitySlot.id == booking.slot_id)
            .values(status="available", version=PanelAvailabilitySlot.version + 1)
        )
        await self.db.delete(booking)
        await self.db.commit()
        return True

    # ── Helpers ───────────────────────────────────────────────

    def _slot_dict(self, slot: PanelAvailabilitySlot) -> dict:
        return {
            "id": slot.id,
            "panel_user_id": slot.panel_user_id,
            "jd_id": slot.jd_id,
            "slot_start": slot.slot_start.isoformat(),
            "slot_end": slot.slot_end.isoformat(),
            "status": slot.status,
        }

    async def _upsert_candidate_status(self, candidate_id: str, jd_id: int, status: str):
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
