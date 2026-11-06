import os
import json
import asyncio
import httpx
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from google import genai
from google.genai import types

load_dotenv()

app = FastAPI(title="Hybrid Free AI Gateway")

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
GEMINI_FIRST_CHUNK_TIMEOUT = float(os.getenv("GEMINI_FIRST_CHUNK_TIMEOUT", "30"))
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")

# Set timeout to 60,000ms (60s) so active streams aren't killed mid-response
gemini_client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY"),
    http_options=types.HttpOptions(timeout=60000)
)

async def stream_generator(prompt: str):
    """
    Asynchronously streams responses from Gemini 3.5 Flash.
    Enforces a configurable timeout on the FIRST token chunk, then allows up to 60s for completion.
    """
    try:
        cloud_stream = await gemini_client.aio.models.generate_content_stream(
            model=GEMINI_MODEL,
            contents=prompt,
        )
        
        # Bound the wait for the first token so slow cloud responses can still start.
        stream_iter = cloud_stream.__aiter__()
        first_chunk = await asyncio.wait_for(
            stream_iter.__anext__(), timeout=GEMINI_FIRST_CHUNK_TIMEOUT
        )
        
        if first_chunk.text:
            yield f"data: {json.dumps({'source': 'cloud-gemini', 'model': GEMINI_MODEL, 'text': first_chunk.text})}\n\n"

        # Stream remaining chunks freely
        async for chunk in stream_iter:
            if chunk.text:
                yield f"data: {json.dumps({'source': 'cloud-gemini', 'model': GEMINI_MODEL, 'text': chunk.text})}\n\n"

    except Exception as cloud_err:
        print(f"[CLOUD ROUTE FAILED] Model: '{GEMINI_MODEL}' | Error: {type(cloud_err).__name__}: {cloud_err}")
        yield f"data: {json.dumps({'info': f'Cloud route unavailable ({type(cloud_err).__name__}). Switching to local Ollama...'})}\n\n"
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                async with client.stream(
                    "POST",
                    f"{OLLAMA_HOST}/api/generate",
                    json={"model": "qwen2.5:1.5b", "prompt": prompt, "stream": True}
                ) as ollama_resp:
                    async for line in ollama_resp.aiter_lines():
                        if line:
                            data = json.loads(line)
                            token = data.get("response", "")
                            if token:
                                yield f"data: {json.dumps({'source': 'local-ollama-fallback', 'model': 'qwen2.5:1.5b', 'text': token})}\n\n"
        except Exception as local_err:
            print(f"[LOCAL ROUTE FAILED] Error: {type(local_err).__name__}: {local_err}")
            yield f"data: {json.dumps({'error': f'Both engines failed. Local error: {str(local_err)}'})}\n\n"

@app.post("/stream")
async def stream_ai_response(prompt: str):
    return StreamingResponse(
        stream_generator(prompt), 
        media_type="text/event-stream"
    )
