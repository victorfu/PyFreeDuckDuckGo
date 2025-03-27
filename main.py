from fastapi import FastAPI
from duckduckgo import chat_completions, OpenAIRequest

app = FastAPI()


@app.get("/")
async def read_root():
    return {
        "message": "Hello! Thank you for using PyFreeDuckDuckGo. Made by Victor Fu. Repo: https://github.com/victorfu/PyFreeDuckDuckGo"
    }


@app.post("/v1/chat/completions")
async def chat_completion_endpoint(request: OpenAIRequest):
    return await chat_completions(request)


@app.get("/v1/models")
async def list_models():
    return {
        "object": "list",
        "data": [
            {
                "id": "gpt-4o-mini",
                "object": "model",
                "created": 1692901427,
                "owned_by": "system",
            }
        ],
    }


# To run the app, use `uvicorn main:app --reload`
