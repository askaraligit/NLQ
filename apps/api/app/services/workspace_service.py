"""User-scoped conversations, query history, and saved-query persistence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.application import Conversation, QueryRecord, SavedQuery, UserSettings
from app.services.auth_service import AuthenticatedUser

if TYPE_CHECKING:
    from app.services.nlq_service import QueryResponseData


class WorkspaceNotFoundError(RuntimeError):
    """A requested workspace record is absent or belongs to another user."""


@dataclass(frozen=True)
class ConversationContextTurn:
    question: str
    summary: str


class WorkspaceService:
    def __init__(self, max_turns: int) -> None:
        self.max_turns = max_turns

    def prepare_conversation(
        self, session: Session, user: AuthenticatedUser, conversation_id: UUID | None, title: str
    ) -> tuple[Conversation, tuple[ConversationContextTurn, ...]]:
        if conversation_id is None:
            conversation = Conversation(user_id=user.id, title=title[:180])
            session.add(conversation)
            session.flush()
            return conversation, ()
        conversation = session.scalar(
            select(Conversation).where(
                Conversation.id == conversation_id, Conversation.user_id == user.id
            )
        )
        if conversation is None:
            raise WorkspaceNotFoundError("Conversation not found.")
        if not self.max_turns:
            return conversation, ()
        records = list(
            session.scalars(
                select(QueryRecord)
                .where(
                    QueryRecord.conversation_id == conversation.id, QueryRecord.user_id == user.id
                )
                .order_by(desc(QueryRecord.created_at))
                .limit(self.max_turns)
            )
        )
        records.reverse()
        return conversation, tuple(
            ConversationContextTurn(record.question, record.summary) for record in records
        )

    def record_query(
        self,
        session: Session,
        user: AuthenticatedUser,
        conversation: Conversation,
        question: str,
        result: QueryResponseData,
    ) -> QueryRecord:
        record = QueryRecord(
            id=result.query_id,
            user_id=user.id,
            conversation_id=conversation.id,
            question=question,
            sql=result.sql,
            query_language=result.query_language,
            summary=result.summary,
            columns=[{"name": name} for name in result.columns],
            rows=result.rows,
            visualization={
                "type": result.visualization_type,
                "xAxis": result.x_axis,
                "yAxis": result.y_axis,
            },
            execution_time_ms=result.execution_time_ms,
        )
        session.add(record)
        session.commit()
        session.refresh(record)
        return record

    @staticmethod
    def history(session: Session, user: AuthenticatedUser, limit: int = 50) -> list[QueryRecord]:
        return list(
            session.scalars(
                select(QueryRecord)
                .where(QueryRecord.user_id == user.id)
                .order_by(desc(QueryRecord.created_at))
                .limit(limit)
            )
        )

    @staticmethod
    def get_record(session: Session, user: AuthenticatedUser, record_id: UUID) -> QueryRecord:
        record = session.scalar(
            select(QueryRecord).where(QueryRecord.id == record_id, QueryRecord.user_id == user.id)
        )
        if record is None:
            raise WorkspaceNotFoundError("Query history record not found.")
        return record

    @staticmethod
    def save(session: Session, user: AuthenticatedUser, record_id: UUID, name: str) -> SavedQuery:
        record = WorkspaceService.get_record(session, user, record_id)
        saved = SavedQuery(
            user_id=user.id,
            query_record_id=record.id,
            name=name.strip(),
            question=record.question,
            sql=record.sql,
            visualization=record.visualization,
        )
        session.add(saved)
        session.commit()
        session.refresh(saved)
        return saved

    @staticmethod
    def saved(session: Session, user: AuthenticatedUser) -> list[SavedQuery]:
        return list(
            session.scalars(
                select(SavedQuery)
                .where(SavedQuery.user_id == user.id)
                .order_by(desc(SavedQuery.created_at))
            )
        )

    @staticmethod
    def delete_saved(session: Session, user: AuthenticatedUser, saved_id: UUID) -> None:
        saved = session.scalar(
            select(SavedQuery).where(SavedQuery.id == saved_id, SavedQuery.user_id == user.id)
        )
        if saved is None:
            raise WorkspaceNotFoundError("Saved query not found.")
        session.delete(saved)
        session.commit()

    @staticmethod
    def settings(session: Session, user: AuthenticatedUser) -> UserSettings:
        settings = session.get(UserSettings, user.id)
        if settings is None:
            settings = UserSettings(user_id=user.id)
            session.add(settings)
            session.commit()
            session.refresh(settings)
        return settings
