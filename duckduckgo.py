import json
import re
import httpx
from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
import hashlib
import base64
from bs4 import BeautifulSoup


def sha256_base64(text: str) -> str:
    sha256_hash = hashlib.sha256(text.encode("utf-8")).digest()
    return base64.b64encode(sha256_hash).decode()


def calculate_dom_fingerprint(
    html_snippet: str,
    numeric_offset: int,
):
    soup = BeautifulSoup(html_snippet, "html5lib")
    corrected_inner_html = soup.body.decode_contents()
    inner_html_length = len(corrected_inner_html)
    fingerprint = numeric_offset + inner_html_length
    return fingerprint, corrected_inner_html, inner_html_length


def parse_client_hashes(js_text):
    html_match = re.search(r"e\.innerHTML\s*=\s*'(.*?)';", js_text)
    offset_match = re.search(
        r"return String\((\d+)\s*\+\s*e\.innerHTML\.length\);", js_text
    )
    if not html_match or not offset_match:
        raise ValueError("Unable to parse JS snippet correctly.")

    html_snippet = html_match.group(1)
    offset_value = int(offset_match.group(1))

    dom_fingerprint, corrected_inner_html, inner_html_length = (
        calculate_dom_fingerprint(html_snippet, offset_value)
    )

    return {
        "html_snippet": html_snippet,
        "offset": offset_value,
        "dom_fingerprint": str(dom_fingerprint),
    }


def parse_server_hashes(js_text):
    matches = re.findall(r"server_hashes:\s*\[([^\]]+)\]", js_text)
    if matches:
        server_hashes = re.findall(r'"([^"]+)"', matches[0])
    else:
        raise ValueError("No server_hashes found.")
    return server_hashes


class Message(BaseModel):
    role: str
    content: str


class OpenAIRequest(BaseModel):
    model: str
    messages: List[Message]
    stream: Optional[bool] = False


async def chat_completions(request: OpenAIRequest):
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
        "Accept": "text/event-stream",
        "Accept-Language": "de,en-US;q=0.7,en;q=0.3",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://duckduckgo.com/",
        "Content-Type": "application/json",
        "Origin": "https://duckduckgo.com",
        "Connection": "keep-alive",
        "Cookie": "dcm=3; dcs=1",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "Pragma": "no-cache",
        "Sec-Ch-Ua": '"Chromium";v="134", "Not:A-Brand";v="24", "Brave";v="134"',
        "Sec-Gpc": "1",
        "X-Fe-Version": "serp_20250326_193736_ET-6743f86a045676e7f6b4",
    }

    status_url = "https://duckduckgo.com/duckchat/v1/status"
    chat_url = "https://duckduckgo.com/duckchat/v1/chat"

    async with httpx.AsyncClient() as client:
        resp = await client.get(status_url, headers={"x-vqd-accept": "1", **headers})
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        vqd4 = resp.headers.get("x-vqd-4")
        vqd_hash_1 = resp.headers.get("x-vqd-hash-1")

    decoded_vqd_hash_1 = base64.b64decode(vqd_hash_1).decode()

    server_hashes = parse_server_hashes(decoded_vqd_hash_1)
    client_hashes = parse_client_hashes(decoded_vqd_hash_1)

    ua_fingerprint = headers["User-Agent"] + headers["Sec-Ch-Ua"]
    ua_hash = sha256_base64(ua_fingerprint)
    dom_hash = sha256_base64(client_hashes["dom_fingerprint"])

    final_result = {
        "server_hashes": server_hashes,
        "client_hashes": [ua_hash, dom_hash],
        "signals": {},
    }
    base64_final_result = base64.b64encode(json.dumps(final_result).encode()).decode()

    payload = {
        "model": "gpt-4o-mini",
        "messages": [message.dict() for message in request.messages],
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            chat_url,
            json=payload,
            headers={"x-vqd-4": vqd4, "x-vqd-hash-1": base64_final_result, **headers},
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)

    if not request.stream:
        result_content = ""
        id = ""
        created = 0
        model = ""
        async for line in resp.aiter_lines():
            if line.startswith("data: "):
                chunk = line[6:]
                if chunk == "[DONE]":
                    break
                try:
                    data = json.loads(chunk)
                    id = data.get("id", "")
                    created = data.get("created", 0)
                    model = data.get("model", "")
                    result_content += data.get("message", "")
                except json.JSONDecodeError:
                    continue
        return {
            "id": id,
            "object": "chat.completion",
            "created": created,
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": result_content},
                    "finish_reason": "stop",
                }
            ],
        }

    async def event_stream():
        async for line in resp.aiter_lines():
            if line.startswith("data: "):
                chunk = line[6:]
                if chunk == "[DONE]":
                    yield f"{chunk}"
                    break
                try:
                    data = json.loads(chunk)
                    message = data.get("message", "")
                    yield f"{message}"
                    # yield f"{json.dumps(data, ensure_ascii=False)}\n\n"
                except json.JSONDecodeError:
                    continue

    return StreamingResponse(event_stream(), media_type="text/event-stream")
