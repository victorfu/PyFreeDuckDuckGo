# PyFreeDuckDuckGo

This is a Python implementation of [FreeDuckDuckGo](https://github.com/missuo/FreeDuckDuckGo/tree/main).

### Docker Compose

#### PyFreeDuckDuckGo Service

```bash
mkdir PyFreeDuckDuckGo && cd PyFreeDuckDuckGo
curl -o compose.yaml https://raw.githubusercontent.com/victorfu/PyFreeDuckDuckGo/master/compose.yaml
docker compose up -d
```

### Test PyFreeDuckDuckGo

```bash
curl http://127.0.0.1:3456/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o-mini",
    "messages": [
      {
        "role": "user",
        "content": "Hello!"
      }
    ],
    "stream": true
    }'
```
