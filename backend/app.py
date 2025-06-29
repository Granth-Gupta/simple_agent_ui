import asyncio
import os
import logging
import json
from typing import Optional, Dict, List, Any
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from flask_cors import CORS
import threading
import warnings
import sys

# Suppress asyncio resource warnings on Windows
if sys.platform == "win32":
    warnings.filterwarnings("ignore", category=ResourceWarning, message="unclosed transport")

from langchain_core.messages import AIMessage, ToolMessage, HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_mcp_adapters.tools import load_mcp_tools
from langgraph.prebuilt import create_react_agent
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('agent.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

load_dotenv()

class AgentError(Exception):
    """Custom exception for agent-related errors"""
    pass

class ToolError(Exception):
    """Custom exception for tool-related errors"""
    pass

class ConfigurationError(Exception):
    """Custom exception for configuration errors"""
    pass


class FirecrawlAgent:
    def __init__(self):
        self.model = None
        self.session = None
        self.stdio_context = None
        self.agent = None
        self.tools = None
        self._shutdown_event = asyncio.Event()
        self._initialized = False
        self._loop = None
        
    async def initialize(self):
        """Initialize the agent with proper error handling"""
        try:
            # Validate environment variables
            if not os.getenv("FIRECRAWL_API_KEY"):
                raise ConfigurationError("FIRECRAWL_API_KEY environment variable is required")
            
            # Initialize model with error handling
            try:
                self.model = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0.1)
                logger.info("Model initialized successfully")
            except Exception as e:
                raise ConfigurationError(f"Failed to initialize Google Generative AI model: {e}")
            
            # Setup server parameters
            server_params = StdioServerParameters(
                command="npx",
                env={
                    "FIRECRAWL_API_KEY": os.getenv("FIRECRAWL_API_KEY"),
                },
                args=["firecrawl-mcp"],
            )
            
            # Initialize MCP client using proper async context manager
            try:
                self.stdio_context = stdio_client(server_params)
                read, write = await self.stdio_context.__aenter__()
                logger.info("MCP client initialized successfully")
            except Exception as e:
                raise AgentError(f"Failed to initialize MCP client: {e}")
            
            # Initialize session
            try:
                self.session = ClientSession(read, write)
                await self.session.__aenter__()
                await self.session.initialize()
                logger.info("MCP session initialized successfully")
            except Exception as e:
                raise AgentError(f"Failed to initialize MCP session: {e}")
            
            # Load tools
            try:
                self.tools = await load_mcp_tools(self.session)
                logger.info(f"Loaded {len(self.tools)} tools successfully")
            except Exception as e:
                raise ToolError(f"Failed to load MCP tools: {e}")
            
            # Create agent
            try:
                self.agent = create_react_agent(self.model, self.tools)
                logger.info("Agent created successfully")
            except Exception as e:
                raise AgentError(f"Failed to create agent: {e}")
            
            self._initialized = True
                
        except Exception as e:
            await self.cleanup()
            raise
    
    async def cleanup(self):
        """Properly cleanup resources"""
        if not self._initialized:
            return
            
        logger.info("Starting cleanup process...")
        
        # Clean up session first
        if self.session:
            try:
                await self.session.__aexit__(None, None, None)
                logger.info("Session closed")
            except Exception as e:
                logger.warning(f"Error closing session: {e}")
            finally:
                self.session = None
        
        # Clean up stdio context
        if self.stdio_context:
            try:
                await self.stdio_context.__aexit__(None, None, None)
                logger.info("MCP client connections closed")
            except Exception as e:
                logger.warning(f"Error closing MCP client: {e}")
            finally:
                self.stdio_context = None
        
        # Small delay to allow subprocess cleanup
        try:
            await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            pass
        
        self._initialized = False
    
    def format_history_for_agent(self, history: List[Dict]) -> List[Any]:
        """Convert frontend history format to LangChain message format"""
        messages = [
            {
                "role": "system",
                "content": """You are a helpful AI assistant with web scraping and data extraction capabilities. Your responses should be well-formatted for a chat interface.

**IMPORTANT FORMATTING RULES:**
- Keep responses concise and scannable
- Use bullet points (•) for lists instead of long paragraphs
- Break information into digestible chunks
- Use line breaks between different topics
- Start with a brief summary, then provide details
- Use **bold** for important points or headings
- Keep sentences shorter and more conversational

**Your Capabilities:**
You have access to Firecrawl tools for:
• 🔍 Web search and research
• 🌐 Website scraping and content extraction  
• 📊 Structured data extraction
• 🗺️ Website mapping and analysis
• 🕷️ Multi-page crawling
• 📝 Content summarization

**Response Format Guidelines:**
✅ DO:
- Start with a direct answer or summary
- Use bullet points for multiple items
- Break long content into short paragraphs
- Use emojis sparingly for visual breaks
- End with next steps or offers to help more

❌ DON'T:
- Write wall-of-text paragraphs
- Use overly technical language
- Include unnecessary details in the main response
- Repeat the same information multiple times

**Example Good Response:**
"I found several great open-source AI models for you:

**Top Recommendations:**
• **Hugging Face** - Popular ML community platform with thousands of models
• **Ollama** - Run LLMs locally on your computer
• **GPT4All** - Free ChatGPT alternative for offline use

**Best for Beginners:**
• Start with Hugging Face for easy access
• Try GPT4All if you want offline capabilities

Would you like me to get more details about any of these options?"

Remember: Chat users prefer scannable, actionable responses over dense academic paragraphs.""",
            }
        ]
        
        for msg in history:
            if msg.get("type") == "user":
                messages.append({"role": "user", "content": msg.get("content", "")})
            elif msg.get("type") == "bot":
                messages.append({"role": "assistant", "content": msg.get("content", "")})
        
        return messages
    
    async def process_message_async(self, user_input: str, history: List[Dict] = None) -> Dict[str, Any]:
        """Process a user message and return structured response"""
        if not self._initialized or not self.agent:
            raise AgentError("Agent is not properly initialized")
        
        # Prepare message history
        if history is None:
            history = []
        
        messages = self.format_history_for_agent(history)
        
        # Truncate input if too long
        truncated_input = user_input[:175000]
        if len(user_input) > 175000:
            logger.warning(f"Input truncated from {len(user_input)} to 175000 characters")
        
        messages.append({"role": "user", "content": truncated_input})
        
        try:
            # Invoke agent with timeout
            agent_response = await asyncio.wait_for(
                self.agent.ainvoke({"messages": messages}),
                timeout=120.0
            )
            
            # Process response
            ai_message_content = ""
            tool_calls = []
            tool_outputs = []
            
            for msg in agent_response["messages"]:
                if isinstance(msg, AIMessage) and msg.tool_calls:
                    for tool_call in msg.tool_calls:
                        tool_calls.append({
                            "name": tool_call.get('name', 'Unknown'),
                            "args": tool_call.get('args', {}),
                            "id": tool_call.get('id', '')
                        })
                        logger.info(f"Tool used: {tool_call.get('name', 'Unknown')}")
                elif isinstance(msg, ToolMessage):
                    tool_outputs.append({
                        "name": msg.name,
                        "content": str(msg.content)[:1000] + ("..." if len(str(msg.content)) > 1000 else ""),
                        "full_content": str(msg.content)
                    })
                    logger.info(f"Tool output from {msg.name}: {len(str(msg.content))} characters")
                elif isinstance(msg, AIMessage) and msg.content:
                    ai_message_content = msg.content
            
            return {
                "success": True,
                "ai_message": ai_message_content or "✅ Task completed successfully! Let me know if you need any clarification or have additional questions.",
                "tool_calls": tool_calls,
                "tool_outputs": tool_outputs
            }
                
        except asyncio.TimeoutError:
            logger.error("Agent invocation timed out")
            return {
                "success": False,
                "error": "Request timed out. Please try a simpler query or check your connection.",
                "ai_message": "⏱️ **Request Timeout**\n\nYour request is taking longer than expected. This might be due to:\n• Complex query processing\n• Network connectivity issues\n\n**Try this:**\n• Break your question into smaller parts\n• Rephrase with simpler terms\n• Check your internet connection"
            }
        except Exception as e:
            logger.error(f"Error during agent invocation: {e}")
            return {
                "success": False,
                "error": str(e),
                "ai_message": f"⚠️ **Processing Error**\n\nI encountered an issue: {str(e)}\n\n**Next steps:**\n• Try rephrasing your question\n• Make sure your request is clear\n• Contact support if this persists"
            }
    
    def get_available_tools(self) -> List[str]:
        """Get list of available tool names"""
        if not self.tools:
            return []
        return [tool.name for tool in self.tools]


# Global agent instance
agent = FirecrawlAgent()

# Flask app setup
app = Flask(__name__)
CORS(app)  # Enable CORS for all routes


def run_async_in_thread(coro):
    """Run async function in the event loop"""
    if agent._loop is None:
        return None
    
    future = asyncio.run_coroutine_threadsafe(coro, agent._loop)
    return future.result(timeout=130.0)  # Give a bit more time than agent timeout


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy" if agent._initialized else "initializing",
        "tools_available": len(agent.tools) if agent.tools else 0
    })


@app.route('/tools', methods=['GET'])
def get_tools():
    """Get available tools"""
    return jsonify({
        "tools": agent.get_available_tools()
    })


@app.route('/chat', methods=['POST'])
def chat():
    """Main chat endpoint"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        user_message = data.get('message', '')
        history = data.get('history', [])
        
        if not user_message.strip():
            return jsonify({"error": "Empty message"}), 400
        
        # Check if agent is initialized
        if not agent._initialized:
            return jsonify({
                "error": "Agent is not initialized",
                "ai_message": "🚀 **Starting Up**\n\nI'm still getting my tools ready! Give me a moment and try again.\n\n• Loading web scraping capabilities\n• Connecting to Firecrawl services\n• Preparing AI models"
            }), 503
        
        # Process message
        try:
            result = run_async_in_thread(
                agent.process_message_async(user_message, history)
            )
            
            if result is None:
                return jsonify({
                    "error": "Failed to process message",
                    "ai_message": "🔧 **Technical Difficulties**\n\nI'm having some issues right now. Please try again in a moment!\n\n• System is recovering\n• Tools are reconnecting\n• Should be back shortly"
                }), 500
            
            return jsonify(result)
            
        except Exception as e:
            logger.error(f"Error processing chat message: {e}")
            return jsonify({
                "error": str(e),
                "ai_message": f"⚠️ **Technical Issue**\n\nSomething went wrong: {str(e)}\n\n**Try this:**\n• Rephrase your question\n• Try a simpler request\n• Wait a moment and try again"
            }), 500
    
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}")
        return jsonify({
            "error": "Internal server error",
            "ai_message": "🛠️ **System Error**\n\nI'm experiencing technical difficulties right now.\n\n• Please try again in a moment\n• The issue should resolve automatically\n• Contact support if this persists"
        }), 500


async def initialize_agent():
    """Initialize the agent in the background"""
    try:
        await agent.initialize()
        logger.info("Agent initialized successfully for web server")
    except Exception as e:
        logger.error(f"Failed to initialize agent: {e}")
        raise


def run_event_loop():
    """Run the asyncio event loop in a separate thread"""
    agent._loop = asyncio.new_event_loop()
    asyncio.set_event_loop(agent._loop)
    
    try:
        agent._loop.run_until_complete(initialize_agent())
        agent._loop.run_forever()
    except Exception as e:
        logger.error(f"Error in event loop: {e}")
    finally:
        agent._loop.close()


if __name__ == "__main__":
    # Start the event loop in a separate thread
    event_loop_thread = threading.Thread(target=run_event_loop, daemon=True)
    event_loop_thread.start()
    
    # Wait a bit for initialization
    import time
    time.sleep(2)
    
    # Start Flask app
    try:
        print("🚀 Starting Flask server on http://localhost:5000")
        print("📡 Available endpoints:")
        print("  GET  /health - Health check")
        print("  GET  /tools  - Get available tools")
        print("  POST /chat   - Chat with the agent")
        print("-" * 50)
        print("🤖 AI Agent is ready to help!")
        
        app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
    except KeyboardInterrupt:
        logger.info("Shutting down Flask server...")
        # Signal the event loop to stop
        if agent._loop:
            agent._loop.call_soon_threadsafe(agent._loop.stop)
    except Exception as e:
        logger.error(f"Error starting Flask server: {e}")
    finally:
        # Cleanup
        if agent._loop:
            try:
                asyncio.run_coroutine_threadsafe(agent.cleanup(), agent._loop).result(timeout=5.0)
            except Exception as e:
                logger.warning(f"Error during cleanup: {e}")