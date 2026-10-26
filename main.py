import os
import time
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from google import genai

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY is not set in .env file")

client = genai.Client(api_key=api_key)
app = FastAPI(title="Free Stack AI API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class PromptRequest(BaseModel):
    prompt: str

# Free-tier Flash models (Pro models have 0 limit on unpaid keys)
MODELS_TO_TRY = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-3.8-flash",
    "gemini-3.5-flash",
]

@app.get("/")
def health_check():
    return {"status": "ok", "message": "Free Stack AI Backend Running"}

@app.post("/generate")
def generate_text(request: PromptRequest):
    last_error = None
    for model_name in MODELS_TO_TRY:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=request.prompt
            )
            return {
                "response": response.text,
                "model_used": model_name
            }
        except Exception as e:
            err_str = str(e)
            last_error = f"{model_name}: {err_str}"
            # Retry once on temporary 503 high-demand spike
            if "503" in err_str or "UNAVAILABLE" in err_str:
                time.sleep(1)
                try:
                    response = client.models.generate_content(
                        model=model_name,
                        contents=request.prompt
                    )
                    return {
                        "response": response.text,
                        "model_used": model_name
                    }
                except Exception as retry_err:
                    last_error = f"{model_name} retry: {str(retry_err)}"
            # Move immediately to the next Flash model on 429 or 404
            continue

    raise HTTPException(
        status_code=503,
        detail=f"All model targets currently unavailable. Last error: {last_error}"
    )
