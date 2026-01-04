"""
Agent controller - pause/resume, human-in-the-loop, findings
"""

import asyncio
from typing import Callable, Optional, List, Dict, Any


class AgentController:
    def __init__(self):
        self.paused = False
        self.running = False
        self.stop_requested = False
        
        self.human_response: Optional[str] = None
        self.human_response_event = asyncio.Event()
        self.resume_event = asyncio.Event()
        self.resume_event.set()
        
        self.findings: List[Dict[str, Any]] = []
        self.log_callback: Optional[Callable] = None
    
    def set_log_callback(self, cb: Callable):
        self.log_callback = cb
    
    async def log(self, message: str, level: str = "info"):
        if self.log_callback:
            await self.log_callback(message, level)
    
    async def check_pause(self):
        if self.stop_requested:
            raise StopIteration("Stopped by user")
        
        if self.paused:
            self.resume_event.clear()
            await self.log("⏸️ Waiting to resume...", "warn")
            await self.resume_event.wait()
    
    async def ask_human(self, question: str) -> str:
        await self.log(f"🤖 NEED HELP: {question}", "question")
        
        self.human_response = None
        self.human_response_event.clear()
        
        try:
            await asyncio.wait_for(
                self.human_response_event.wait(),
                timeout=300
            )
        except asyncio.TimeoutError:
            return "No response - continue with best judgment"
        
        response = self.human_response or "Continue"
        self.human_response = None
        return response
    
    def add_finding(
        self,
        title: str,
        price: str,
        url: str,
        notes: str,
        image_url: str = ""
    ) -> Dict[str, Any]:
        finding = {
            "title": title,
            "price": price,
            "url": url,
            "notes": notes,
            "image_url": image_url
        }
        self.findings.append(finding)
        return finding
