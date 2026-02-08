# Discord Integration Setup Guide

This guide will help you set up Discord integration for the self-improving AI agent.

## Overview

The Discord integration allows your AI agent to:
- **Receive messages** from Discord users in configured channels
- **Respond to messages** with intelligent, context-aware replies
- **Post status updates** about self-improvements and knowledge updates

## Architecture

The integration follows the existing GitHubIntegration pattern:
- **DiscordIntegration**: Core integration class managing the Discord client
- **DiscordFormatter**: Handles message formatting and rich embeds
- **RateLimiter**: Prevents spam with configurable rate limiting
- Clean integration with FastAPI lifespan management
- Async callback system for status updates

## Setup Instructions

### 1. Create a Discord Bot

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click **"New Application"** and give it a name (e.g., "Self-Improving AI Agent")
3. Navigate to the **"Bot"** tab
4. Click **"Add Bot"** to create your bot
5. Under **"Privileged Gateway Intents"**, enable:
   - ✅ **Message Content Intent** (required)
   - ✅ **Server Members Intent** (optional, for user context)
6. Click **"Reset Token"** and copy the bot token (you'll need this later)

### 2. Invite Bot to Your Server

1. Navigate to **OAuth2 → URL Generator**
2. Select scopes:
   - ✅ `bot`
   - ✅ `applications.commands`
3. Select bot permissions:
   - ✅ Send Messages
   - ✅ Send Messages in Threads
   - ✅ Embed Links
   - ✅ Attach Files
   - ✅ Read Message History
   - ✅ Add Reactions
4. Copy the generated URL
5. Open the URL in your browser to invite the bot to your Discord server

### 3. Get Channel IDs

1. Enable **Developer Mode** in Discord:
   - User Settings → Advanced → Developer Mode ✅
2. Right-click on the channels where you want the bot to operate
3. Click **"Copy ID"** to get each channel ID
4. Note down:
   - Channel IDs where bot should respond to messages
   - Status channel ID for bot status updates

### 4. Configure Environment Variables

Edit your `.env` file (or create one from `.env.example`):

```bash
# Discord Bot Configuration
DISCORD_BOT_TOKEN=your_actual_discord_bot_token_here
DISCORD_ENABLED=true

# Channel Configuration
DISCORD_CHANNEL_IDS=1234567890,9876543210  # Replace with your channel IDs
DISCORD_STATUS_CHANNEL_ID=9876543210        # Replace with your status channel ID

# Bot Behavior (configured based on your preferences)
DISCORD_MENTION_REQUIRED=false              # Bot responds to all messages
DISCORD_TYPING_INDICATOR=true               # Shows typing while processing
DISCORD_EMBED_RESPONSES=true                # Uses rich embeds
DISCORD_COMMAND_PREFIX=                     # Empty = natural message format

# Rate Limiting
DISCORD_RATE_LIMIT_MESSAGES=10              # Max messages per user per minute
DISCORD_COOLDOWN_SECONDS=2                  # Cooldown between messages

# Status Updates
DISCORD_STATUS_UPDATES_ENABLED=true         # Enable status updates
DISCORD_STATUS_ON_IMPROVEMENT=true          # Post self-improvement updates
DISCORD_STATUS_ON_KNOWLEDGE_UPDATE=true     # Post knowledge updates
DISCORD_STATUS_ON_HIGH_QUALITY=false        # Don't post high-quality interaction updates
```

### 5. Install Dependencies

Install the required Discord library:

```bash
# Using pip
pip install discord.py>=2.3.0

# Or install all requirements
pip install -r requirements.txt
```

### 6. Start the Server

Start your FastAPI server:

```bash
python api_server.py
```

Or using uvicorn:

```bash
uvicorn api_server:app --host 0.0.0.0 --port 8000 --reload
```

You should see log messages indicating Discord integration started:
```
INFO: Initializing Discord integration...
INFO: Discord integration started successfully
INFO: Discord bot logged in as YourBotName#1234
INFO: Connected to X guilds
```

## Usage

### Sending Messages to the Bot

Based on your configuration (natural message format, no mention required):

1. Simply type your message in any configured channel
2. The bot will show a typing indicator while processing
3. You'll receive a response with:
   - Rich embed formatting
   - Quality score (if available)
   - Processing time

**Example:**
```
User: What are the best practices for Python async programming?

Bot: [Rich embed with detailed response]
    Quality Score: ⭐ 0.92
    Processing Time: ⏱️ 2.35s
```

### Status Updates

The bot will automatically post status updates to the designated status channel:

#### Self-Improvement Updates
Posted every 10 interactions when the agent analyzes and improves its own code:
```
🔧 Self-Improvement Cycle Complete
The agent has analyzed its own code and identified improvements.

Improvements Made:
• Optimized context retrieval algorithm
• Enhanced memory storage efficiency
• Improved error handling

Files Modified: 3
```

#### Knowledge Base Updates
Posted when significant new knowledge is added (evaluation score ≥ 0.8):
```
📚 Knowledge Base Updated
New knowledge has been added to the agent's knowledge base.

Category: Programming
Entries Added: 5
Summary: Advanced async patterns in Python...
```

## Features

### Intelligent Message Handling
- ✅ Automatic conversation context extraction
- ✅ User information included in context hints
- ✅ Discord channel context for relevant responses
- ✅ Memory storage of all interactions

### Rate Limiting
- ✅ Prevents spam (10 messages per minute per user)
- ✅ 2-second cooldown between messages
- ✅ Friendly rate limit notifications
- ✅ Per-user tracking

### Error Handling
- ✅ Graceful error messages to users
- ✅ Automatic reconnection on disconnect
- ✅ Comprehensive logging
- ✅ Retry logic for Discord API failures

### Message Formatting
- ✅ Rich embeds with color coding
- ✅ Automatic message splitting for long responses
- ✅ Quality score indicators
- ✅ Processing time display
- ✅ User-friendly error messages

## Testing

Run the test suite to verify the integration:

```bash
pytest tests/test_discord_integration.py -v
```

This will test:
- Rate limiter functionality
- Message formatting
- Discord integration initialization
- Response sending
- Status updates

## Troubleshooting

### Bot doesn't respond to messages

1. **Check bot is online**: Look for "Discord bot logged in" in logs
2. **Verify channel IDs**: Ensure `DISCORD_CHANNEL_IDS` contains correct channel IDs
3. **Check permissions**: Bot needs "Read Messages" and "Send Messages" permissions
4. **Verify Message Content Intent**: Must be enabled in Discord Developer Portal
5. **Check mention setting**: If `DISCORD_MENTION_REQUIRED=true`, you must @mention the bot

### Bot crashes on startup

1. **Invalid token**: Verify `DISCORD_BOT_TOKEN` is correct
2. **Missing intents**: Enable Message Content Intent in Discord Developer Portal
3. **Check logs**: Look for error messages in `agent.log`

### Status updates not posting

1. **Verify status channel ID**: Check `DISCORD_STATUS_CHANNEL_ID` is correct
2. **Check status updates enabled**: Ensure `DISCORD_STATUS_UPDATES_ENABLED=true`
3. **Verify permissions**: Bot needs "Send Messages" permission in status channel
4. **Trigger event**: For self-improvement, need 10+ interactions

### Rate limiting issues

1. **Adjust limits**: Modify `DISCORD_RATE_LIMIT_MESSAGES` in `.env`
2. **Change cooldown**: Adjust `DISCORD_COOLDOWN_SECONDS`
3. **Reset user**: Rate limits reset automatically after time window

## Configuration Options

### Response Behavior

- **DISCORD_MENTION_REQUIRED**: Set to `true` to require @mention to respond
- **DISCORD_EMBED_RESPONSES**: Set to `false` for plain text responses
- **DISCORD_TYPING_INDICATOR**: Set to `false` to disable typing indicator
- **DISCORD_MAX_MESSAGE_LENGTH**: Discord limit is 2000, don't change unless needed

### Status Updates

- **DISCORD_STATUS_UPDATES_ENABLED**: Master switch for all status updates
- **DISCORD_STATUS_ON_IMPROVEMENT**: Self-improvement cycle updates
- **DISCORD_STATUS_ON_KNOWLEDGE_UPDATE**: Knowledge base updates
- **DISCORD_STATUS_ON_HIGH_QUALITY**: High-quality interaction updates (score > 0.9)

### Rate Limiting

- **DISCORD_RATE_LIMIT_MESSAGES**: Max messages per user per 60 seconds
- **DISCORD_COOLDOWN_SECONDS**: Minimum time between messages from same user

## Architecture Details

### File Structure

```
evolving_agent/integrations/
├── __init__.py                  # Package exports
├── discord_integration.py       # Core integration class (~450 lines)
├── discord_formatter.py         # Message formatting (~350 lines)
└── discord_rate_limiter.py      # Rate limiting (~200 lines)

tests/
└── test_discord_integration.py  # Unit tests
```

### Integration Flow

```
1. FastAPI starts → lifespan context manager initializes
2. Discord integration created with agent and config
3. Agent callback registered for status updates
4. Discord bot starts in background task
5. Bot connects to Discord API
6. Event handlers activate

On Message:
  Discord → on_message → handle_message → rate limit check →
  agent.run(query, context_hints) → response → format →
  send to Discord channel

On Status Event:
  Agent → _notify_status → handle_status_update →
  format status → send to status channel
```

### Callback System

The agent now supports status callbacks:
```python
# In agent initialization (api_server.py)
discord_integration.initialize()
# Registers: agent.register_status_callback(discord_integration.handle_status_update)

# In agent.py when events occur
await self._notify_status("self_improvement", {
    "cycle_count": self.improvement_cycle_count,
    "improvements": [...],
    ...
})

# Discord integration receives and posts to Discord
```

## Security Best Practices

1. **Never commit your `.env` file**: Keep bot token secret
2. **Use environment-specific tokens**: Different tokens for dev/prod
3. **Restrict channels**: Only allow bot in specific channels
4. **Monitor usage**: Check logs for unusual activity
5. **Role-based access**: Consider adding role checks (future enhancement)

## Future Enhancements

Potential improvements for future versions:

- **Slash Commands**: `/ask`, `/status`, `/memory` commands
- **Interactive Components**: Buttons for follow-up questions
- **Thread Support**: Longer conversations in threads
- **Multi-Server Support**: Separate contexts per Discord server
- **Voice Channel Updates**: Status updates in voice channels
- **Analytics Dashboard**: Usage statistics and metrics
- **Advanced Permissions**: Role-based access control

## Support

If you encounter issues:

1. Check logs in `agent.log`
2. Verify all configuration in `.env`
3. Review Discord Developer Portal settings
4. Run tests: `pytest tests/test_discord_integration.py -v`
5. Check Discord bot status in Developer Portal

## Example Workflow

Here's a complete example of the Discord bot in action:

1. **User sends message**:
   ```
   User: Can you explain how the self-improvement system works?
   ```

2. **Bot shows typing indicator** (if enabled)

3. **Bot responds with rich embed**:
   ```
   Self-Improving AI Agent

   The self-improvement system works through a continuous cycle:

   1. **Performance Analysis**: After every 10 interactions, the agent
      analyzes its response quality scores and identifies patterns...

   [Detailed explanation continues...]

   Quality Score: ⭐ 0.91
   Processing Time: ⏱️ 3.12s
   Query ID: abc123def456
   ```

4. **After 10 interactions, status update posted**:
   ```
   🔧 Self-Improvement Cycle Complete

   The agent has analyzed its own code and identified improvements.

   Improvements Made:
   • Enhanced context retrieval algorithm
   • Optimized memory storage
   • Improved response evaluation

   Files Modified: 2
   Cycle Count: 5
   ```

5. **High-quality interaction leads to knowledge update**:
   ```
   📚 Knowledge Base Updated

   New knowledge has been added to the agent's knowledge base.

   Category: AI Systems
   Evaluation Score: 0.91
   Interaction Count: 47
   ```

## Conclusion

Your Discord integration is now complete and ready to use! The bot will:
- ✅ Respond to messages in configured channels
- ✅ Post status updates about self-improvements
- ✅ Post status updates about knowledge updates
- ✅ Use rich embeds for better presentation
- ✅ Rate limit to prevent spam
- ✅ Handle errors gracefully

Enjoy your intelligent Discord bot! 🤖✨
