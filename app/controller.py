
import asyncio
from typing import Callable, Optional, List, Dict, Any
from browser_use import Controller


class AgentController:
    def __init__(self):
        # State
        self.paused = False
        self.running = False
        self.stop_requested = False
        
        # Human interaction
        self.human_response: Optional[str] = None
        self.human_response_event = asyncio.Event()
        self.resume_event = asyncio.Event()
        self.resume_event.set()
        
        # Data
        self.findings: List[Dict[str, Any]] = []
        self.log_callback: Optional[Callable] = None
        
        # Browser-use controller
        self.browser_controller = Controller()
        self._setup_actions()
    
    def set_log_callback(self, cb: Callable):
        self.log_callback = cb
    
    async def log(self, message: str, level: str = "info"):
        if self.log_callback:
            await self.log_callback(message, level)
    
    async def check_pause(self):
        """Check for pause/stop - call periodically"""
        if self.stop_requested:
            raise StopIteration("Stopped by user")
        
        if self.paused:
            self.resume_event.clear()
            await self.log("⏸️ Waiting to resume...", "warn")
            await self.resume_event.wait()
    
    async def ask_human(self, question: str) -> str:
        """Pause and request human input"""
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
        """Record a finding"""
        finding = {
            "title": title,
            "price": price,
            "url": url,
            "notes": notes,
            "image_url": image_url
        }
        self.findings.append(finding)
        return finding
    
    def _setup_actions(self):
        """Register custom browser-use actions"""
        
        @self.browser_controller.action(
            "Ask human for guidance",
            param_model=None
        )
        async def ask_human_action(question: str) -> str:
            """
            Ask the human for help when:
            - Unsure about item value or authenticity
            - Need to choose between multiple options
            - Stuck or confused
            - Need clarification on the task
            """
            return await self.ask_human(question)
        
        @self.browser_controller.action(
            "Report interesting item",
            param_model=None
        )
        async def report_item(
            title: str,
            price: str, 
            url: str,
            notes: str,
            image_url: str = ""
        ) -> str:
            """
            Report an item worth noting. Include:
            - title: Item name/description
            - price: Current price or bid
            - url: Link to listing
            - notes: Why this is interesting (deal, rare, misspelled, etc)
            - image_url: Optional thumbnail URL
            """
            finding = self.add_finding(title, price, url, notes, image_url)
            await self.log(f"📦 {title} - {price}", "finding")
            return "Finding recorded. Continue searching."
        
        @self.browser_controller.action(
            "Check if should continue",
            param_model=None
        )
        async def check_continue() -> str:
            """
            Periodic check - call this every few actions.
            Handles pause/resume and stop requests.
            """
            try:
                await self.check_pause()
                return "Continue"
            except StopIteration:
                return "STOP - User requested stop"
