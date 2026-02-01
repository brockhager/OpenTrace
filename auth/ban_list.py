# auth/ban_list.py
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Integer
from sqlalchemy.dialects.postgresql import INET
from api.models import Base


class IPBanList(Base):
    __tablename__ = "ip_ban_list"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ip_address = Column(INET, unique=True, nullable=False)
    reason = Column(String)
    banned_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)  # NULL = permanent