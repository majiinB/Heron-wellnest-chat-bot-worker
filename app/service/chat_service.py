# app/service/chat_service.py
"""
Chat Service Module

Handles Pub/Sub message processing for chat messages, including:
- Receiving and validating Pub/Sub payloads
- Retrieving chat sessions and messages
- Decrypting encrypted message content
- Generating AI responses using Google Gemini
- Saving bot responses back to the database

@author Arthur M. Artugue
@created 2026-01-15
"""

from typing import Dict, Any, Optional
import json
from app.repository.chat_session_repository import ChatSessionRepository
from app.repository.chat_message_repository import ChatMessageRepository
from app.utils.crypto_utils import decrypt
from app.config.env_config import env
from app.config.gemini_config import client, get_model
from app.utils.logger_util import LoggerUtil
from app.utils.crypto_utils import encrypt
from sqlalchemy.exc import IntegrityError

class ChatService:
    """
    Service class for processing chat messages and generating AI responses.

    Handles the complete workflow from Pub/Sub message receipt to AI response generation.
    """

    HARD_STOP_TOTAL = 100
    HARD_STOP_ROLE = 50
    NEAR_STOP_TOTAL = 90
    NEAR_STOP_ROLE = 45
    PH_HOTLINE = "1553"  # National Center for Mental Health Crisis Hotline

    def __init__(self):
        """Initialize repositories and logger."""
        self.session_repo = ChatSessionRepository()
        self.message_repo = ChatMessageRepository()
        self.logger = LoggerUtil().logger
        self.encryption_key = env.CONTENT_ENCRYPTION_KEY

    async def process_chat_message(
        self,
        payload: Dict[str, Any],
        system_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process a chat message from Pub/Sub payload.

        This is the main entry point for handling chat messages. It:
        1. Validates and extracts payload data
        2. Retrieves session and verifies it's waiting_for_bot
        3. Retrieves the specific message from the payload
        4. Retrieves last 5 messages before the current message as context
        5. Checks if bot has already responded (idempotency)
        6. Decrypts all messages and builds conversation context
        7. Generates AI response using Gemini
        8. Encrypts and saves bot response to database
        9. Updates session status to active

        Args:
            payload: Pub/Sub message payload containing:
                - userId: User identifier
                - sessionId: Chat session identifier
                - messageId: Message identifier
                - timestamp: ISO timestamp of message creation
                - eventType (optional): Event type identifier
            system_prompt: Optional engineered prompt to guide AI behavior

        Returns:
            Dict containing:
                - success: Boolean indicating operation success
                - skipped: (Optional) Boolean indicating if response was skipped
                - reason: (Optional) Reason for skipping
                - error: Error message (if failed)

        Raises:
            ValueError: If payload is invalid or missing required fields
            Exception: For database or AI generation errors
        """
        # Initialize variables for error handling
        user_id = None
        session_id = None

        try:
            # Step 1: Validate and extract payload
            self.logger.info(f"Processing chat message payload: {payload}")
            user_id = payload.get("userId")
            session_id = payload.get("sessionId")
            message_id = payload.get("messageId")

            if not all([user_id, session_id, message_id]):
                raise ValueError("Missing required fields: userId, sessionId, or messageId")

            # Step 2: Retrieve session
            self.logger.info(f"Retrieving session {session_id} for user {user_id}")
            session = await self.session_repo.find_session_by_id(session_id, user_id)

            if not session:
                raise ValueError(f"Session {session_id} not found for user {user_id}")

            # Step 3: Check session status - only respond if waiting_for_bot
            if session["status"] != "waiting_for_bot":
                self.logger.warning(f"Session {session_id} status is {session['status']}, not waiting_for_bot. Skipping.")
                return {
                    "success": False,
                    "error": f"Session is not waiting for bot response (status: {session['status']})"
                }

            # Step 4: Retrieve the specific message from the payload
            self.logger.info(f"Retrieving message {message_id}")
            current_message = await self.message_repo.find_message_by_id(session_id, message_id, user_id)

            if not current_message:
                raise ValueError(f"Message {message_id} not found")

            # Verify message is from student
            if current_message["role"] != "student":
                self.logger.warning(f"Message {message_id} is not from student (role: {current_message['role']})")
                return {
                    "success": False,
                    "error": "Message is not from student"
                }

            context_limit = 5

            # Step 5: Retrieve last 5 messages before the current message as context
            self.logger.info(f"Retrieving last {context_limit} messages before message {message_id} for context")
            previous_messages = await self.message_repo.find_by_message_before_id(
                session_id=session_id,
                user_id=user_id,
                last_message_id=message_id,
                limit=context_limit
            )

            # Step 6: Check if bot has already responded to this message (idempotency check)
            self.logger.info(f"Checking if bot has already responded to message {message_id}")
            messages_after_current = await self.message_repo.find_messages_after_id(
                session_id=session_id,
                user_id=user_id,
                after_message_id=message_id,
                limit=5  # Check next 5 messages for bot response
            )

            # Look for any bot message after the current student message
            bot_response_exists = any(msg["role"] == "bot" for msg in messages_after_current)

            if bot_response_exists:
                self.logger.warning(f"Bot has already responded to message {message_id}. Skipping to maintain idempotency.")
                # Update session back to active if needed
                if session["status"] == "waiting_for_bot":
                    await self.session_repo.update_session(
                        session_id=session_id,
                        user_id=user_id,
                        status="active"
                    )

                return {
                    "success": True,
                    "skipped": True,
                    "reason": "Bot response already exists for this message"
                }

            # Step 6.5: Count messages for limit enforcement (non-deleted)
            total_count = await self.message_repo.count_messages_total(session_id, user_id)
            student_count = await self.message_repo.count_messages_by_role(session_id, user_id, "student")
            bot_count = await self.message_repo.count_messages_by_role(session_id, user_id, "bot")

            hard_stop = (
                total_count >= self.HARD_STOP_TOTAL or
                student_count >= self.HARD_STOP_ROLE or
                bot_count >= self.HARD_STOP_ROLE
            )
            near_limit = (
                total_count >= self.NEAR_STOP_TOTAL or
                student_count >= self.NEAR_STOP_ROLE or
                bot_count >= self.NEAR_STOP_ROLE
            )

            # Step 7: Decrypt current message and previous messages, build conversation context
            self.logger.info(f"Decrypting current message and {len(previous_messages)} previous messages")
            conversation_context = self._build_conversation_context(
                previous_messages,
                current_message,
                near_limit=near_limit,
                hard_stop=hard_stop
            )

            # Step 8: Generate AI response using Gemini (or graceful close on hard stop)
            self.logger.info(f"Generating AI response for session {session_id}")

            if hard_stop:
                bot_response_text = (
                    "Salamat sa pag-share. Kailangan na nating tapusin ang usapan para hindi humaba masyado. "
                    "Kung gusto mo, pwede kitang i-connect sa CGCS para sa counseling o kamustahan session. "
                    f"Kung urgent ang tulong na kailangan mo, tumawag sa {self.PH_HOTLINE}."
                )
                should_notify = False
            else:
                ai_payload = await self.generate_ai_response(
                    conversation_context=conversation_context,
                    system_prompt=system_prompt,
                    near_limit=near_limit
                )

                bot_response_text = ai_payload.get("response") or "I apologize, but I could not generate a response right now."
                should_notify = bool(ai_payload.get("should_notify"))

                if should_notify:
                    # Placeholder for future Pub/Sub notification to counselor
                    self.logger.warning("Self-harm indication detected; notify workflow placeholder triggered")

            # Step 9: Calculate next sequence number and save bot response with retry logic
            # Handles race condition when multiple requests try to use the same sequence number

            max_retries = 3
            retry_count = 0
            bot_message_saved = False
            next_sequence = 0  # Initialize for error handling

            while retry_count < max_retries and not bot_message_saved:
                try:
                    # Calculate next sequence number
                    latest_message = await self.message_repo.find_latest_message_by_session(user_id, session_id)
                    next_sequence = (latest_message["sequence_number"] + 1) if latest_message else 1

                    self.logger.info(f"Attempting to save bot response with sequence number {next_sequence} (attempt {retry_count + 1}/{max_retries})")

                    # Step 10: Encrypt and save bot response to database
                    encrypted_response = encrypt(bot_response_text, self.encryption_key)

                    await self.message_repo.create_message(
                        user_id=user_id,
                        session_id=session_id,
                        role="bot",
                        content_encrypted=encrypted_response,
                        sequence_number=next_sequence
                    )

                    bot_message_saved = True
                    self.logger.info(f"Successfully saved bot response with sequence number {next_sequence}")

                except IntegrityError as ie:
                    # Handle unique constraint violation (sequence number collision)
                    if "unique_session_sequence" in str(ie.orig).lower() or "duplicate" in str(ie.orig).lower():
                        retry_count += 1
                        self.logger.warning(f"Sequence number {next_sequence} already exists. Retrying... (attempt {retry_count}/{max_retries})")

                        if retry_count >= max_retries:
                            self.logger.error(f"Failed to save bot response after {max_retries} attempts due to sequence number conflicts")
                            raise Exception(f"Failed to save message after {max_retries} retries due to sequence number conflicts")
                    else:
                        # Different integrity error, re-raise
                        raise

            if not bot_message_saved:
                raise Exception("Failed to save bot message due to unknown error")

            # Step 11: Update session status to active
            await self.session_repo.update_session(
                session_id=session_id,
                user_id=user_id,
                status="active"
            )

            self.logger.info(f"Successfully processed session {session_id} and saved bot response")

            # Return minimal success response (no message content to avoid leaks)
            return {
                "success": True
            }

        except ValueError as ve:
            self.logger.error(f"Validation error: {str(ve)}")
            return {
                "success": False,
                "error": str(ve)
            }
        except Exception as e:
            self.logger.error(f"Error processing chat message: {str(e)}", exc_info=True)

            # Try to update session to failed status
            try:
                if session_id and user_id:
                    await self.session_repo.update_session(
                        session_id=session_id,
                        user_id=user_id,
                        status="failed"
                    )
            except Exception as update_error:
                self.logger.error(f"Failed to update session status: {str(update_error)}")

            return {
                "success": False,
                "error": str(e)
            }

    async def generate_ai_response(
        self,
        conversation_context: str,
        system_prompt: Optional[str] = None,
        near_limit: bool = False
    ) -> Dict[str, Any]:
        """
        Generate an AI response using Google Gemini.

        Args:
            conversation_context: The formatted conversation history
            system_prompt: Optional system instruction to guide AI behavior
            near_limit: Whether the conversation is nearing the hard stop

        Returns:
            Dict with keys: response (str), should_notify (bool)

        Raises:
            Exception: If AI generation fails
        """
        try:
            # Default system prompt if none provided
            if not system_prompt:
                system_prompt = f"""
You are a helpful, empathetic, and safety-aware mental health support chatbot for students.
Output strictly as JSON with keys: response (string), should_notify (boolean).
Set should_notify=true if you see indications of self-harm or suicide risk. Otherwise false.
Tone: warm, respectful, not overly validating; give encouraging, actionable, context-aware guidance.
Offer counselor/booking pathways when user seems very negative or asks for help; mention CGCS counseling or kamustahan sessions when wrapping up.
If topic is family/relationships, tailor advice to the context; offer supportive encouragement (e.g., failure is part of success) without empty validation.
Be conversational: ask brief follow-ups or invitations to share more, unless wrapping up.
Handle gibberish by politely asking for clarity (e.g., "what are you trying to say?"). Handle swearing calmly and redirect constructively.
Use respectful "real talk" but avoid offense.
If user expresses self-harm, encourage immediate help and include PH hotline {self.PH_HOTLINE}.
When nearing session limit, start guiding toward a graceful close.
"""

            if near_limit:
                system_prompt += "\nYou are close to the session message limit; start wrapping up and propose next steps."

            response_schema = {
                "type": "object",
                "properties": {
                    "response": {"type": "string"},
                    "should_notify": {"type": "boolean"}
                },
                "required": ["response", "should_notify"],
            }

            # Get model configuration
            model_id, config = get_model(
                temperature=0.8,
                max_output_tokens=1024,
                response_mime_type="application/json",
                response_schema=response_schema,
                system_instruction=system_prompt
            )

            # Generate response
            self.logger.info(f"Calling Gemini API")
            response = client.models.generate_content(
                model=model_id,
                contents=conversation_context,
                config=config
            )

            # Parse structured response
            raw_text = response.text if response and response.text else None
            parsed: Dict[str, Any] = {"response": None, "should_notify": False}

            if raw_text:
                try:
                    parsed_json = json.loads(raw_text)
                    parsed["response"] = parsed_json.get("response")
                    parsed["should_notify"] = bool(parsed_json.get("should_notify"))
                except Exception:
                    self.logger.warning("Failed to parse structured Gemini response; falling back to text")
                    parsed["response"] = raw_text

            if not parsed["response"]:
                parsed["response"] = "I apologize, but I'm having trouble generating a response right now. Could you please try again?"

            self.logger.info(f"Generated AI response: {str(parsed['response'])[:100]}...")

            return parsed

        except Exception as e:
            self.logger.error(f"Error generating AI response: {str(e)}", exc_info=True)
            raise Exception(f"Failed to generate AI response: {str(e)}")

    def _build_conversation_context(
        self,
        previous_messages: list[Dict[str, Any]],
        current_message: Dict[str, Any],
        near_limit: bool = False,
        hard_stop: bool = False
    ) -> str:
        """
        Build conversation context from previous messages and current message.

        Args:
            previous_messages: List of previous message dictionaries (ordered by created_at DESC)
            current_message: The current message from the user that triggered the bot
            near_limit: Whether the conversation is close to the hard stop
            hard_stop: Whether the conversation hit the hard stop

        Returns:
            Formatted conversation context string
        """
        # Reverse previous messages to get chronological order
        messages = list(reversed(previous_messages)) if previous_messages else []

        context_lines = []

        if messages:
            context_lines.append("Previous conversation:")
            for msg in messages:
                role = "Student" if msg["role"] == "student" else "Bot"
                # Decrypt message if needed
                try:
                    if isinstance(msg["content_encrypted"], dict):
                        content = decrypt(msg["content_encrypted"], self.encryption_key)
                    else:
                        content = str(msg["content_encrypted"])
                except Exception as e:
                    self.logger.warning(f"Failed to decrypt message in history: {str(e)}")
                    content = "[Unable to decrypt message]"

                context_lines.append(f"{role}: {content}")
        else:
            context_lines.append("This is the start of the conversation.")

        # Add current student message
        try:
            if isinstance(current_message["content_encrypted"], dict):
                current_content = decrypt(current_message["content_encrypted"], self.encryption_key)
            else:
                current_content = str(current_message["content_encrypted"])
        except Exception as e:
            self.logger.error(f"Failed to decrypt current message: {str(e)}")
            raise Exception(f"Cannot decrypt current message: {str(e)}")

        if hard_stop:
            context_lines.append("\nSystem: Conversation has reached the limit; provide a short wrap-up and offer CGCS counseling or kamustahan.")
        elif near_limit:
            context_lines.append("\nSystem: Conversation is nearing the limit; start guiding toward a wrap-up and offer next steps.")

        context_lines.append(f"\nStudent: {current_content}")

        return "\n".join(context_lines)

    async def generate_custom_response(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.8,
        max_tokens: int = 1024
    ) -> str:
        """
        Generate a custom AI response with full control over parameters.

        Useful for testing or specific use cases where you need full control
        over the generation parameters.

        Args:
            prompt: The input prompt
            system_instruction: Optional system instruction
            temperature: Temperature for generation (0.0-2.0)
            max_tokens: Maximum output tokens

        Returns:
            Generated response text
        """
        try:
            model_id, config = get_model(
                temperature=temperature,
                max_output_tokens=max_tokens,
                response_mime_type="text/plain",
                system_instruction=system_instruction
            )

            response = client.models.generate_content(
                model=model_id,
                contents=prompt,
                config=config
            )

            return response.text if response.text else ""

        except Exception as e:
            self.logger.error(f"Error in custom response generation: {str(e)}")
            raise

