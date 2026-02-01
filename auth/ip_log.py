# auth/ip_log.py
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Integer, Boolean, Text
from sqlalchemy.dialects.postgresql import INET
from api.models import Base


class IPLookupLog(Base):
    __tablename__ = "ip_lookup_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ip_address = Column(INET, nullable=False, index=True)
    action = Column(String, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    user_agent = Column(Text)
    success = Column(Boolean, default=True)