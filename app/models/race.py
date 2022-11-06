import datetime

from sqlalchemy import Column, Integer, DateTime, String, Float

from app.context import AppContext
from app.models.request_models import State
from store.postgres import Base


class Race(Base):
    __tablename__ = "races"

    id = Column(Integer, primary_key=True)
    start_time = Column(DateTime)
    finish_time = Column(DateTime)
    boat_name = Column(String)
    start_pos_lat = Column(Float)
    start_pos_lng = Column(Float)

    @staticmethod
    async def start_new_race(ctx: AppContext):
        cur_state: State = await State.get_current_state(ctx)
        new_race = Race(
            start_time=datetime.datetime.now(),
            start_pos_lat=cur_state.position_lat,
            start_pos_lng=cur_state.position_lng)
        new_race.save(ctx)
        # создать_нулевой_круг()
        return new_race

    @staticmethod
    async def get_current_race(ctx: AppContext):
        race = ctx.session.query(Race).order_by(Race.id.desc()).first()
        return race

    def save(self, ctx: AppContext):
        ctx.session.add(self)

    async def stop(self, ctx: AppContext):
        self.finish_time = datetime.datetime.now()
        self.save(ctx)
        cur_state: State = await State.get_current_state(ctx)
        cur_state.race_id = None
        # закончить_круг()
