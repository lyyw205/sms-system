"""
Seed data for demo mode - creates sample messages, reservations, rules, and documents
"""
from sqlalchemy.orm import Session
from app.db.database import SessionLocal, init_db
from app.db.models import Message, Reservation, Rule, Document
from app.db.models import MessageDirection, MessageStatus, ReservationStatus
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_sample_messages(db: Session):
    """Create 30 sample messages"""
    messages = [
        # Inbound customer messages
        {
            "message_id": "sample_in_1",
            "direction": MessageDirection.INBOUND,
            "from_": "010-1234-5678",
            "to": "010-9999-0000",
            "message": "영업시간이 어떻게 되나요?",
            "status": MessageStatus.RECEIVED,
            "auto_response": "평일 09:00-18:00, 주말 10:00-17:00 영업합니다.",
            "auto_response_confidence": 0.95,
            "needs_review": False,
            "response_source": "rule",
        },
        {
            "message_id": "sample_in_2",
            "direction": MessageDirection.INBOUND,
            "from_": "010-2345-6789",
            "to": "010-9999-0000",
            "message": "예약 변경하고 싶어요",
            "status": MessageStatus.RECEIVED,
            "auto_response": "예약 변경은 고객센터로 연락 부탁드립니다.",
            "auto_response_confidence": 0.78,
            "needs_review": False,
            "response_source": "llm",
        },
        {
            "message_id": "sample_in_3",
            "direction": MessageDirection.INBOUND,
            "from_": "010-3456-7890",
            "to": "010-9999-0000",
            "message": "가격이 얼마인가요?",
            "status": MessageStatus.RECEIVED,
            "auto_response": "서비스 종류에 따라 가격이 다릅니다. 자세한 상담은 전화 주세요.",
            "auto_response_confidence": 0.85,
            "needs_review": False,
            "response_source": "rule",
        },
        {
            "message_id": "sample_in_4",
            "direction": MessageDirection.INBOUND,
            "from_": "010-4567-8901",
            "to": "010-9999-0000",
            "message": "주차 가능한가요?",
            "status": MessageStatus.RECEIVED,
            "auto_response": "건물 지하 1층에 무료 주차 가능합니다.",
            "auto_response_confidence": 0.92,
            "needs_review": False,
            "response_source": "rule",
        },
        {
            "message_id": "sample_in_5",
            "direction": MessageDirection.INBOUND,
            "from_": "010-5678-9012",
            "to": "010-9999-0000",
            "message": "할인 행사 있나요?",
            "status": MessageStatus.RECEIVED,
            "auto_response": "현재 진행 중인 할인 행사는 없습니다.",
            "auto_response_confidence": 0.45,
            "needs_review": True,
            "response_source": "llm",
        },
    ]

    # Outbound confirmation messages
    outbound_messages = [
        {
            "message_id": "sample_out_1",
            "direction": MessageDirection.OUTBOUND,
            "from_": "010-9999-0000",
            "to": "010-1111-2222",
            "message": "예약이 확정되었습니다. 2026-02-10 14:00에 방문 부탁드립니다.",
            "status": MessageStatus.SENT,
            "response_source": "auto",
        },
        {
            "message_id": "sample_out_2",
            "direction": MessageDirection.OUTBOUND,
            "from_": "010-9999-0000",
            "to": "010-2222-3333",
            "message": "예약이 취소되었습니다.",
            "status": MessageStatus.SENT,
            "response_source": "auto",
        },
    ]

    for msg_data in messages + outbound_messages:
        msg = Message(**msg_data)
        db.add(msg)

    logger.info(f"Created {len(messages + outbound_messages)} sample messages")


def create_sample_reservations(db: Session):
    """Create 20 sample reservations"""
    base_date = datetime.now()
    reservations = []

    names = [
        "김철수",
        "이영희",
        "박민수",
        "정수진",
        "최동욱",
        "강미영",
        "윤서준",
        "장지은",
        "임태준",
        "오혜진",
    ]

    for i in range(20):
        date = base_date + timedelta(days=i)
        status = ReservationStatus.PENDING
        if i % 3 == 0:
            status = ReservationStatus.CONFIRMED
        elif i % 7 == 0:
            status = ReservationStatus.CANCELLED

        reservations.append(
            {
                "external_id": f"naver_{i+1000}",
                "customer_name": names[i % len(names)],
                "phone": f"010-{1000+i:04d}-{2000+i:04d}",
                "date": date.strftime("%Y-%m-%d"),
                "time": f"{10 + (i % 8)}:00",
                "status": status,
                "notes": f"샘플 예약 {i+1}",
                "source": "naver" if i % 2 == 0 else "manual",
            }
        )

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
        db.commit()

        # Create sample data
        create_sample_messages(db)
        create_sample_reservations(db)
        create_sample_rules(db)
        create_sample_documents(db)

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
