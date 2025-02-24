from datetime import datetime
from enum import IntEnum

from sqlalchemy import Column, Integer, DateTime, String

from app.BoatAPI.context import AppContext
from store.postgres import Base


class LandData(Base):
    __tablename__ = "land_data"
    id = Column(Integer, primary_key=True)
    priority = Column(Integer)
    created_at = Column(DateTime)
    sent_at = Column(DateTime)
    data = Column(String)

    class Priority(IntEnum):
        low = 0
        high = 1

    def save(self, ctx: AppContext):
        ctx.session.add(self)

    @staticmethod
    def get_by_id(land_data_id: int, ctx: AppContext):
        land_data = ctx.session.query(LandData).filter_by(id=land_data_id).first()
        return land_data