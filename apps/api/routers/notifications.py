"""Notification routers for email recipients, SMTP config, scheduling, and test sends."""

from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator

from apps.api.dependencies import MarketDep
from src.notifications.service import NotificationService

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])

_service = NotificationService()

# Deliberately permissive RFC-5322-ish check: the project keeps the dependency
# surface small (no email-validator), and delivery is the real proof of validity.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")


def _check_email(value: str) -> str:
    value = value.strip()
    if not _EMAIL_RE.match(value):
        raise ValueError(f"invalid email address: {value!r}")
    return value


class RecipientCreate(BaseModel):
    email: str
    name: str | None = None

    @field_validator("email")
    @classmethod
    def _valid_email(cls, v: str) -> str:
        return _check_email(v)


class RecipientUpdate(BaseModel):
    is_active: bool


class SmtpConfigIn(BaseModel):
    smtp_server: str = "smtp.gmail.com"
    smtp_port: int = 587
    sender_email: str
    sender_password: str = Field(..., description="Gmail App Password or SMTP password")
    sender_name: str = "DTCK Market Intel"
    use_tls: bool = True
    use_ssl: bool = False

    @field_validator("sender_email")
    @classmethod
    def _valid_sender(cls, v: str) -> str:
        return _check_email(v)


class ScheduleConfigIn(BaseModel):
    morning_hour: int = Field(8, ge=0, le=23)
    morning_minute: int = Field(0, ge=0, le=59)
    afternoon_hour: int = Field(15, ge=0, le=23)
    afternoon_minute: int = Field(30, ge=0, le=59)
    days_of_week: str = "mon-fri"
    is_enabled: bool = True


class SendTestRequest(BaseModel):
    recipient_email: str
    subject: str | None = None

    @field_validator("recipient_email")
    @classmethod
    def _valid_recipient(cls, v: str) -> str:
        return _check_email(v)



# --- Recipients ---
@router.get("/recipients")
def list_recipients(active_only: bool = False) -> list[dict[str, Any]]:
    return _service.get_recipients(active_only=active_only)


@router.post("/recipients", status_code=status.HTTP_201_CREATED)
def add_recipient(payload: RecipientCreate) -> dict[str, Any]:
    return _service.add_recipient(email=payload.email, name=payload.name)


@router.patch("/recipients/{recipient_id}")
def update_recipient(recipient_id: str, payload: RecipientUpdate) -> dict[str, Any]:
    ok = _service.update_recipient(recipient_id, is_active=payload.is_active)
    if not ok:
        raise HTTPException(status_code=404, detail="Recipient not found")
    return {"success": True}


@router.delete("/recipients/{recipient_id}")
def delete_recipient(recipient_id: str) -> dict[str, Any]:
    ok = _service.delete_recipient(recipient_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Recipient not found")
    return {"success": True}


# --- SMTP Settings ---
@router.get("/smtp")
def get_smtp_config() -> dict[str, Any]:
    return _service.get_smtp_config()


@router.post("/smtp")
def save_smtp_config(payload: SmtpConfigIn) -> dict[str, Any]:
    return _service.save_smtp_config(
        smtp_server=payload.smtp_server,
        smtp_port=payload.smtp_port,
        sender_email=payload.sender_email,
        sender_password=payload.sender_password,
        sender_name=payload.sender_name,
        use_tls=payload.use_tls,
        use_ssl=payload.use_ssl,
    )


# --- Schedule Settings ---
@router.get("/schedule")
def get_schedule_config() -> dict[str, Any]:
    return _service.get_schedule_config()


@router.post("/schedule")
def save_schedule_config(payload: ScheduleConfigIn) -> dict[str, Any]:
    return _service.save_schedule_config(
        morning_hour=payload.morning_hour,
        morning_minute=payload.morning_minute,
        afternoon_hour=payload.afternoon_hour,
        afternoon_minute=payload.afternoon_minute,
        days_of_week=payload.days_of_week,
        is_enabled=payload.is_enabled,
    )


# --- Send Test & Dispatch ---
@router.post("/send-test")
def send_test_email(payload: SendTestRequest, market_dep: MarketDep) -> dict[str, Any]:
    res = _service.dispatch_report(
        market_service=market_dep,
        recipients=[payload.recipient_email],
        subject=payload.subject or "[DTCK TEST] Báo Cáo Tổng Quan Thị Trường",
    )
    return res


@router.get("/preview-html")
def preview_html(market_dep: MarketDep) -> dict[str, str]:
    html = _service.build_current_overview_html(market_dep)
    return {"html": html}


@router.get("/logs")
def list_logs(limit: int = Query(default=50, ge=1, le=200)) -> list[dict[str, Any]]:
    return _service.get_logs(limit=limit)
