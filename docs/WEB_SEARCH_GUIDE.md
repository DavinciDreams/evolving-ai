# Web Search Integration Guide

Your AI agent now has **web search capabilities** powered by Tavily! This allows the agent to search the internet in real-time for current information.

## 🎯 Configuration Status

✅ **Web Search**: ENABLED
✅ **Provider**: Tavily (AI-optimized search)
✅ **API Key**: Configured
✅ **Max Results**: 5 per search

## 🚀 Getting Started

### Step 1: Install Dependencies

First, install the required Python packages:

```bash
pip install -r requirements.txt
```

Or install individually:
```bash
pip install beautifulsoup4 lxml httpx python-dotenv
```

**Note**: The `duckduckgo-search` package is optional since you're using Tavily.

### Step 2: Start the API Server

```bash
python api_server.py
```

The server will start at `http://localhost:8000`

### Step 3: Test Web Search

**Option A: Use the test script**
```bash
# In a new terminal, once the server is running:
./quick_web_search_test.sh
```

**Option B: Use curl directly**
```bash
curl -X POST "http://localhost:8000/web-search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Latest developments in AI 2025",
    "max_results": 5,
    "include_content": true
  }'
```

**Option C: Use the Swagger UI**
1. Open `http://localhost:8000/docs` in your browser
2. Find the `/web-search` endpoint under "Web Search"
3. Click "Try it out"
4. Enter your search query
5. Click "Execute"

## 📡 API Endpoints

### POST /web-search
Search the web for information.

**Request:**
```json
{
  "query": "your search query",
  "max_results": 5,
  "include_content": true
}
```

**Response:**
```json
{
  "query": "your search query",
  "sources": [
    {
      "position": 1,
      "title": "Result Title",
      "url": "https://example.com",
      "snippet": "Result snippet..."
    }
  ],
  "provider": "tavily",
  "timestamp": "2025-02-02T12:00:00"
}
```

### GET /web-search/status
Check web search configuration and available providers.

**Response:**
```json
{
  "enabled": true,
  "default_provider": "tavily",
  "max_results": 5,
  "available_providers": {
    "duckduckgo": true,
    "tavily": true,
    "serpapi": false
  },
  "cache_enabled": true
}
```

## 💡 Using Web Search in Your Agent

The agent can now search the web programmatically:

```python
from evolving_agent.core.agent import SelfImprovingAgent

# Initialize the agent
agent = SelfImprovingAgent()
await agent.initialize()

# Search the web
results = await agent.search_web(
    query="Latest Python frameworks 2025",
    max_results=5
)

# Access results
for source in results['sources']:
    print(f"Title: {source['title']}")
    print(f"URL: {source['url']}")
    print(f"Snippet: {source['snippet']}\n")
```

## 🎨 Features

### 1. **AI-Optimized Search**
Tavily is specifically designed for AI applications, providing:
- More relevant results for AI queries
- Structured data perfect for LLM consumption
- Answer extraction from search results

### 2. **Automatic Caching**
- Search results are cached for 1 hour
- Reduces API calls and improves response time
- Cache is cleared on agent restart

### 3. **Memory Integration**
- All searches are automatically stored in the agent's long-term memory
- The agent can learn from past searches
- Search history influences future responses

### 4. **Fallback System**
- If Tavily fails, automatically falls back to DuckDuckGo
- Ensures search capability is always available
- No downtime even if one provider has issues

### 5. **Content Extraction**
- Optionally fetches full page content
- Extracts clean text from HTML
- Removes scripts, ads, and navigation elements

## 🔧 Advanced Configuration

### Switch Search Providers

Edit your `.env` file:

```bash
# Use DuckDuckGo (free, no API key)
WEB_SEARCH_DEFAULT_PROVIDER=duckduckgo

# Use Tavily (recommended, requires API key)
WEB_SEARCH_DEFAULT_PROVIDER=tavily

# Use SerpAPI (requires API key)
WEB_SEARCH_DEFAULT_PROVIDER=serpapi
SERPAPI_KEY=your_serpapi_key
```

### Adjust Result Count

```bash
# Get more results per search (1-10)
WEB_SEARCH_MAX_RESULTS=10
```

### Disable Web Search

```bash
# Temporarily disable web search
WEB_SEARCH_ENABLED=false
```

## 📊 Example Use Cases

### 1. Current Events
```json
{
  "query": "Latest news about artificial intelligence",
  "max_results": 5
}
```

### 2. Technical Research
```json
{
  "query": "Best practices for Python async programming",
  "max_results": 3
}
```

### 3. Code Examples
```json
{
  "query": "FastAPI web search integration examples",
  "max_results": 5,
  "include_content": true
}
```

### 4. Documentation Lookup
```json
{
  "query": "ChromaDB vector database documentation",
  "max_results": 3
}
```

## 🐛 Troubleshooting

### Issue: "Web search not enabled"
**Solution**: Check that `WEB_SEARCH_ENABLED=true` in your `.env` file

### Issue: "No module named 'beautifulsoup4'"
**Solution**: Run `pip install beautifulsoup4 lxml httpx`

### Issue: Tavily API errors
**Solution**: Check your API key or switch to DuckDuckGo:
```bash
WEB_SEARCH_DEFAULT_PROVIDER=duckduckgo
```

### Issue: Slow responses
**Solution**: Reduce `WEB_SEARCH_MAX_RESULTS` or disable content fetching:
```json
{
  "query": "...",
  "include_content": false
}
```

## 🔐 Security Notes

- API keys are stored in `.env` (not committed to git)
- `.env` is listed in `.gitignore`
- Never share your `.env` file or commit it to version control
- Tavily API keys are prefixed with `tvly-dev-` or `tvly-`

## 📈 Rate Limits

**Tavily Free Tier:**
- 1,000 requests per month
- 5 requests per minute

**Tips to stay within limits:**
- Results are cached for 1 hour
- Use `max_results` wisely (lower = fewer API credits)
- Consider DuckDuckGo for high-volume usage (unlimited, free)

## 🎓 Next Steps

1. **Test the integration**: Run `./quick_web_search_test.sh`
2. **Explore the API**: Visit `http://localhost:8000/docs`
3. **Build features**: Use web search in your agent's chat responses
4. **Monitor usage**: Check Tavily dashboard for API usage stats

## 🤝 Support

- **Tavily Documentation**: https://docs.tavily.com
- **API Status**: Check `/web-search/status` endpoint
- **Issues**: Check server logs for detailed error messages

---

**Your agent is now connected to the web! 🌐**
