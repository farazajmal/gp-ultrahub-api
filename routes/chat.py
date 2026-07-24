from fastapi import APIRouter
from pydantic import BaseModel

from services.ai_service import chat

router = APIRouter()


class ChatRequest(BaseModel):
    session_id: str
    message: str


@router.post("/chat")
def chat_endpoint(request: ChatRequest):

    reply = chat(
        request.session_id,
        request.message
    )

    return {
        "response": reply
    }