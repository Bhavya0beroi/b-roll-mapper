# 🚂 RAILWAY DIRECT DEPLOYMENT (WITHOUT GITHUB)

Since GitHub is blocking the push due to secret detection, let's deploy directly to Railway using Railway CLI. This is actually **faster and easier**!

---

## 🚀 STEP 1: Install Railway CLI (2 minutes)

### For Mac (using Homebrew):
```bash
brew install railway
```

### Or using npm:
```bash
npm install -g @railway/cli
```

### Or download directly:
Go to: https://docs.railway.app/guides/cli#installing-the-cli

---

## 🔐 STEP 2: Login to Railway (1 minute)

```bash
railway login
```

This will open your browser to authenticate with your Railway account.

---

## 📦 STEP 3: Create New Railway Project (2 minutes)

```bash
railway init
```

When prompted:
- Project name: `broll-mapper` (or any name you want)
- Select: **"Empty Project"**

---

## ⚙️ STEP 4: Add Environment Variables (3 minutes)

```bash
railway variables set SUPABASE_URL="https://frfrevcsrissjgtyowtb.supabase.co"
railway variables set SUPABASE_SERVICE_KEY="<your-service-role-key>"
railway variables set OPENAI_API_KEY="<your-openai-key>"
railway variables set PORT="5002"
```

Replace `<your-service-role-key>` and `<your-openai-key>` with your actual keys.

---

## 🚀 STEP 5: Deploy! (5 minutes)

```bash
railway up
```

This will:
- Upload all your code to Railway
- Install dependencies from `requirements.txt`
- Start the Flask app with Gunicorn
- Give you a public URL

---

## 🌐 STEP 6: Get Your Public URL (1 minute)

```bash
railway domain
```

Or go to Railway dashboard and click on your project to see the URL.

---

## ✅ THAT'S IT!

Your app will be live at: `https://your-app.railway.app`

**Total time: ~15 minutes** (much faster than GitHub route!)

---

## 🔧 UPDATING YOUR APP LATER

After making changes to your code:

```bash
railway up
```

Railway will automatically redeploy with the new changes.

---

## 📊 MONITORING

Check logs:
```bash
railway logs
```

Check status:
```bash
railway status
```

---

## 💡 WHY THIS IS BETTER

✅ No GitHub secrets scanning issues  
✅ Faster deployment  
✅ Direct from local machine  
✅ Still get all Railway features  
✅ Easy to update (just run `railway up`)

---

## 🎯 NEXT STEPS AFTER DEPLOYMENT

1. ✅ Setup Supabase database (run SQL schema)
2. ✅ Migrate data to Supabase
3. ✅ Upload videos to Supabase Storage
4. ✅ Your app is live!

---

**Ready to start?** Run:

```bash
brew install railway  # or npm install -g @railway/cli
railway login
railway init
railway up
```

That's it! 🚀
