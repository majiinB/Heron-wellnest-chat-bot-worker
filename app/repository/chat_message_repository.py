# app/repository/chat_message_repository.py
"""
Repository for managing chat message database operations.

Provides methods for creating, retrieving, updating, and deleting chat messages
using SQLAlchemy with async support and raw SQL queries.
"""

from typing import Optional, List, Literal
from app.utils.db_utils import fetch_one, fetch_all, execute_query
from app.config.datasource_config import SessionLocal
from sqlalchemy import text


class ChatMessageRepository:
    """
    Repository class for ChatMessage database operations.

    Handles CRUD operations for chat messages including pagination,
    soft deletes, and role-based queries.
    """

    async def create_message(
        self,
        user_id: str,
        session_id: str,
        role: Literal["student", "bot"],
        content_encrypted: dict,
        sequence_number: int,
    ) -> dict:
        """
        Creates a new chat message for the bot.

        Args:
            user_id: The unique identifier of the user creating the message.
            session_id: The unique identifier of the chat session.
            role: The role of the message sender ('student' or 'bot').
            content_encrypted: The encrypted content field as a dictionary.
            sequence_number: The sequence number of the message in the session.

        Returns:
            The saved chat message entity as a dict.
        """
        import json

        query = """
            INSERT INTO chat_messages 
                (user_id, session_id, role, content_encrypted, sequence_number, created_at)
            VALUES 
                (:user_id, :session_id, :role, :content_encrypted, :sequence_number, NOW())
            RETURNING *
        """

        async with SessionLocal() as session:
            result = await session.execute(
                text(query),
                {
                    "user_id": user_id,
                    "session_id": session_id,
                    "role": role,
                    "content_encrypted": json.dumps(content_encrypted),  # Convert dict to JSON string
                    "sequence_number": sequence_number,
                }
            )
            await session.commit()
            chat_message = result.mappings().first()
            return dict(chat_message)

    async def find_message_by_id(
        self,
        session_id: str,
        message_id: str,
        user_id: str
    ) -> Optional[dict]:
        """
        Retrieves a chat message by its ID for a specific user.

        Args:
            session_id: The unique identifier of the chat session.
            message_id: The unique identifier of the chat message to retrieve.
            user_id: The unique identifier of the user who owns the chat message.

        Returns:
            The chat message as a dict if found, otherwise None.
        """
        query = """
            SELECT * FROM chat_messages
            WHERE session_id = :session_id 
                AND message_id = :message_id 
                AND user_id = :user_id
        """
        result = await fetch_one(
            query,
            {"session_id": session_id, "message_id": message_id, "user_id": user_id}
        )
        return dict(result) if result else None

    async def find_latest_user_message_by_session(
        self,
        user_id: str,
        session_id: str
    ) -> Optional[dict]:
        """
        Retrieves the latest chat message from a student for a specific session.

        Args:
            user_id: The unique identifier of the user whose latest message is to be fetched.
            session_id: The unique identifier of the chat session.

        Returns:
            The most recent student message for the session, or None if none exists.
        """
        query = """
            SELECT * FROM chat_messages
            WHERE user_id = :user_id 
                AND session_id = :session_id 
                AND role = 'student'
                AND is_deleted = FALSE
            ORDER BY created_at DESC
            LIMIT 1
        """
        result = await fetch_one(
            query,
            {"user_id": user_id, "session_id": session_id}
        )
        return dict(result) if result else None

    async def find_latest_bot_message_by_session(
        self,
        user_id: str,
        session_id: str
    ) -> Optional[dict]:
        """
        Retrieves the latest bot message for a specific session.

        Args:
            user_id: The unique identifier of the user whose latest bot message is to be fetched.
            session_id: The unique identifier of the chat session.

        Returns:
            The most recent bot message for the session, or None if none exists.
        """
        query = """
            SELECT * FROM chat_messages
            WHERE user_id = :user_id 
                AND session_id = :session_id 
                AND role = 'bot'
                AND is_deleted = FALSE
            ORDER BY created_at DESC
            LIMIT 1
        """
        result = await fetch_one(
            query,
            {"user_id": user_id, "session_id": session_id}
        )
        return dict(result) if result else None

    async def find_latest_message_by_session(
        self,
        user_id: str,
        session_id: str
    ) -> Optional[dict]:
        """
        Retrieves the latest chat message (any role) for a specific session.

        Args:
            user_id: The unique identifier of the user whose latest message is to be fetched.
            session_id: The unique identifier of the chat session.

        Returns:
            The most recent chat message for the session, or None if none exists.
        """
        query = """
            SELECT * FROM chat_messages
            WHERE user_id = :user_id 
                AND session_id = :session_id 
                AND is_deleted = FALSE
            ORDER BY created_at DESC
            LIMIT 1
        """
        result = await fetch_one(
            query,
            {"user_id": user_id, "session_id": session_id}
        )
        return dict(result) if result else None

    async def hard_delete(
        self,
        session_id: str,
        message_id: str,
        user_id: str
    ) -> None:
        """
        Permanently deletes a chat message entry from the repository by its ID.

        Args:
            session_id: The unique identifier of the chat session.
            message_id: The unique identifier of the message to delete.
            user_id: The unique identifier of the user who owns the message.
        """
        query = """
            DELETE FROM chat_messages
            WHERE session_id = :session_id 
                AND message_id = :message_id 
                AND user_id = :user_id
        """
        await execute_query(
            query,
            {"session_id": session_id, "message_id": message_id, "user_id": user_id}
        )

    async def soft_delete(
        self,
        session_id: str,
        message_id: str,
        user_id: str
    ) -> None:
        """
        Soft deletes a chat message entry by setting its is_deleted flag to True.

        Args:
            session_id: The unique identifier of the chat session.
            message_id: The unique identifier of the message to soft delete.
            user_id: The unique identifier of the user who owns the message.
        """
        query = """
            UPDATE chat_messages
            SET is_deleted = TRUE
            WHERE session_id = :session_id 
                AND message_id = :message_id 
                AND user_id = :user_id
        """
        await execute_query(
            query,
            {"session_id": session_id, "message_id": message_id, "user_id": user_id}
        )

    async def count_user_messages(
        self,
        user_id: str,
        session_id: str
    ) -> int:
        """
        Counts the number of chat messages for a specific user and session.

        Args:
            user_id: The unique identifier of the user whose messages are to be counted.
            session_id: The unique identifier of the chat session.

        Returns:
            The count of chat messages for the specified user and session.
        """
        query = """
            SELECT COUNT(*) as count FROM chat_messages
            WHERE user_id = :user_id AND session_id = :session_id
        """
        result = await fetch_one(query, {"user_id": user_id, "session_id": session_id})
        return result["count"] if result else 0

    async def find_by_message_before_id(
        self,
        session_id: str,
        user_id: str,
        last_message_id: Optional[str] = None,
        limit: int = 10,
    ) -> List[dict]:
        """
        Retrieves chat messages for a specific session with cursor-based pagination.

        Uses created_at and message_id for stable pagination ordering.

        Args:
            session_id: The unique identifier of the chat session.
            user_id: The unique identifier of the user whose messages are to be fetched.
            last_message_id: (Optional) The ID of the last message from the previous page.
            limit: (Optional) The maximum number of messages to retrieve. Defaults to 10.

        Returns:
            A list of chat messages as dicts, ordered by creation date DESC.
        """
        if not last_message_id:
            # First page: no cursor
            query = """
                SELECT * FROM chat_messages
                WHERE session_id = :session_id 
                    AND user_id = :user_id 
                    AND is_deleted = FALSE
                ORDER BY created_at DESC, message_id DESC
                LIMIT :limit
            """
            params = {"session_id": session_id, "user_id": user_id, "limit": limit}
        else:
            # Fetch the last message to get its created_at timestamp
            last_entry_query = """
                SELECT created_at, message_id FROM chat_messages
                WHERE message_id = :last_message_id
            """
            last_entry = await fetch_one(last_entry_query, {"last_message_id": last_message_id})

            if not last_entry:
                # Invalid cursor, return empty list
                return []

            # Cursor-based pagination: fetch messages before the last message
            query = """
                SELECT * FROM chat_messages
                WHERE session_id = :session_id 
                    AND user_id = :user_id 
                    AND is_deleted = FALSE
                    AND (
                        created_at < :last_created_at
                        OR (created_at = :last_created_at AND message_id < :last_message_id)
                    )
                ORDER BY created_at DESC, message_id DESC
                LIMIT :limit
            """
            params = {
                "session_id": session_id,
                "user_id": user_id,
                "last_created_at": last_entry["created_at"],
                "last_message_id": last_message_id,
                "limit": limit,
            }

        results = await fetch_all(query, params)
        return [dict(row) for row in results]

    async def find_messages_after_id(
        self,
        session_id: str,
        user_id: str,
        after_message_id: str,
        limit: int = 10,
    ) -> List[dict]:
        """
        Retrieves chat messages AFTER a specific message ID (for idempotency checks).

        Uses created_at and message_id for stable ordering.

        Args:
            session_id: The unique identifier of the chat session.
            user_id: The unique identifier of the user whose messages are to be fetched.
            after_message_id: The ID of the message to query after.
            limit: (Optional) The maximum number of messages to retrieve. Defaults to 10.

        Returns:
            A list of chat messages as dicts that come after the specified message.
        """
        # Fetch the reference message to get its created_at timestamp
        reference_query = """
            SELECT created_at, message_id FROM chat_messages
            WHERE message_id = :after_message_id
        """
        reference_message = await fetch_one(reference_query, {"after_message_id": after_message_id})

        if not reference_message:
            # Reference message not found, return empty list
            return []

        # Fetch messages after the reference message
        query = """
            SELECT * FROM chat_messages
            WHERE session_id = :session_id 
                AND user_id = :user_id 
                AND is_deleted = FALSE
                AND (
                    created_at > :reference_created_at
                    OR (created_at = :reference_created_at AND message_id > :after_message_id)
                )
            ORDER BY created_at ASC, message_id ASC
            LIMIT :limit
        """
        params = {
            "session_id": session_id,
            "user_id": user_id,
            "reference_created_at": reference_message["created_at"],
            "after_message_id": after_message_id,
            "limit": limit,
        }

        results = await fetch_all(query, params)
        return [dict(row) for row in results]

