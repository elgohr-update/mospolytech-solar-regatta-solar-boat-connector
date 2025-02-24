from app.BoatAPI.context import AppContext
from app.entities.land_ack import LandAck
from app.models.land_data import LandData


class LandDataController:
    @staticmethod
    async def save_sending_time(ack: LandAck, ctx: AppContext):
        land_data = LandData.get_by_id(ack.id, ctx)
        land_data.sent_at = ack.timestamp
        land_data.save(ctx)
