"""
Seed data for demo mode - creates sample messages, reservations, rules, documents,
message templates, campaign logs, and gender statistics
"""
from sqlalchemy.orm import Session
from app.db.database import SessionLocal, init_db
from app.db.models import (
    Message, Reservation, Rule, Document,
    MessageTemplate, CampaignLog, GenderStat,
    MessageDirection, MessageStatus, ReservationStatus,
)
from datetime import datetime, timedelta
import logging
import json
import random

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_sample_messages(db: Session):
    """Create sample conversation threads matching reservation phone numbers"""
    now = datetime.utcnow()
    our = "010-9999-0000"

    # Conversations — phone numbers match reservations (010-{1000+i}-{2000+i})
    # Each conversation is a list of (direction, message, minutes_ago, source, confidence, needs_review)
    conversations = [
        # 김철수 (010-1000-2000) — 영업시간 문의, 3턴
        ("010-1000-2000", [
            ("in",  "안녕하세요, 영업시간이 어떻게 되나요?",       120, None, None, False),
            ("out", "평일 09:00-18:00, 주말 10:00-17:00 영업합니다. 공휴일은 휴무입니다.", 119, "rule", 0.95, False),
            ("in",  "주말에도 예약 가능한가요?",                    60, None, None, False),
            ("out", "네, 주말에도 예약 가능합니다. 네이버 예약이나 전화로 예약해주세요.", 59, "rule", 0.92, False),
            ("in",  "감사합니다!",                                  30, None, None, False),
            ("out", "감사합니다. 좋은 하루 보내세요!",              29, "llm", 0.80, False),
        ]),
        # 이영희 (010-1001-2001) — 예약 변경, 2턴 + 검토 필요 케이스
        ("010-1001-2001", [
            ("in",  "예약 변경하고 싶은데요, 2월 12일로 바꿀 수 있나요?", 180, None, None, False),
            ("out", "예약 변경은 고객센터(010-9999-0000)로 전화 부탁드립니다. 영업시간 내에 연락주시면 바로 처리해드리겠습니다.", 179, "llm", 0.78, False),
            ("in",  "전화 말고 문자로 처리 안 되나요?",             90, None, None, True),
        ]),
        # 박민수 (010-1002-2002) — 가격 문의, 3턴
        ("010-1002-2002", [
            ("in",  "가격이 얼마인가요?",                         300, None, None, False),
            ("out", "서비스 종류에 따라 가격이 다릅니다. 자세한 상담은 전화 주세요.", 299, "rule", 0.85, False),
            ("in",  "스탠다드룸 1박 기준으로요",                   240, None, None, False),
            ("out", "스탠다드룸 1박 기준 50,000원입니다. 주말/공휴일은 10,000원 추가됩니다.", 239, "llm", 0.72, False),
            ("in",  "카드 결제 되나요?",                           200, None, None, False),
            ("out", "네, 카드 결제 가능합니다. 현장에서 결제해주시면 됩니다.", 199, "llm", 0.80, False),
        ]),
        # 정수진 (010-1003-2003) — 주차 + 위치 문의
        ("010-1003-2003", [
            ("in",  "주차 가능한가요?",                            400, None, None, False),
            ("out", "건물 지하 1층에 무료 주차 가능합니다.",        399, "rule", 0.92, False),
            ("in",  "위치가 정확히 어디예요?",                      350, None, None, False),
            ("out", "서울시 강남구 테헤란로 123 (강남역 2번 출구에서 도보 5분)", 349, "rule", 0.95, False),
        ]),
        # 최동욱 (010-1004-2004) — 할인 문의, 검토 필요
        ("010-1004-2004", [
            ("in",  "할인 행사 같은 거 있나요?",                   500, None, None, True),
            ("in",  "단체 할인도 궁금합니다",                      480, None, None, True),
        ]),
        # 강미영 (010-1005-2005) — 취소 문의
        ("010-1005-2005", [
            ("in",  "예약 취소하고 싶습니다",                      600, None, None, False),
            ("out", "예약 취소는 1일 전까지 무료 취소 가능합니다. 예약번호를 알려주시면 처리해드리겠습니다.", 599, "llm", 0.75, False),
            ("in",  "NB20260205 이 번호입니다",                    550, None, None, False),
            ("out", "해당 예약이 취소 처리되었습니다. 감사합니다.", 549, "llm", 0.70, False),
        ]),
        # 윤서준 (010-1006-2006) — 파티 문의
        ("010-1006-2006", [
            ("in",  "파티는 몇시에 시작하나요?",                    45, None, None, False),
            ("out", "파티는 저녁 8시에 B동 1층 포차에서 시작됩니다. 편한 옷차림으로 와주세요!", 44, "rule", 0.95, False),
            ("in",  "드레스코드 같은 거 있나요?",                   20, None, None, False),
            ("out", "특별한 드레스코드는 없습니다. 편한 옷차림이면 충분합니다.", 19, "llm", 0.68, False),
        ]),
        # 장지은 (010-1007-2007) — 체크인 문의, 최근 대화
        ("010-1007-2007", [
            ("in",  "체크인 시간이 어떻게 되나요?",                  10, None, None, False),
            ("out", "체크인은 오후 3시부터 가능합니다. 무인 체크인이라 바로 입실하시면 됩니다.", 9, "rule", 0.95, False),
            ("in",  "비밀번호는 어디서 확인하나요?",                  5, None, None, False),
            ("out", "객실 안내 문자에 비밀번호가 포함되어 있습니다. 확인 부탁드립니다.", 4, "llm", 0.82, False),
            ("in",  "감사합니다 곧 도착합니다!",                      2, None, None, False),
            ("out", "감사합니다. 편안한 시간 보내세요!",              1, "llm", 0.85, False),
        ]),
    ]

    msg_count = 0
    for phone, thread in conversations:
        for i, (direction, text, mins_ago, source, confidence, needs_review) in enumerate(thread):
            is_inbound = direction == "in"
            msg = Message(
                message_id=f"seed_{phone}_{i}",
                direction=MessageDirection.INBOUND if is_inbound else MessageDirection.OUTBOUND,
                from_=phone if is_inbound else our,
                to=our if is_inbound else phone,
                message=text,
                status=MessageStatus.RECEIVED if is_inbound else MessageStatus.SENT,
                created_at=now - timedelta(minutes=mins_ago),
                auto_response=None,
                auto_response_confidence=confidence if not is_inbound else None,
                needs_review=needs_review if is_inbound else False,
                response_source=source,
            )
            db.add(msg)
            msg_count += 1

    logger.info(f"Created {msg_count} sample messages (8 conversations)")


def create_sample_reservations(db: Session):
    """Create 20 sample reservations with full fields for demo"""
    today = datetime.now()

    names = [
        "김철수", "이영희", "박민수", "정수진", "최동욱",
        "강미영", "윤서준", "장지은", "임태준", "오혜진",
        "한상우", "배수연", "송민호", "류하은", "조윤서",
        "권태양", "신예린", "황준혁", "문서현", "안지호",
    ]

    rooms = ["A101", "A102", "A103", "A104", "A105", "B201", "B202", "B203", "B204", "B205"]
    room_infos = ["더블룸", "트윈룸", "패밀리룸", "디럭스룸", "스탠다드룸"]
    genders = ["남", "여"]
    age_groups = ["20대", "30대", "20대", "30대", "20대"]
    tag_options = ["객후", "1초", "2차만", "객후,1초", "1초,2차만", "객후,2차만"]

    reservations = []

    for i in range(20):
        # Spread dates around today: -1 to +2 days
        day_offset = (i % 4) - 1  # -1, 0, 1, 2
        date = today + timedelta(days=day_offset)

        # Status distribution
        if i < 12:
            status = ReservationStatus.CONFIRMED
        elif i < 16:
            status = ReservationStatus.PENDING
        elif i < 18:
            status = ReservationStatus.COMPLETED
        else:
            status = ReservationStatus.CANCELLED

        # Room assignment: first 10 get rooms, rest don't
        has_room = i < 10
        room_number = rooms[i] if has_room else None
        room_info = room_infos[i % 5] if has_room else None
        room_password = f"{random.randint(1,9)}0{(i+1)*100}" if has_room else None

        # Gender and demographics
        gender = genders[i % 2]
        age_group = age_groups[i % 5]
        visit_count = random.randint(1, 5)

        # Tags
        tags = tag_options[i % len(tag_options)]

        # Party participants
        party_participants = random.randint(1, 4)

        # SMS sent tracking
        room_sms_sent = i < 12  # First 12 have room SMS sent
        party_sms_sent = i < 10  # First 10 have party SMS sent

        reservations.append({
            "external_id": f"naver_{i+1000}",
            "customer_name": names[i],
            "phone": f"010-{1000+i:04d}-{2000+i:04d}",
            "date": date.strftime("%Y-%m-%d"),
            "time": f"{10 + (i % 8)}:00",
            "status": status,
            "notes": f"샘플 예약 {i+1}",
            "source": "naver" if i % 2 == 0 else "manual",
            "naver_booking_id": f"NB{20260200 + i}" if i % 2 == 0 else None,
            "room_number": room_number,
            "room_password": room_password,
            "room_info": room_info,
            "gender": gender,
            "age_group": age_group,
            "visit_count": visit_count,
            "party_participants": party_participants,
            "tags": tags,
            "room_sms_sent": room_sms_sent,
            "party_sms_sent": party_sms_sent,
            "room_sms_sent_at": datetime.utcnow() if room_sms_sent else None,
            "party_sms_sent_at": datetime.utcnow() if party_sms_sent else None,
        })

    for res_data in reservations:
        res = Reservation(**res_data)
        db.add(res)

    logger.info(f"Created {len(reservations)} sample reservations")


def create_sample_rules(db: Session):
    """Create 5 basic rules"""
    rules = [
        {
            "name": "영업시간 안내",
            "pattern": r"(영업시간|몇시|언제|시간)",
            "response": "평일 09:00-18:00, 주말 10:00-17:00 영업합니다. 공휴일은 휴무입니다.",
            "priority": 10,
            "active": True,
        },
        {
            "name": "예약 문의",
            "pattern": r"(예약|방문|언제|가능)",
            "response": "예약은 전화(010-9999-0000) 또는 네이버 예약으로 가능합니다.",
            "priority": 9,
            "active": True,
        },
        {
            "name": "가격 안내",
            "pattern": r"(가격|비용|얼마|요금)",
            "response": "서비스 종류에 따라 가격이 다릅니다. 자세한 상담은 전화 주세요.",
            "priority": 8,
            "active": True,
        },
        {
            "name": "주차 안내",
            "pattern": r"(주차|차|자동차)",
            "response": "건물 지하 1층에 무료 주차 가능합니다.",
            "priority": 7,
            "active": True,
        },
        {
            "name": "위치 안내",
            "pattern": r"(위치|어디|주소|찾아가|길)",
            "response": "서울시 강남구 테헤란로 123 (강남역 2번 출구에서 도보 5분)",
            "priority": 6,
            "active": True,
        },
    ]

    for rule_data in rules:
        rule = Rule(**rule_data)
        db.add(rule)

    logger.info(f"Created {len(rules)} sample rules")


def create_sample_documents(db: Session):
    """Create 3 sample documents"""
    documents = [
        {
            "filename": "서비스_가격표.pdf",
            "content": "기본 서비스: 50,000원\n프리미엄 서비스: 100,000원",
            "file_path": "/uploads/서비스_가격표.pdf",
            "indexed": False,
        },
        {
            "filename": "자주_묻는_질문_FAQ.txt",
            "content": "Q: 예약 취소 가능한가요?\nA: 예약 1일 전까지 무료 취소 가능합니다.",
            "file_path": "/uploads/FAQ.txt",
            "indexed": False,
        },
        {
            "filename": "이용_안내.docx",
            "content": "방문 시 주의사항:\n1. 예약 시간 10분 전 도착\n2. 신분증 지참",
            "file_path": "/uploads/이용_안내.docx",
            "indexed": False,
        },
    ]

    for doc_data in documents:
        doc = Document(**doc_data)
        db.add(doc)

    logger.info(f"Created {len(documents)} sample documents")


def create_sample_templates(db: Session):
    """Create 4 message templates"""
    templates = [
        {
            "key": "room_guide",
            "name": "객실 안내 문자",
            "content": (
                "금일 객실은 스테이블 {{building}}동 {{roomNum}}호 - {{roomInfo}}룸입니다."
                "(비밀번호: {{password}}*)\n\n"
                "무인 체크인이라서 바로 입실하시면 됩니다.\n"
                "객실내에서(발코니포함) 음주, 흡연, 취식, 혼숙 절대 금지입니다."
                "(적발시 벌금 10만원 또는 퇴실)\n\n"
                "파티 참여 시 저녁 8시에 B동 1층 포차로 내려와 주시면 되세요."
            ),
            "variables": json.dumps(["building", "roomNum", "roomInfo", "password"]),
            "category": "room_guide",
            "active": True,
        },
        {
            "key": "party_guide",
            "name": "파티 안내 문자",
            "content": (
                "금일 파티 참여 시 아래 계좌로 파티비 입금 후 "
                "저녁 8시 스테이블 B동 1층 포차로 내려와주세요!\n\n"
                "{{priceInfo}}\n\n"
                "- 금일 파티 인원은 {{totalParticipants}}명+ 예상됨(여자{{femaleCount}}명)\n"
                "- 조별활동이 있으니 편한 옷차림으로 내려와주세요."
            ),
            "variables": json.dumps(["priceInfo", "totalParticipants", "femaleCount"]),
            "category": "party_guide",
            "active": True,
        },
        {
            "key": "reservation_confirm",
            "name": "예약 확정 안내",
            "content": (
                "안녕하세요 {{name}}님, 예약이 확정되었습니다.\n\n"
                "날짜: {{date}}\n시간: {{time}}\n\n"
                "문의사항은 010-9999-0000으로 연락 주세요."
            ),
            "variables": json.dumps(["name", "date", "time"]),
            "category": "notification",
            "active": True,
        },
        {
            "key": "gender_invite",
            "name": "성비 초대 문자",
            "content": (
                "오늘 파티에 여성분들의 참여를 기다리고 있어요!\n\n"
                "현재 남녀비율: 남 {{maleCount}}명 / 여 {{femaleCount}}명\n"
                "총 {{totalParticipants}}명 참여 예정\n\n"
                "저녁 8시 스테이블 B동 1층 포차에서 만나요!"
            ),
            "variables": json.dumps(["maleCount", "femaleCount", "totalParticipants"]),
            "category": "party_guide",
            "active": True,
        },
    ]

    for tmpl_data in templates:
        tmpl = MessageTemplate(**tmpl_data)
        db.add(tmpl)

    logger.info(f"Created {len(templates)} message templates")


def create_sample_campaign_logs(db: Session):
    """Create 5 campaign log entries"""
    now = datetime.utcnow()

    campaigns = [
        {
            "campaign_type": "room_guide",
            "target_tag": None,
            "target_count": 8,
            "sent_count": 8,
            "failed_count": 0,
            "sent_at": now - timedelta(days=2, hours=3),
            "completed_at": now - timedelta(days=2, hours=3),
        },
        {
            "campaign_type": "room_guide",
            "target_tag": None,
            "target_count": 6,
            "sent_count": 5,
            "failed_count": 1,
            "sent_at": now - timedelta(days=1, hours=5),
            "completed_at": now - timedelta(days=1, hours=5),
            "error_message": "1건 전송 실패: 번호 오류",
        },
        {
            "campaign_type": "party_guide",
            "target_tag": None,
            "target_count": 12,
            "sent_count": 12,
            "failed_count": 0,
            "sent_at": now - timedelta(days=1, hours=2),
            "completed_at": now - timedelta(days=1, hours=2),
        },
        {
            "campaign_type": "tag_based",
            "target_tag": "객후",
            "target_count": 5,
            "sent_count": 5,
            "failed_count": 0,
            "sent_at": now - timedelta(hours=6),
            "completed_at": now - timedelta(hours=6),
        },
        {
            "campaign_type": "tag_based",
            "target_tag": "1초,2차만",
            "target_count": 3,
            "sent_count": 2,
            "failed_count": 1,
            "sent_at": now - timedelta(hours=2),
            "completed_at": now - timedelta(hours=2),
            "error_message": "1건 전송 실패: 수신거부",
        },
    ]

    for camp_data in campaigns:
        camp = CampaignLog(**camp_data)
        db.add(camp)

    logger.info(f"Created {len(campaigns)} campaign logs")


def create_sample_gender_stats(db: Session):
    """Create 8 days of gender statistics"""
    today = datetime.now()

    stats_data = [
        {"offset": -7, "male": 15, "female": 8},
        {"offset": -6, "male": 18, "female": 10},
        {"offset": -5, "male": 22, "female": 14},
        {"offset": -4, "male": 20, "female": 12},
        {"offset": -3, "male": 25, "female": 15},
        {"offset": -2, "male": 19, "female": 11},
        {"offset": -1, "male": 23, "female": 13},
        {"offset": 0, "male": 18, "female": 12},
    ]

    for s in stats_data:
        date = today + timedelta(days=s["offset"])
        stat = GenderStat(
            date=date.strftime("%Y-%m-%d"),
            male_count=s["male"],
            female_count=s["female"],
            total_participants=s["male"] + s["female"],
        )
        db.add(stat)

    logger.info(f"Created {len(stats_data)} gender stat records")


def seed_all():
    """Run all seed functions"""
    logger.info("Initializing database...")
    init_db()

    logger.info("Seeding data...")
    db = SessionLocal()
    try:
        # Clear existing data
        db.query(Message).delete()
        db.query(Reservation).delete()
        db.query(Rule).delete()
        db.query(Document).delete()
        db.query(MessageTemplate).delete()
        db.query(CampaignLog).delete()
        db.query(GenderStat).delete()
        db.commit()

        # Create sample data
        create_sample_messages(db)
        create_sample_reservations(db)
        create_sample_rules(db)
        create_sample_documents(db)
        create_sample_templates(db)
        create_sample_campaign_logs(db)
        create_sample_gender_stats(db)

        db.commit()
        logger.info("✅ Seeding completed successfully!")
    except Exception as e:
        logger.error(f"❌ Seeding failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_all()
