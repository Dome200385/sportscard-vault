# SportsCard Vault V0.12

- OpenAI vision call moved off the FastAPI/Uvicorn event loop via `asyncio.to_thread`.
- This prevents long vision requests from blocking Render health checks and dropping the browser connection.
- First-pass model changed to `gpt-5.6-terra` for lower latency/cost while keeping image input and original-detail support.
- Browser scan request now has a 120-second timeout and reports HTTP status/body instead of only `Failed to fetch` when the server responds with an error.
- Version bumped to V0.12.
