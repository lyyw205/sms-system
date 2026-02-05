"""
SQLAlchemy database models
"""
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Float, Enum
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import enum

Base = declarative_base()


class MessageDirection(str, enum.Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class MessageStatus(str, enum.Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    RECEIVED = "received"


class ReservationStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class Message(Base):
    """SMS message records"""

    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(String(100), unique=True, index=True)
    direction = Column(Enum(MessageDirection), nullable=False)
    from_ = Column("from_phone", String(20), nullable=False)
    to = Column(String(20), nullable=False)
    message = Column(Text, nullable=False)
    status = Column(Enum(MessageStatus), default=MessageStatus.PENDING)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Auto-response metadata
    auto_response = Column(Text, nullable=True)
    auto_response_confidence = Column(Float, nullable=True)
    needs_review = Column(Boolean, default=False)
    response_source = Column(String(20), nullable=True)  # 'rule', 'llm', 'manual'


class Reservation(Base):
    """Reservation records"""

    __tablename__ = "reservations"

    id = Column(Integer, primary_key=True, index=True)
    external_id = Column(String(100), unique=True, nullable=True, index=True)
    customer_name = Column(String(100), nullable=False)
    phone = Column(String(20), nullable=False)
    date = Column(String(20), nullable=False)  # YYYY-MM-DD
    time = Column(String(10), nullable=False)  # HH:MM
    status = Column(Enum(ReservationStatus), default=ReservationStatus.PENDING)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Source tracking
    source = Column(String(20), default="manual")  # 'naver', 'manual', 'phone'


class Rule(Base):
    """Auto-response rules"""

    __tablename__ = "rules"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    pattern = Column(String(500), nullable=False)  # Regex pattern
    response = Column(Text, nullable=False)
    priority = Column(Integer, default=0)  # Higher = higher priority
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Document(Base):
    """Knowledge base documents for RAG"""

    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(200), nullable=False)
    content = Column(Text, nullable=True)
    file_path = Column(String(500), nullable=True)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    indexed = Column(Boolean, default=False)  # ChromaDB indexing status
