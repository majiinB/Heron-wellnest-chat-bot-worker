# app/repository/chat_session_repository.py
"""
Repository for managing chat session database operations.

Provides methods for creating, retrieving, updating, and deleting chat sessions
using SQLAlchemy with async support and raw SQL queries.
"""

from typing import Optional
from sqlalchemy.exc import IntegrityError
from sqlalchemy import text
from app.utils.db_utils import fetch_one, fetch_all, execute_query
from app.config.datasource_config import SessionLocal


class ChatSessionRepository:
    """
    Repository class for ChatSession database operations.

    Handles CRUD operations and business logic for chat sessions including
    race condition handling and optimistic locking.
    """
    async def find_session_by_id(
        self,
        session_id: str,
        user_id: str
    ) -> Optional[dict]:
        """
        Retrieves a chat session by its unique identifier.

        Args:
            session_id: The unique identifier of the chat session to retrieve.
            user_id: The unique identifier of the user who owns the chat session.

        Returns:
            The chat session as a dict if found, otherwise None.
        """
        query = """
            SELECT * FROM chat_sessions
            WHERE session_id = :session_id AND user_id = :user_id
        """
        result = await fetch_one(query, {"session_id": session_id, "user_id": user_id})
        return dict(result) if result else None

    async def update_session(
        self,
        session_id: str,
        user_id: str,
        **updates
    ) -> Optional[dict]:
        """
        Updates a chat session entry with new values.

        Args:
            session_id: The unique identifier of the chat session.
            user_id: The unique identifier of the user who owns the session.
            **updates: Key-value pairs of fields to update (e.g., status='ended').

        Returns:
            The updated chat session if found, otherwise None.

        Remarks:
            Updates the updated_at timestamp automatically.
            For optimistic locking, include version in updates and WHERE clause.
        """
        if not updates:
            return await self.find_session_by_id(session_id, user_id)

        # Build SET clause dynamically
        set_clauses = [f"{key} = :{key}" for key in updates.keys()]
        set_clauses.append("updated_at = NOW()")
        set_clause = ", ".join(set_clauses)

        query = f"""
            UPDATE chat_sessions
            SET {set_clause}
            WHERE session_id = :session_id AND user_id = :user_id
            RETURNING *
        """

        params = {**updates, "session_id": session_id, "user_id": user_id}

        async with SessionLocal() as session:
            result = await session.execute(text(query), params)
            await session.commit()
            updated_session = result.mappings().first()
            return dict(updated_session) if updated_session else None

    async def find_latest_user_session(self, user_id: str) -> Optional[dict]:
        """
        Retrieves the latest in-progress chat session for a specific user.

        In-progress sessions are those not in terminal states (ended/escalated).
        This includes: active, waiting_for_bot, and failed (can transition back).

        Args:
            user_id: The unique identifier of the user whose latest chat session is to be fetched.

        Returns:
            The most recent in-progress session for the user as a dict, or None if none exists.
        """
        query = """
            SELECT * FROM chat_sessions
            WHERE user_id = :user_id 
                AND status IN ('active', 'waiting_for_bot', 'failed')
            ORDER BY created_at DESC
            LIMIT 1
        """
        result = await fetch_one(query, {"user_id": user_id})
        return dict(result) if result else None

    async def count_user_session(self, user_id: str) -> int:
        """
        Counts the number of chat sessions for a specific user.

        Args:
            user_id: The unique identifier of the user whose chat sessions are to be counted.

        Returns:
            The count of chat sessions for the specified user.
        """
        query = """
            SELECT COUNT(*) as count FROM chat_sessions
            WHERE user_id = :user_id
        """
        result = await fetch_one(query, {"user_id": user_id})
        return result["count"] if result else 0

