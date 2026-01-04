
import os
import asyncio
from typing import List, Dict, Any
from cerebras.cloud.sdk import Cerebras
from browser_use import Agent, Browser, BrowserConfig
from browser_use.browser.context import BrowserContextConfig

from controller import AgentController


class CerebrasGPTOSS:
    """
    Cerebras GPT OSS 120B wrapper
    Optimized for agentic tasks - better instruction following
    """
    
    def __init__(self):
        api_key = os.environ.get("CEREBRAS_API_KEY")
        if not api_key:
            raise ValueError("CEREBRAS_API_KEY not set")
        
        self.client = Cerebras(api_key=api_key)
        self.model = "gpt-oss-120b"  # Optimized for agents
        
        # Track usage
        self.total_tokens = 0
    
    async def __call__(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """Generate completion"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=kwargs.get("max_tokens", 4096),
                temperature=kwargs.get("temperature", 0.6),
                top_p=0.95,
            )
            
            self.total_tokens += response.usage.total_tokens
            return response.choices[0].message.content
            
        except Exception as e:
            print(f"Cerebras API error: {e}")
            raise
    
    async def generate(self, prompt: str, **kwargs) -> str:
        """Simple generate interface"""
        return await self([{"role": "user", "content": prompt}], **kwargs)
    
    def get_usage(self) -> int:
        return self.total_tokens


class EbayResearchAgent:
    """Main research agent"""
    
    SYSTEM_PROMPT = """You are an expert eBay researcher and deal finder. 

YOUR CAPABILITIES:
- Navigate eBay efficiently
- Find rare and hard-to-find items
- Identify underpriced listings
- Discover misspelled listings (major source of deals!)
- Analyze sold prices vs current listings
- Evaluate seller reliability

SEARCH STRATEGIES:
1. **Misspellings** - Try common typos:
   - Missing letters: "walkman" → "wlkman", "walman" 
   - Swapped letters: "vintage" → "vintgae"
   - Phonetic: "chrome" → "crome"
   
2. **Keyword variations**:
   - Brand misspellings
   - Model number variations
   - Abbreviated names
   
3. **Advanced filters**:
   - Check "Sold Items" for price history
   - Compare "Buy It Now" vs auctions
   - Look at ending soon auctions
   
4. **Hidden gems**:
   - Search "lot" or "bundle" for mixed items
   - Check "Parts/Not Working" for repairable items
   - International listings (less competition)

WHEN TO ASK HUMAN FOR HELP:
- Found something but unsure of value/authenticity
- Multiple promising leads, need prioritization
- Stuck on captcha or unusual situation
- Need clarification on what exactly to find

ALWAYS:
- Use 'Report interesting item' for any notable finds
- Call 'Check if should continue' periodically
- Be thorough - try multiple search angles
- Note WHY something is a good find"""

    def __init__(self, controller: AgentController):
        self.controller = controller
        self.llm = CerebrasGPTOSS()
    
    async def run(self, task: str) -> str:
        """Execute research task"""
        
        browser = Browser(
            config=BrowserConfig(
                headless=False,
                disable_security=True,
                extra_chromium_args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-infobars",
                    "--window-size=1366,768",
                    "--window-position=0,0"
                ]
            )
        )
        
        context_config = BrowserContextConfig(
            wait_for_network_idle_page_load_time=3.0,
            browser_window_size={"width": 1366, "height": 768},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/121.0.0.0 Safari/537.36"
            )
        )
        
        full_task = f"""RESEARCH TASK:
{task}

INSTRUCTIONS:
- Search eBay thoroughly using multiple strategies
- Try misspellings and keyword variations  
- Check both active listings and sold items
- Report ALL interesting finds
- Ask for human guidance when unsure
- Be persistent - good deals are often hidden"""

        agent = Agent(
            task=full_task,
            llm=self.llm,
            browser=browser,
            controller=self.controller.browser_controller,
            system_prompt_class=lambda: self.SYSTEM_PROMPT,
            max_actions_per_step=5,
        )
        
        try:
            result = await agent.run(max_steps=100)
            
            # Log token usage
            await self.controller.log(
                f"📊 Tokens used: {self.llm.get_usage():,}",
                "info"
            )
            
            return result
            
        except StopIteration:
            return "Research stopped by user"
            
        except Exception as e:
            await self.controller.log(f"Agent error: {e}", "error")
            raise
            
        finally:
            await browser.close()
