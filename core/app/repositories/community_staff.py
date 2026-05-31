# # app/models/community_staff.py

# from uuid import UUID
# from sqlalchemy import select
# from sqlalchemy.ext.asyncio import AsyncSession

# from app.models.community_staff import CommunityStaff


# async def get_staff_membership(
#     session: AsyncSession,
#     *,
#     community_id: UUID,
#     user_id: UUID,
# ) -> CommunityStaff | None:
#     result = await session.execute(
#         select(CommunityStaff).where(
#             CommunityStaff.community_id == community_id,
#             CommunityStaff.user_id == user_id,
#         )
#     )
#     return result.scalar_one_or_none()
