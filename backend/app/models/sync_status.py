from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime
from app.database import Base


class SyncStatus(Base):
    __tablename__ = "sync_status"

    id = Column(Integer, primary_key=True, index=True)
    folder = Column(String(100), nullable=False, unique=True)
    last_uid = Column(Integer, default=0)
    last_sync_at = Column(DateTime(timezone=True))
    total_emails = Column(Integer, default=0)
    status = Column(String(50), default="idle")  # idle, syncing, completed, error
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "folder": self.folder,
            "last_uid": self.last_uid,
            "last_sync_at": self.last_sync_at.isoformat() if self.last_sync_at else None,
            "total_emails": self.total_emails,
            "status": self.status,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
