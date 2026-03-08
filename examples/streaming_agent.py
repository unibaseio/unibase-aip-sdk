#!/usr/bin/env python3
"""
Streaming Agent Example
Demonstrates how to use raw streaming response with user_id injection and ag_ui protocol.
"""
from openai import AsyncOpenAI
from typing import AsyncIterator
from aip_sdk.types import AgentSkillCard

from aip_sdk import expose_as_a2a
from ag_ui.core import TextMessageContentEvent, EventType, UserMessage, TextInputContent
from ag_ui.encoder import EventEncoder

async def openai_streaming_handler(input_text: str, user_id: str = "anonymous") -> AsyncIterator[str]:
    """Streaming OpenAI handler with user_id injection using ag_ui."""
    
    print(f"[Handler] Received input: {input_text}")
    print(f"[Handler] User ID: {user_id}")
    
    # In real usage: from openai import AsyncOpenAI
    client = AsyncOpenAI()
    
    # Create UserMessage using ag_ui
    message = UserMessage(
        id="msg_input",
        content=[
            TextInputContent(text=input_text),
        ],
        role="user"
    )
    # payload = message.model_dump(by_alias=True)
    # print(f"[Handler] Usage: Payload for OpenAI: {payload}")

    # Generate message ID for the stream
    stream = await client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": input_text}],
        max_tokens=1024,
        stream=True,
    )
    encoder = EventEncoder()
    
    async for chunk in stream:
        if chunk.choices[0].delta.content:
            # Use ag_ui TextMessageContentEvent
            event = TextMessageContentEvent(
                type=EventType.TEXT_MESSAGE_CONTENT,
                message_id=chunk.id,
                delta=chunk.choices[0].delta.content,
            )
            sse_data = encoder.encode(event)
            yield sse_data

def main():
    print("Starting Streaming Agent with ag_ui...")
    
    # Expose agent with raw_response=True which will be used by /a2a/stream-agui
    server = expose_as_a2a(
        name="Streaming Agent",
        handler=openai_streaming_handler,
        port=8000,
        streaming=True,
        raw_response=True, # Enable raw response support
        description="Agent with raw streaming response and ag_ui",
        skills=[
            AgentSkillCard(
                id="story.teller",
                name="Story Teller",
                description="Generates long stories with streaming response",
                tags=["creative", "story", "streaming"],
            )
        ],
    )
    
    server.run_sync()

if __name__ == "__main__":
    main()
