# FLUDO CAD Studio - Render.com Deployment Guide

## Quick Start (3 Minutes!)

### Step 1: Sign Up for Render
1. Go to https://render.com
2. Click "Get Started" 
3. Sign up with your GitHub account (recommended) or email
4. Verify your email if needed

### Step 2: Create New Web Service
1. Click "New +" button in top right
2. Select "Web Service"
3. Connect your GitHub repository: `sachinmaurya-agi/Hase-Version--3`
4. Click "Connect" next to the repository

### Step 3: Configure Service
Fill in the following settings:

**Basic Settings:**
- **Name**: `fludo-cad-studio` (or any name you prefer)
- **Region**: Choose closest to you (e.g., Oregon, Frankfurt, Singapore)
- **Branch**: `main`
- **Root Directory**: Leave empty
- **Runtime**: `Python 3`

**Build & Deploy:**
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `uvicorn app.server:app --host 0.0.0.0 --port $PORT`

**Instance Type:**
- Select **Free** (512MB RAM, 750 hours/month free)

### Step 4: Add Environment Variable
Before clicking "Create Web Service":
1. Scroll down to "Environment Variables"
2. Click "Add Environment Variable"
3. Add:
   - **Key**: `GEMINI_API_KEY`
   - **Value**: Your API key from https://makersuite.google.com/app/apikey
   - Click "Add"

> **Note**: The app works without GEMINI_API_KEY but AI chat will be disabled. You can add it later.

### Step 5: Deploy!
1. Click "Create Web Service" at the bottom
2. Render will start building your app (takes 5-10 minutes first time)
3. Watch the logs to see progress

### Step 6: Access Your App
Once deployed, you'll get a URL like: `https://fludo-cad-studio.onrender.com`

**Available Interfaces:**
- Main: `https://fludo-cad-studio.onrender.com/`
- Enhanced CASCADE: `https://fludo-cad-studio.onrender.com/fludo_cascade_enhanced.html`
- CASCADE Style: `https://fludo-cad-studio.onrender.com/cascade_studio.html`
- Alternative: `https://fludo-cad-studio.onrender.com/cad_studio_v2.html`

## Important Notes

### Free Tier Limits
- **750 hours/month** of runtime (enough for personal use)
- **512MB RAM** (sufficient for CadQuery)
- **Sleeps after 15 min inactivity** (wakes up in ~30 seconds on next request)
- **100GB bandwidth/month**

### Add Environment Variables Later
If you skipped GEMINI_API_KEY:
1. Go to your service dashboard
2. Click "Environment" in left sidebar
3. Click "Add Environment Variable"
4. Add `GEMINI_API_KEY` with your API key
5. Service will auto-redeploy

### Custom Domain (Optional)
1. Go to "Settings" tab
2. Scroll to "Custom Domain"
3. Click "Add Custom Domain"
4. Follow instructions to point your domain to Render

### Monitoring
- **Logs**: Click "Logs" tab to see real-time application logs
- **Metrics**: Click "Metrics" tab to see CPU/Memory usage
- **Events**: Click "Events" tab to see deployment history

## Troubleshooting

### Build Failed
If build fails, check:
1. `requirements.txt` is present in root directory
2. All dependencies are compatible
3. Check build logs for specific error

### Service Won't Start
If service deploys but won't start:
1. Check logs for Python errors
2. Verify start command is correct: `uvicorn app.server:app --host 0.0.0.0 --port $PORT`
3. Make sure `app/server.py` exists

### App is Slow to Wake Up
- Free tier services sleep after 15 minutes of inactivity
- First request wakes it up (takes ~30 seconds)
- Upgrade to paid tier ($7/month) for always-on service

### Memory Issues
If you see memory errors:
1. Free tier has 512MB RAM
2. Upgrade to Starter ($7/month) for 2GB RAM
3. Or optimize code to use less memory

## Upgrade Options

### Starter Plan ($7/month)
- **2GB RAM** (better for complex CAD operations)
- **Always-on** (no sleep)
- **Persistent disk** (100GB)
- **Better CPU**

### Pro Plan ($25/month)
- **8GB RAM** (handles large models)
- **Autoscaling** (multiple instances)
- **Priority support**

## Cost Comparison
- **Free**: $0/month (750 hours, sleeps after 15min)
- **Starter**: $7/month (always-on, 2GB RAM)
- **Pro**: $25/month (autoscaling, 8GB RAM)

## Why Render over AWS?
✅ **3 minutes** to deploy vs 15 minutes  
✅ **Zero config** needed (no CLI, no complex setup)  
✅ **Auto-deploys** on git push  
✅ **Free SSL** certificate  
✅ **Simple dashboard** vs AWS console maze  
✅ **750 hours free** vs careful free tier tracking  
✅ **No credit card** required for free tier  

## Support
- Render Docs: https://render.com/docs
- Community Forum: https://community.render.com
- Status Page: https://status.render.com

## Next Steps After Deployment
1. ✅ Test all 4 interfaces
2. ✅ Run example CadQuery code
3. ✅ Test Export (STL, STEP, IGES, DXF)
4. ✅ Test AI chat with GEMINI_API_KEY
5. ✅ Share your deployed URL!

---

**Deployment Time**: ~10 minutes total (5 min setup + 5 min build)  
**Recommended**: Keep browser tab open to watch build logs
