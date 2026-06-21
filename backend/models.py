import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, Text, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from backend.database import Base

def generate_uuid():
    return str(uuid.uuid4())

class Case(Base):
    __tablename__ = "cases"
    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String, nullable=False)
    description = Column(Text, default="")
    device_info = Column(JSON, default={})
    file_path = Column(String, nullable=False)
    file_name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default="processing")
    chats = relationship("ChatMessage", back_populates="case", cascade="all, delete")
    calls = relationship("CallRecord", back_populates="case", cascade="all, delete")
    contacts = relationship("Contact", back_populates="case", cascade="all, delete")
    media_files = relationship("MediaFile", back_populates="case", cascade="all, delete")

class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id = Column(String, primary_key=True, default=generate_uuid)
    case_id = Column(String, ForeignKey("cases.id"), nullable=False)
    platform = Column(String, default="Unknown")
    sender = Column(String, default="Unknown")
    receiver = Column(String, default="Unknown")
    message_text = Column(Text, default="")
    timestamp = Column(String, default="")
    direction = Column(String, default="unknown")
    risk_score = Column(Float, default=0.0)
    entities_json = Column(JSON, default={})
    is_flagged = Column(Boolean, default=False)
    flag_reason = Column(String, default="")
    case = relationship("Case", back_populates="chats")

class CallRecord(Base):
    __tablename__ = "call_records"
    id = Column(String, primary_key=True, default=generate_uuid)
    case_id = Column(String, ForeignKey("cases.id"), nullable=False)
    caller_number = Column(String, default="")
    receiver_number = Column(String, default="")
    timestamp = Column(String, default="")
    duration_seconds = Column(Integer, default=0)
    call_type = Column(String, default="unknown")
    platform = Column(String, default="GSM")
    risk_score = Column(Float, default=0.0)
    is_foreign_number = Column(Boolean, default=False)
    is_flagged = Column(Boolean, default=False)
    case = relationship("Case", back_populates="calls")

class Contact(Base):
    __tablename__ = "contacts"
    id = Column(String, primary_key=True, default=generate_uuid)
    case_id = Column(String, ForeignKey("cases.id"), nullable=False)
    name = Column(String, default="Unknown")
    phone_numbers = Column(JSON, default=[])
    email_addresses = Column(JSON, default=[])
    organization = Column(String, default="")
    notes = Column(Text, default="")
    risk_score = Column(Float, default=0.0)
    entities_json = Column(JSON, default={})
    case = relationship("Case", back_populates="contacts")

class MediaFile(Base):
    __tablename__ = "media_files"
    id = Column(String, primary_key=True, default=generate_uuid)
    case_id = Column(String, ForeignKey("cases.id"), nullable=False)
    file_name = Column(String, default="")
    file_type = Column(String, default="")
    file_size_bytes = Column(Integer, default=0)
    timestamp = Column(String, default="")
    gps_latitude = Column(Float, nullable=True)
    gps_longitude = Column(Float, nullable=True)
    source_app = Column(String, default="")
    sha256_hash = Column(String, default="")
    risk_score = Column(Float, default=0.0)
    case = relationship("Case", back_populates="media_files")
