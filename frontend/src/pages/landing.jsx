import React, { useState, useRef, useEffect } from "react";
import {
  Send,
  Bot,
  User,
  Loader,
  Search,
  Globe,
  FileText,
  Database,
  Brain,
  Zap,
} from "lucide-react";
// Import Card components from shadcn/ui
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { cn } from "@/lib/utils";

function LandingPage({ onNavigate }) {
  const [messages, setMessages] = useState([
    {
      id: 1,
      type: "bot",
      content:
        "Hello! I'm your AI agent powered by Gemini LLM and Firecrawl tools. I can help you search the web, scrape content, extract data, and provide intelligent responses. What would you like to know?",
      timestamp: new Date().toLocaleTimeString(),
    },
  ]);
  const [inputValue, setInputValue] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [availableTools] = useState([
    "firecrawl_scrape",
    "firecrawl_map",
    "firecrawl_crawl",
    "firecrawl_check_crawl_status",
    "firecrawl_search",
    "firecrawl_extract",
    "firecrawl_deep_research",
    "firecrawl_generate_llmstxt",
  ]);

  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  // Scrolls to the bottom of the messages container
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  // Effect to scroll to bottom whenever messages update
  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Handles the submission of a user message and communicates with the backend
  const handleSubmit = async () => {
    if (!inputValue.trim() || isLoading) return;

    const userMessage = {
      id: Date.now(),
      type: "user",
      content: inputValue,
      timestamp: new Date().toLocaleTimeString(),
    };

    setMessages((prev) => [...prev, userMessage]); // Add user message immediately
    setInputValue("");
    setIsLoading(true);

    try {
      // Prepare chat history to send to backend (optional, but good for context)
      // Filter out only content and type for sending to backend, as IDs/timestamps
      // are frontend specific. You might need to adjust based on how your Python
      // agent expects history.
      const historyToSend = messages.map((msg) => ({
        type: msg.type,
        content: msg.content,
      }));

      const response = await fetch("http://localhost:5000/chat", {
        // Flask server runs on port 5000
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          message: userMessage.content,
          history: historyToSend, // Sending history for context if agent uses it
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();

      let botMessageContent = data.ai_message || "(No direct textual response)";
      let toolsUsedByBot = [];

      // Process tool_calls and tool_outputs if present
      if (data.tool_calls && data.tool_calls.length > 0) {
        // Here, we're just collecting the tool names that were called
        // You might want to display more detailed tool call info to the user
        toolsUsedByBot = data.tool_calls.map((tc) => tc.name);
        // Optionally, you could prepend tool call info to the bot message
        // For now, we'll just show them in the 'toolsUsed' section.
      }
      if (data.tool_outputs && data.tool_outputs.length > 0) {
        // You might want to display tool outputs as separate messages or append to bot message
        // For simplicity, we're not adding them as separate messages in this example
        // but you could iterate and add them if needed.
      }

      const botResponse = {
        id: Date.now() + 1,
        type: "bot",
        content: botMessageContent,
        timestamp: new Date().toLocaleTimeString(),
        toolsUsed: toolsUsedByBot,
      };

      setMessages((prev) => [...prev, botResponse]);
    } catch (error) {
      console.error("Error sending message to backend:", error);
      setMessages((prev) => [
        ...prev,
        {
          id: Date.now() + 1,
          type: "bot",
          content: `Sorry, there was an error processing your request: ${error.message}`,
          timestamp: new Date().toLocaleTimeString(),
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  // No longer needed as we get real responses from the agent
  // const generateMockResponse = (query) => { /* ... */ };
  // const getRandomTools = () => { /* ... */ };

  // Returns the appropriate Lucide icon for a given tool
  const getToolIcon = (tool) => {
    if (tool.includes("search")) return <Search className="w-3 h-3" />;
    if (tool.includes("scrape")) return <Globe className="w-3 h-3" />;
    if (tool.includes("extract")) return <FileText className="w-3 h-3" />;
    if (tool.includes("crawl")) return <Database className="w-3 h-3" />;
    return <Zap className="w-3 h-3" />;
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 flex items-center justify-center p-4 font-sans">
      {/* Main Chat Container Card */}
      <Card className="w-full max-w-3xl h-[90vh] flex flex-col rounded-xl overflow-hidden bg-black/40 backdrop-blur-xl border border-purple-500/20 shadow-lg shadow-purple-900/50">
        {/* Header - Now part of the main Card */}
        <CardHeader className="bg-black/30 border-b border-purple-500/20 p-4 flex flex-row items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-gradient-to-r from-purple-500 to-pink-500 rounded-full flex items-center justify-center">
              <Brain className="w-6 h-6 text-white" />
            </div>
            <div>
              <CardTitle className="text-xl font-bold text-white m-0">
                AI Agent
              </CardTitle>
              <CardDescription className="text-sm text-purple-300 m-0">
                Powered by Gemini LLM & Firecrawl
              </CardDescription>
            </div>
          </div>
          <div className="px-3 py-1 bg-green-500/20 text-green-400 rounded-full text-sm font-medium">
            Online
          </div>
        </CardHeader>

        {/* Available Tools - Also inside the main Card, but visually separate */}
        <div className="bg-black/20 backdrop-blur-lg border-b border-purple-500/10 p-3">
          <p className="text-sm text-purple-300 mb-2">Available Tools:</p>
          <div className="flex flex-wrap gap-2">
            {availableTools.map((tool, index) => (
              <span
                key={index}
                className="px-2 py-1 bg-purple-500/20 text-purple-200 rounded text-xs font-mono flex items-center gap-1"
              >
                {getToolIcon(tool)}
                {tool}
              </span>
            ))}
          </div>
        </div>

        {/* Messages */}
        <CardContent className="flex-1 overflow-y-auto p-4 space-y-6">
          {messages.map((message) => (
            <div
              key={message.id}
              className={`flex gap-4 ${
                message.type === "user" ? "justify-end" : "justify-start"
              }`}
            >
              <div
                className={`flex gap-3 max-w-[80%] ${
                  message.type === "user" ? "flex-row-reverse" : "flex-row"
                }`}
              >
                {/* Avatar */}
                <div
                  className={cn(
                    "w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0",
                    message.type === "user"
                      ? "bg-gradient-to-r from-blue-500 to-cyan-500"
                      : "bg-gradient-to-r from-purple-500 to-pink-500"
                  )}
                >
                  {message.type === "user" ? (
                    <User className="w-5 h-5 text-white" />
                  ) : (
                    <Bot className="w-5 h-5 text-white" />
                  )}
                </div>

                {/* Message Card */}
                <Card
                  className={cn(
                    "rounded-2xl",
                    message.type === "user"
                      ? "bg-gradient-to-r from-blue-500 to-cyan-500 text-white border-none shadow-md"
                      : "bg-background text-card-foreground border border-purple-500/20 shadow-md"
                  )}
                >
                  <CardContent className="p-4">
                    <p className="text-sm leading-relaxed m-0">
                      {message.content}
                    </p>

                    {message.toolsUsed && message.toolsUsed.length > 0 && (
                      <div className="mt-3 pt-3 border-t border-purple-500/20">
                        <p className="text-xs text-purple-300 mb-2">
                          Tools Used:
                        </p>
                        <div className="flex flex-wrap gap-1">
                          {message.toolsUsed.map((tool, index) => (
                            <span
                              key={index}
                              className="px-1.5 py-0.5 bg-purple-500/30 text-purple-200 rounded text-xs font-mono flex items-center gap-1"
                            >
                              {getToolIcon(tool)}
                              {tool}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}

                    <div className="mt-2 text-xs opacity-70">
                      {message.timestamp}
                    </div>
                  </CardContent>
                </Card>
              </div>
            </div>
          ))}

          {isLoading && (
            <div className="flex justify-start">
              <div className="flex gap-3 max-w-[80%]">
                <div className="w-8 h-8 rounded-full bg-gradient-to-r from-purple-500 to-pink-500 flex items-center justify-center">
                  <Bot className="w-5 h-5 text-white" />
                </div>
                <Card className="bg-background text-card-foreground border border-purple-500/20 shadow-md">
                  <CardContent className="p-4">
                    <div className="flex items-center gap-2 text-purple-300">
                      <Loader className="w-4 h-4 animate-spin" />
                      <span className="text-sm">AI is thinking...</span>
                    </div>
                  </CardContent>
                </Card>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </CardContent>

        {/* Input */}
        <div className="bg-black/30 backdrop-blur-xl border-t border-purple-500/20 p-4">
          <div className="flex gap-3">
            <input
              ref={inputRef}
              type="text"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyPress={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleSubmit();
                }
              }}
              placeholder="Ask me anything... I can search, scrape, extract data, and more!"
              className="flex-1 px-4 py-3 bg-black/40 backdrop-blur-lg border border-purple-500/30 rounded-2xl text-white text-sm outline-none placeholder:text-purple-300 focus:border-purple-500 focus:shadow-lg focus:shadow-purple-500/20 disabled:opacity-50 transition-all duration-200"
              disabled={isLoading}
            />
            <button
              onClick={handleSubmit}
              disabled={!inputValue.trim() || isLoading}
              className={`px-6 py-3 rounded-2xl flex items-center gap-2 font-medium text-white transition-all duration-200 ${
                isLoading || !inputValue.trim()
                  ? "bg-gray-500/50 cursor-not-allowed"
                  : "bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600 cursor-pointer shadow-lg hover:shadow-purple-500/25"
              }`}
            >
              {isLoading ? (
                <Loader className="w-5 h-5 animate-spin" />
              ) : (
                <Send className="w-5 h-5" />
              )}
              {isLoading ? "Processing..." : "Send"}
            </button>
          </div>

          <div className="mt-2 text-xs text-purple-400 text-center">
            Powered by Gemini LLM • Firecrawl Tools • Real-time Web Intelligence
          </div>
        </div>
      </Card>
    </div>
  );
}

export default LandingPage;
