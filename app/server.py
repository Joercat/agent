import asyncio
import json
import os
from pathlib import Path
from aiohttp import web, WSMsgType
import aiofiles

from agent import EbayResearchAgent
from controller import AgentController

controller = AgentController()
connections: set[web.WebSocketResponse] = set()


async def broadcast(msg_type: str, data: dict):
    """Broadcast to all WebSocket clients"""
    msg = json.dumps({"type": msg_type, **data})
    dead = set()
    for ws in connections:
        try:
            await ws.send_str(msg)
        except:
            dead.add(ws)
    connections.difference_update(dead)


async def ws_handler(request):
    """WebSocket endpoint"""
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    connections.add(ws)
    
    async def log_cb(msg: str, level: str = "info"):
        await broadcast("log", {"message": msg, "level": level})
    
    controller.set_log_callback(log_cb)
    
    await ws.send_str(json.dumps({
        "type": "state",
        "paused": controller.paused,
        "running": controller.running,
        "findings": controller.findings
    }))
    
    try:
        async for msg in ws:
            if msg.type == WSMsgType.TEXT:
                await handle_ws_message(json.loads(msg.data))
    finally:
        connections.discard(ws)
    
    return ws


async def handle_ws_message(data: dict):
    """Process incoming WebSocket commands"""
    action = data.get("action")
    
    if action == "start" and not controller.running:
        task = data.get("task", "")
        if task:
            asyncio.create_task(run_research(task))
            await broadcast("state", {"running": True, "paused": False})
    
    elif action == "pause":
        controller.paused = True
        await broadcast("state", {"paused": True})
        await broadcast("log", {"message": "⏸️ Paused", "level": "warn"})
    
    elif action == "resume":
        controller.paused = False
        controller.resume_event.set()
        await broadcast("state", {"paused": False})
        await broadcast("log", {"message": "▶️ Resumed", "level": "info"})
    
    elif action == "stop":
        controller.stop_requested = True
        controller.resume_event.set()
        await broadcast("log", {"message": "🛑 Stopping...", "level": "warn"})
    
    elif action == "human_input":
        msg = data.get("message", "")
        if msg:
            controller.human_response = msg
            controller.human_response_event.set()
            await broadcast("log", {"message": f"👤 You: {msg}", "level": "human"})


async def run_research(task: str):
    """Execute research agent"""
    controller.running = True
    controller.stop_requested = False
    controller.findings = []
    
    try:
        agent = EbayResearchAgent(controller)
        await broadcast("log", {"message": f"🚀 Starting: {task}", "level": "info"})
        
        result = await agent.run(task)
        
        await broadcast("log", {"message": "✅ Research complete!", "level": "success"})
        await broadcast("result", {"summary": result, "findings": controller.findings})
        
    except Exception as e:
        await broadcast("log", {"message": f"❌ Error: {e}", "level": "error"})
    finally:
        controller.running = False
        await broadcast("state", {"running": False})


async def serve_index(request):
    """Serve main page"""
    path = Path(__file__).parent / "web/index.html"
    async with aiofiles.open(path) as f:
        return web.Response(text=await f.read(), content_type="text/html")


async def serve_static(request):
    """Serve static assets"""
    filename = request.match_info.get("filename", "")
    path = Path(__file__).parent / "web" / filename
    
    if not path.exists():
        return web.Response(status=404)
    
    ctypes = {".css": "text/css", ".js": "application/javascript"}
    ct = ctypes.get(path.suffix, "text/plain")
    
    async with aiofiles.open(path) as f:
        return web.Response(text=await f.read(), content_type=ct)


def create_app():
    app = web.Application()
    app.router.add_get("/", serve_index)
    app.router.add_get("/ws", ws_handler)
    app.router.add_get("/static/{filename}", serve_static)
    app.router.add_static("/vnc/", "/usr/share/novnc/")
    return app


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    print(f"🌐 Server starting on port {port}")
    web.run_app(create_app(), host="0.0.0.0", port=port)
