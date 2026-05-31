# from uuid import UUID

# from fastapi import HTTPException, status
# from sqlalchemy.ext.asyncio import AsyncSession

# from app.models.report import CommentReport
# from app.repositories import comment as comment_repo


# async def report_comment(
#     session: AsyncSession,
#     *,
#     comment_id: int,
#     reporter_community_user_id: UUID,
#     reason: str,
#     details: str | None,
# ):
#     comment = await comment_repo.get_comment_by_id(session, comment_id)

#     if not comment:
#         raise HTTPException(
#             status_code=status.HTTP_404_NOT_FOUND,
#             detail="Comment not found",
#         )

#     report = CommentReport(
#         comment_id=comment_id,
#         reporter_community_user_id=reporter_community_user_id,
#         reason=reason,
#         details=details,
#         status="open",
#     )

#     session.add(report)
#     await session.commit()
#     await session.refresh(report)

#     return report
