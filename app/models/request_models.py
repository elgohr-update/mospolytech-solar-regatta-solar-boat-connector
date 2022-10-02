import json
from dataclasses import dataclass
from datetime import datetime, timedelta
import geopy.distance

from redis import Redis
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import constants
from app.models.telemetry import Telemetry as pgTelemetry

from store.redis import RedisDB


@dataclass
class TelemetrySaveStatus:
    TEMP_SAVED = 'temporary saved'
    PERM_SAVED = 'permanently saved'
    FAILED = 'fail'


class Telemetry(BaseModel):
    created_at: datetime
    controller_watts: int
    time_to_go: int
    controller_volts: float
    MPPT_volts: float
    MPPT_watts: float
    motor_temp: float
    motor_revols: float
    position_lat: float
    position_lng: float

    async def save_current_state(self, db: Redis, session: Session):
        state = await State.from_telemetry(self, db)
        await state.save(db, session)


class PointSet(BaseModel):
    lng: float
    lat: float


class State(BaseModel):
    created_at: datetime
    controller_watts: int
    time_to_go: int
    controller_volts: float
    MPPT_volts: float
    MPPT_watts: float
    motor_temp: float
    motor_revols: float
    position_lat: float
    position_lng: float
    speed: float = 0
    distance_travelled: float = 0
    laps: int = 0
    lap_point_lat: float = None
    lap_point_lng: float = None

    class Config:
        orm_mode = True

    @staticmethod
    async def get_current_state(db: Redis):
        cur = await RedisDB.get(db, constants.CURRENT_STATE_KEY)
        if cur is None:
            raise FileNotFoundError("Key not found")
        return State(**json.loads(cur))

    @staticmethod
    def get_pg_state(session: Session):
        return pgTelemetry.get_last(session)

    def update_from_previous(self, prev):
        cur_coord = (self.position_lat, self.position_lng)
        prev_coord = (prev.position_lat, prev.position_lng)
        delta = (self.created_at - prev.created_at).seconds / 3600
        distance = geopy.distance.geodesic(cur_coord, prev_coord).km

        self.speed = distance / max(delta, 1)
        self.distance_travelled = prev.distance_travelled + distance
        self.laps = prev.laps
        self.lap_point_lat = prev.lap_point_lat
        self.lap_point_lng = prev.lap_point_lng
        if self.lap_point_lng is not None and self.lap_point_lat is not None:
            self.count_laps(prev)

    def count_laps(self, prev):
        lap_coord = (self.lap_point_lat, self.lap_point_lng)
        prev_coord = (prev.position_lat, prev.position_lng)
        cur_coord = (self.position_lat, self.position_lng)
        prev_dist = geopy.distance.geodesic(prev_coord, lap_coord).m
        cur_dist = geopy.distance.geodesic(cur_coord, lap_coord).m
        if prev_dist > constants.LAP_ADD_RADIUS_METERS >= cur_dist:
            self.laps += 1

    @staticmethod
    async def from_telemetry(telemetry: Telemetry, db: Redis):
        res = State(**telemetry.dict())

        try:
            prev = await State.get_current_state(db)
        except FileNotFoundError:
            return res
        res.update_from_previous(prev)
        return res

    async def _save_redis(self, db: Redis):
        await RedisDB.set(db, constants.CURRENT_STATE_KEY, self.json())

    def _save_pg(self, session: Session):
        pgTelemetry.save_from_schema(self, session)
        session.commit()

    async def save(self, db: Redis, session: Session):
        try:
            prev = await State.get_current_state(db)
        except FileNotFoundError:
            await self._save_redis(db)
            self._save_pg(session)
            return TelemetrySaveStatus.PERM_SAVED

        if prev.created_at < self.created_at:
            await self._save_redis(db)
        prev = State.get_pg_state(session)
        if prev is None or self.created_at - prev.created_at > timedelta(seconds=constants.TELEMETRY_REMEMBER_DELAY):
            self._save_pg(session)
            return TelemetrySaveStatus.PERM_SAVED
        else:
            return TelemetrySaveStatus.TEMP_SAVED

    @staticmethod
    async def set_point(db: Redis) -> PointSet:
        prev = await State.get_current_state(db)
        prev.lap_point_lng = prev.position_lng
        prev.lap_point_lat = prev.position_lat
        prev.laps = 0
        await prev._save_redis(db)
        return PointSet(lng=prev.lap_point_lng, lat=prev.lap_point_lat)

    @staticmethod
    async def reset_point(db: Redis) -> None:
        prev = await State.get_current_state(db)
        prev.lap_point_lng = None
        prev.lap_point_lat = None
        prev.laps = 0
        await prev._save_redis(db)

    @staticmethod
    async def reset_distance(db: Redis) -> None:
        prev = await State.get_current_state(db)
        prev.distance_travelled = 0
        await prev._save_redis(db)

    @staticmethod
    async def remove_point(db: Redis):
        prev = await State.get_current_state(db)
        prev.lap_point_lng = None
        prev.lap_point_lat = None
        prev.laps = 0
        await prev._save_redis(db)
        return PointSet(lng=prev.lap_point_lng, lat=prev.lap_point_lat)

    @staticmethod
    async def clear_distance(db: Redis):
        prev = await State.get_current_state(db)
        prev.distance_travelled = 0
        await prev._save_redis(db)
