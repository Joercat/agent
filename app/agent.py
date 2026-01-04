"""
eBay Research Agent - Cerebras GPT OSS 120B
"""

import os
import asyncio
from typing import List, Dict, Any
from cerebras.cloud.sdk import Cerebras
from browser_use import Agent, BrowserConfig, Browser

from controller import AgentController


class CerebrasGPTOSS:
    """
    Cerebras GPT OSS 120B wrapper
    """
    
    def __init__(self):
        api_key = os.environ.get("CEREBRAS_API_KEY")
        if not api_key:
            raise ValueError("CEREBRAS_API_KEY not set")
        
        self.client = Cerebras(api_key=api_key)
        self.model = "gpt-oss-120b"
        self.total_tokens = 0
    
    async def __call__(self, messages: List[Dict[str, str]], **kwargs) -> str:
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
   - Compare the found item to each items approximate cost

Important Rules to follow:
   - Always find items that are "Buy It Now" instead of auctions, even though its harder.
   - The final price of an item should be the max or lower, including after tax and shipping.
   - If you can not tell if an item is a good deal, check with human, avoid submitting any unsure finds.
   
WHEN TO ASK HUMAN FOR HELP:
- Found something but unsure of value/authenticity
- Multiple promising leads, need prioritization
- Stuck on captcha or unusual situation
- Need clarification on what exactly to find

ALWAYS:
- Use 'Report interesting item' for any notable finds
- Call 'Check if should continue' periodically when you think its been a while
- Be thorough - try multiple search angles
- Note WHY something is a good find"""

    def __init__(self, controller: AgentController):
        self.controller = controller
        self.llm = CerebrasGPTOSS()
    
    async def run(self, task: str) -> str:
        config = BrowserConfig(
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
        
        browser = Browser(config=config)
        
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
        )
        
        try:
            result = await agent.run()
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
