# from uuid import UUID

# from fastapi import HTTPException, status
# from sqlalchemy.ext.asyncio import AsyncSession

# from app.models.moderation import ModerationAction
# from app.repositories import comment as comment_repo
# from app.repositories import community_staff as staff_repo


# MODERATOR_ROLES = {"owner", "admin", "moderator"}


# async def require_moderator(
#     session: AsyncSession,
#     *,
#     community_id: UUID,
#     user_id: UUID,
# ):
#     staff = await staff_repo.get_staff_membership(
#         session,
#         community_id=community_id,
#         user_id=user_id,
#     )

#     if not staff or staff.role not in MODERATOR_ROLES:
#         raise HTTPException(
#             status_code=status.HTTP_403_FORBIDDEN,
#             detail="Moderator permissions required",
#         )

#     return staff


# async def remove_comment(
#     session: AsyncSession,
#     *,
#     comment_id: int,
#     moderator_user_id: UUID,
#     reason: str | None,
# ):
#     comment = await comment_repo.get_comment_by_id(session, comment_id)

#     if not comment:
#         raise HTTPException(
#             status_code=status.HTTP_404_NOT_FOUND,
#             detail="Comment not found",
#         )

#     # You need the thread's community_id. Either join Thread or use relationship.
#     thread = comment.thread

#     await require_moderator(
#         session,
#         community_id=thread.community_id,
#         user_id=moderator_user_id,
#     )

#     comment.status = "removed_by_moderator"

#     action = ModerationAction(
#         community_id=thread.community_id,
#         moderator_user_id=moderator_user_id,
#         comment_id=comment.id,
#         action="remove_comment",
#         reason=reason,
#     )

#     session.add(action)

#     await session.commit()
#     await session.refresh(comment)

#     return comment
