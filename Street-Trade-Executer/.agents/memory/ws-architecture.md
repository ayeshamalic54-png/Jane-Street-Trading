---
name: WebSocket Architecture
description: How the real-time WS server is set up in the API server
---
**Rule:** index.ts creates http.createServer(app), then calls initWsServer(server). NOT app.listen().
**Why:** ws package requires an http.Server instance. Path is /api/ws.
**Broadcast:** 1s interval. Snapshot sent immediately on new connection.
