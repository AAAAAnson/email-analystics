from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
from datetime import datetime
from app.database import Base


class Email(Base):
    __tablename__ = "emails"

    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(String(255), unique=True, nullable=False, index=True)
    subject = Column(Text)
    sender = Column(String(255), index=True)
    recipients = Column(Text)
    cc = Column(Text)
    date = Column(DateTime(timezone=True), index=True)
    body_text = Column(Text)
    body_html = Column(Text)
    folder = Column(String(100), default="INBOX", index=True)
    is_read = Column(Boolean, default=False)
    has_attachments = Column(Boolean, default=False)
    attachments = Column(JSON, default=[])
    raw_headers = Column(JSON, default={})
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关联向量
    vectors = relationship("EmailVector", back_populates="email", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "message_id": self.message_id,
            "subject": self.subject,
            "sender": self.sender,
            "recipients": self.recipients,
            "cc": self.cc,
            "date": self.date.isoformat() if self.date else None,
            "body_text": self.body_text,
            "body_html": self.body_html,
            "folder": self.folder,
            "is_read": self.is_read,
            "has_attachments": self.has_attachments,
            "attachments": self.attachments,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class EmailVector(Base):
    __tablename__ = "email_vectors"

    id = Column(Integer, primary_key=True, index=True)
    email_id = Column(Integer, ForeignKey("emails.id", ondelete="CASCADE"), index=True)
    chunk_index = Column(Integer, default=0)
    chunk_text = Column(Text, nullable=False)
    embedding = Column(Vector(1024))  # DeepSeek embedding维度
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    # 关联邮件
    email = relationship("Email", back_populates="vectors")
