from fastapi import APIRouter, Request
from app.controller.chat_controller import ChatController

router = APIRouter()
chat_controller = ChatController()

@router.post("/pubsub/chat-bot")
async def receive_pubsub(request: Request):
    """
    Endpoint to receive Pub/Sub messages for chatbot processing.

    Args:
        request: The FastAPI Request object containing the Pub/Sub message

    Returns:
        JSON response with status and optional error message
    """
    response_dict, status_code = await chat_controller.handle_pubsub_message(request)
    return response_dict, status_code

