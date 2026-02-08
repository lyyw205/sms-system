"""
Campaign API endpoints for tag-based SMS sending
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from datetime import datetime

from ..db.database import get_db
from ..db.models import CampaignLog, GenderStat, MessageTemplate
from ..factory import get_sms_provider, get_storage_provider
from ..campaigns.tag_manager import TagCampaignManager
from ..notifications.service import NotificationService
from ..analytics.gender_analyzer import GenderAnalyzer

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


# Request/Response models
class CampaignRequest(BaseModel):
    tag: str
    template_key: str
    variables: Optional[Dict[str, Any]] = None
    sms_type: str = 'room'  # 'room' or 'party'
    date: Optional[str] = None  # YYYY-MM-DD


class RoomGuideRequest(BaseModel):
    date: Optional[str] = None  # YYYY-MM-DD
    start_row: int = 3
    end_row: int = 68


class PartyGuideRequest(BaseModel):
    date: Optional[str] = None
    start_row: int = 100
    end_row: int = 117


class GenderStatsResponse(BaseModel):
    date: str
    male_count: int
    female_count: int
    total_participants: int
    balance: Dict[str, Any]


@router.get("/targets")
async def get_campaign_targets(
    tag: str,
    exclude_sent: bool = True,
    sms_type: str = 'room',
    date: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Get SMS targets filtered by tag

    Args:
        tag: Tag to filter by (e.g., "객후", "1,2,2차만")
        exclude_sent: Exclude already-sent numbers
        sms_type: Type of SMS ('room' or 'party')
        date: Date filter in YYYY-MM-DD format
    """
    sms_provider = get_sms_provider()
    manager = TagCampaignManager(db, sms_provider)

    targets = manager.get_targets_by_tag(tag, exclude_sent, sms_type, date=date)

    return {
        "tag": tag,
        "total_count": len(targets),
        "targets": [
            {
                "id": t.id,
                "name": t.customer_name,
                "phone": t.phone,
                "date": t.date,
                "room_number": t.room_number,
                "tags": t.tags,
                "room_sms_sent": t.room_sms_sent,
                "party_sms_sent": t.party_sms_sent
            }
            for t in targets
        ]
    }


@router.post("/send-by-tag")
async def send_by_tag(
    request: CampaignRequest,
    db: Session = Depends(get_db)
):
    """
    Execute tag-based SMS campaign

    Args:
        request: Campaign configuration
    """
    sms_provider = get_sms_provider()
    manager = TagCampaignManager(db, sms_provider)

    try:
        campaign = await manager.send_campaign(
            tag=request.tag,
            template_key=request.template_key,
            variables=request.variables,
            sms_type=request.sms_type,
            date=request.date,
        )

        return {
            "campaign_id": campaign.id,
            "target_count": campaign.target_count,
            "sent_count": campaign.sent_count,
            "failed_count": campaign.failed_count,
            "status": "completed" if campaign.completed_at else "running"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/campaigns/{campaign_id}")
async def get_campaign_stats(
    campaign_id: int,
    db: Session = Depends(get_db)
):
    """Get campaign statistics by ID"""
    sms_provider = get_sms_provider()
    manager = TagCampaignManager(db, sms_provider)

    stats = manager.get_campaign_stats(campaign_id)

    if not stats:
        raise HTTPException(status_code=404, detail="Campaign not found")

    return stats


@router.post("/notifications/room-guide")
async def send_room_guide(
    request: RoomGuideRequest,
    db: Session = Depends(get_db)
):
    """
    Send room guide messages to confirmed guests

    Automated version of stable-clasp-main roomGuideSMS()
    """
    sms_provider = get_sms_provider()
    storage_provider = get_storage_provider()

    service = NotificationService(db, sms_provider, storage_provider)

    # Parse date
    if request.date:
        date = datetime.strptime(request.date, "%Y-%m-%d")
    else:
        date = datetime.now()

    try:
        campaign = await service.send_room_guide(
            date=date,
            start_row=request.start_row,
            end_row=request.end_row
        )

        return {
            "campaign_id": campaign.id,
            "date": date.strftime("%Y-%m-%d"),
            "target_count": campaign.target_count,
            "sent_count": campaign.sent_count,
            "failed_count": campaign.failed_count,
            "status": "completed"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/notifications/party-guide")
async def send_party_guide(
    request: PartyGuideRequest,
    db: Session = Depends(get_db)
):
    """
    Send party guide messages to unassigned guests

    Automated version of stable-clasp-main partyGuideSMS()
    """
    sms_provider = get_sms_provider()
    storage_provider = get_storage_provider()

    service = NotificationService(db, sms_provider, storage_provider)

    # Parse date
    if request.date:
        date = datetime.strptime(request.date, "%Y-%m-%d")
    else:
        date = datetime.now()

    try:
        campaign = await service.send_party_guide(
            date=date,
            start_row=request.start_row,
            end_row=request.end_row
        )

        return {
            "campaign_id": campaign.id,
            "date": date.strftime("%Y-%m-%d"),
            "target_count": campaign.target_count,
            "sent_count": campaign.sent_count,
            "failed_count": campaign.failed_count,
            "status": "completed"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/gender-stats")
async def get_gender_stats(
    date: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Get gender statistics for a specific date

    Args:
        date: Date in YYYY-MM-DD format (defaults to today)
    """
    storage_provider = get_storage_provider()
    analyzer = GenderAnalyzer(db, storage_provider)

    # Parse date
    if date:
        target_date = datetime.strptime(date, "%Y-%m-%d")
    else:
        target_date = datetime.now()

    # Try to get from database first
    stat = analyzer.get_gender_stats(target_date)

    if not stat:
        # Extract from sheets if not in DB
        stat = await analyzer.extract_gender_stats(target_date)

    if not stat:
        raise HTTPException(status_code=404, detail="Gender stats not found")

    # Calculate balance
    balance = analyzer.calculate_party_balance(stat)

    return {
        "date": stat.date,
        "male_count": stat.male_count,
        "female_count": stat.female_count,
        "total_participants": stat.total_participants,
        "balance": balance,
        "invite_message": analyzer.generate_invite_message(stat)
    }


@router.post("/gender-stats/refresh")
async def refresh_gender_stats(
    date: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Refresh gender statistics from Google Sheets

    Args:
        date: Date in YYYY-MM-DD format (defaults to today)
    """
    storage_provider = get_storage_provider()
    analyzer = GenderAnalyzer(db, storage_provider)

    # Parse date
    if date:
        target_date = datetime.strptime(date, "%Y-%m-%d")
    else:
        target_date = datetime.now()

    try:
        stat = await analyzer.extract_gender_stats(target_date)

        if not stat:
            raise HTTPException(status_code=404, detail="Failed to extract gender stats")

        balance = analyzer.calculate_party_balance(stat)

        return {
            "date": stat.date,
            "male_count": stat.male_count,
            "female_count": stat.female_count,
            "total_participants": stat.total_participants,
            "balance": balance,
            "updated_at": stat.updated_at.isoformat()
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history")
async def get_campaign_history(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """Get campaign sending history"""
    campaigns = (
        db.query(CampaignLog)
        .order_by(CampaignLog.sent_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    return [
        {
            "id": c.id,
            "campaign_type": c.campaign_type,
            "target_tag": c.target_tag,
            "target_count": c.target_count,
            "sent_count": c.sent_count,
            "failed_count": c.failed_count,
            "sent_at": c.sent_at.isoformat() if c.sent_at else None,
            "completed_at": c.completed_at.isoformat() if c.completed_at else None,
            "error_message": c.error_message,
        }
        for c in campaigns
    ]


@router.get("/gender-stats/history")
async def get_gender_stats_history(
    days: int = 8,
    db: Session = Depends(get_db)
):
    """Get gender statistics history for chart"""
    stats = (
        db.query(GenderStat)
        .order_by(GenderStat.date.desc())
        .limit(days)
        .all()
    )

    # Return in chronological order
    stats.reverse()

    return [
        {
            "date": s.date,
            "male_count": s.male_count,
            "female_count": s.female_count,
            "total_participants": s.total_participants,
        }
        for s in stats
    ]


@router.get("/templates")
async def get_templates(db: Session = Depends(get_db)):
    """Get all message templates"""
    templates = db.query(MessageTemplate).filter_by(active=True).all()

    return [
        {
            "id": t.id,
            "key": t.key,
            "name": t.name,
            "content": t.content,
            "variables": t.variables,
            "category": t.category,
        }
        for t in templates
    ]
