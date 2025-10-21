## Web Frontend (Next.js on Vercel)

This folder will contain a minimal Next.js app that calls your proxy server (FastAPI) to chat and manage models.

For now, deploy any simple static page to Vercel that calls your server endpoints:

- GET `${SERVER_URL}/health`
- GET `${SERVER_URL}/models`
- POST `${SERVER_URL}/pull` body `{ name }` (NDJSON streaming)
- POST `${SERVER_URL}/delete` body `{ name }`
- POST `${SERVER_URL}/chat` body `{ model, messages, options }`
- POST `${SERVER_URL}/chat_stream` body `{ model, messages, options }` (NDJSON streaming tokens)
- WS `${SERVER_URL}/ws/chat` send `{ model, messages, options }`

Include header `x-api-key: YOUR_KEY` if you set an API key.


