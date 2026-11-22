"""AI Voice Assistant API Router (Module 13)."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from gramsetu.api.deps import get_store
from gramsetu.store import InMemoryStore
from gramsetu.schemas import VoiceQueryRequest, VoiceQueryResponse
from gramsetu.services.voice import process_voice_query

router = APIRouter(prefix="/voice", tags=["voice"])


@router.post("/query", response_model=VoiceQueryResponse)
async def api_voice_query(
    payload: VoiceQueryRequest,
    store: InMemoryStore = Depends(get_store),
):
    """Process natural language voice/text query in Bengali, Hindi, or English."""
    return process_voice_query(store, payload)
