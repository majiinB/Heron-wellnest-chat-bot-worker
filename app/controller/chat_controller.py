# app/controller/chat_controller.py
"""
Chat Controller Module

Handles HTTP request parsing and validation for Pub/Sub messages.
Delegates business logic to ChatService.

@author Arthur M. Artugue
@created 2026-01-17
"""

import base64
import json
from typing import Dict, Any
from app.service.chat_service import ChatService
from app.utils.logger_util import LoggerUtil


class ChatController:
    """
    Controller for handling chat-related HTTP requests.

    Responsible for:
    - Parsing Pub/Sub message envelopes
    - Validating message structure
    - Decoding base64-encoded payloads
    - Delegating to ChatService for business logic
    """

    def __init__(self):
        """Initialize controller with service and logger."""
        self.chat_service = ChatService()
        self.logger = LoggerUtil().logger

    async def handle_pubsub_message(self, request) -> tuple[Dict[str, Any], int]:
        """
        Handle incoming Pub/Sub message from HTTP request.

        Validates the Pub/Sub message format and extracts the payload,
        then delegates to ChatService for processing.

        Args:
            request: The HTTP request object (should have .json() method)

        Returns:
            Tuple of (response_dict, status_code)

        Example Pub/Sub envelope structure:
        {
            "message": {
                "data": "base64-encoded-json-payload",
                "messageId": "...",
                "publishTime": "..."
            },
            "subscription": "..."
        }
        """
        try:
            # Parse request body
            envelope = await request.json()

            # Validate envelope structure
            if not envelope or "message" not in envelope:
                self.logger.error("Invalid Pub/Sub message format")
                return {"error": "Bad Request"}, 400

            if "message" not in envelope:
                self.logger.error("No message field in Pub/Sub message")
                return {"error": "Bad Request"}, 400

            pubsub_message = envelope["message"]

            # Validate message data field
            if "data" not in pubsub_message:
                self.logger.error("No data field in Pub/Sub message")
                return {"error": "Bad Request"}, 400

            # Decode the Pub/Sub message data
            try:
                data_str = base64.b64decode(pubsub_message["data"]).decode("utf-8")
                payload = json.loads(data_str)
                self.logger.info(f"Successfully decoded Pub/Sub payload: {payload}")
            except (ValueError, UnicodeDecodeError) as e:
                self.logger.error(f"Failed to decode base64 data: {str(e)}")
                return {"error": "Invalid base64 encoding"}, 400
            except json.JSONDecodeError as e:
                self.logger.error(f"Failed to parse JSON payload: {str(e)}")
                return {"error": "Invalid JSON payload"}, 400

            # Delegate to service for processing
            result = await self.chat_service.process_chat_message(payload)

            # Return appropriate response based on result
            if result.get("success"):
                if result.get("skipped"):
                    self.logger.info(f"Message processing skipped: {result.get('reason')}")
                    return {"status": "skipped", "reason": result.get("reason")}, 200
                else:
                    self.logger.info("Message processed successfully")
                    return {"status": "success"}, 200
            else:
                error_msg = result.get("error", "Unknown error")
                self.logger.error(f"Message processing failed: {error_msg}")
                return {"error": error_msg}, 500

        except Exception as e:
            self.logger.error(f"Unexpected error in handle_pubsub_message: {str(e)}", exc_info=True)
            return {"error": "Internal server error"}, 500

