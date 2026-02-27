# Deployment Guide

This guide covers deploying the Evolving AI Agent to Coolify (backend) and Vercel (frontend).

## Prerequisites

- GitHub account with the repository pushed
- Coolify instance (self-hosted or cloud)
- Vercel account

---

## Part 1: Deploy Backend to Coolify

### Step 1: Create New Resource in Coolify

1. Log in to your Coolify dashboard
2. Click **"+ New Resource"**
3. Select **"Docker Compose"** or **"Dockerfile"**
4. Choose your GitHub repository: `DavinciDreams/evolving-ai`
5. Select branch: `main`

### Step 2: Configure Build Settings

**If using Dockerfile:**
- Build context: `/`
- Dockerfile location: `./Dockerfile`
- Port: `8000`

**If using Docker Compose:**
- Compose file: `./docker-compose.yml`
- Port: `8000`

### Step 3: Set Environment Variables

In Coolify, add these environment variables:

**Required:**
```bash
# LLM Provider (choose one)
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...

# Or use Anthropic
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...

# Or use OpenRouter
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=sk-or-...

MODEL_NAME=gpt-4  # or claude-3-opus-20240229, etc.
```

**Optional but Recommended:**
```bash
# GitHub Integration
GITHUB_TOKEN=ghp_...
GITHUB_REPO=DavinciDreams/evolving-ai
ENABLE_SELF_MODIFICATION=false

# Discord Integration
DISCORD_ENABLED=false
DISCORD_BOT_TOKEN=your_discord_bot_token
DISCORD_ALLOWED_CHANNEL_IDS=123456789,987654321

# Web Search
WEB_SEARCH_ENABLED=true
WEB_SEARCH_DEFAULT_PROVIDER=duckduckgo
TAVILY_API_KEY=tvly-...
SERPAPI_KEY=your_serpapi_key

# Memory
CHROMA_PERSIST_DIR=/app/data/chroma
MEMORY_COLLECTION_NAME=agent_memories

# Logging
LOG_LEVEL=INFO
```

### Step 4: Deploy

1. Click **"Deploy"**
2. Wait for the build to complete
3. Once deployed, note your backend URL: `https://your-app.coolify.app`
4. Test the API by visiting: `https://your-app.coolify.app/docs`

### Step 5: Verify Deployment

Check the health endpoint:
```bash
curl https://your-app.coolify.app/health
```

Should return:
```json
{
  "status": "healthy",
  "timestamp": "...",
  "agent_initialized": true,
  "github_available": false
}
```

---

## Part 2: Deploy Frontend to Vercel

### Step 1: Import Project to Vercel

1. Go to [vercel.com](https://vercel.com)
2. Click **"Add New..."** → **"Project"**
3. Import your GitHub repository: `DavinciDreams/evolving-ai`
4. Select the `frontend` directory as the root directory

### Step 2: Configure Build Settings

Vercel should auto-detect Vite. Verify these settings:

- **Framework Preset:** Vite
- **Root Directory:** `frontend`
- **Build Command:** `npm run build`
- **Output Directory:** `dist`
- **Install Command:** `npm install`

### Step 3: Set Environment Variables

Add these environment variables in Vercel:

```bash
VITE_API_BASE_URL=https://your-app.coolify.app
VITE_APP_NAME=Evolving AI Agent
VITE_ENABLE_DEVTOOLS=false
```

**Important:** Replace `https://your-app.coolify.app` with your actual Coolify backend URL from Part 1.

### Step 4: Update vercel.json

Before deploying, update `frontend/vercel.json` with your actual backend URL:

```json
{
  "rewrites": [
    {
      "source": "/api/:path*",
      "destination": "https://your-actual-backend.coolify.app/:path*"
    }
  ]
}
```

### Step 5: Deploy

1. Click **"Deploy"**
2. Wait for the build to complete
3. Your frontend will be live at: `https://your-app.vercel.app`

### Step 6: Configure Custom Domain (Optional)

1. In Vercel project settings, go to **"Domains"**
2. Add your custom domain
3. Follow DNS configuration instructions

---

## Part 3: Post-Deployment Configuration

### Update CORS Settings

If you encounter CORS issues, update the backend's CORS settings in `api_server.py`:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://your-app.vercel.app",
        "https://your-custom-domain.com"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

Then redeploy the backend.

### Test the Integration

1. Visit your Vercel frontend URL
2. Navigate to the Chat page
3. Send a test message
4. Verify the response comes from the backend

---

## Troubleshooting

### Backend Issues

**Container won't start:**
- Check Coolify logs
- Verify all required environment variables are set
- Ensure API keys are valid

**API returning 503:**
- Agent initialization may have failed
- Check logs for LLM provider errors
- Verify API keys

### Frontend Issues

**API calls failing:**
- Verify `VITE_API_BASE_URL` is correct
- Check browser console for CORS errors
- Ensure backend is running and accessible

**Build failing:**
- Clear Vercel build cache
- Check `package.json` dependencies
- Verify Node version compatibility

### Connection Issues

**CORS errors:**
- Update backend `allow_origins` with frontend URL
- Redeploy backend

**404 on API calls:**
- Check Vercel rewrites configuration
- Verify backend endpoints exist

---

## Monitoring

### Backend Monitoring (Coolify)
- View logs in Coolify dashboard
- Monitor resource usage
- Set up alerts for downtime

### Frontend Monitoring (Vercel)
- Check Analytics in Vercel dashboard
- Monitor function logs
- Set up deployment notifications

---

## Updating Deployments

### Backend Updates
1. Push changes to GitHub
2. Coolify will auto-deploy (if configured)
3. Or manually trigger deployment in Coolify

### Frontend Updates
1. Push changes to GitHub
2. Vercel will auto-deploy
3. Or manually trigger in Vercel dashboard

---

## Security Best Practices

1. **Never commit API keys** - Use environment variables
2. **Enable HTTPS** - Both platforms provide SSL by default
3. **Restrict CORS** - Only allow your frontend domain
4. **Use secrets** - For sensitive environment variables
5. **Enable rate limiting** - Protect your API endpoints
6. **Monitor logs** - Watch for suspicious activity
7. **Keep dependencies updated** - Regularly update packages

---

## Cost Optimization

### Coolify
- Monitor resource usage
- Scale down if needed
- Use appropriate instance size

### Vercel
- Free tier includes:
  - 100 GB bandwidth
  - Serverless function invocations
- Upgrade to Pro if needed

---

## Support

For issues:
- Backend: Check Coolify logs and GitHub issues
- Frontend: Check Vercel deployment logs
- General: See project README.md

---

## Quick Reference

### Important URLs
- Backend API: `https://your-app.coolify.app`
- API Docs: `https://your-app.coolify.app/docs`
- Frontend: `https://your-app.vercel.app`
- Health Check: `https://your-app.coolify.app/health`

### Useful Commands
```bash
# Test backend locally
docker-compose up

# Build frontend locally
cd frontend && npm run build

# Preview frontend build
cd frontend && npm run preview
```
