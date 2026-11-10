# CloudDesk — 100% Free Cloud Deployment Guide

This guide walks you through deploying **CloudDesk** live to the public internet using **100% free cloud tiers** (no credit card required).

---

## 🎯 Recommended Architecture (Best for Portfolios)

```text
┌───────────────────────────────┐           ┌────────────────────────────────┐
│   Vercel (Free Hobby Tier)    │   HTTPS   │   Render.com (Free Web Tier)   │
│   Next.js 15 Frontend         ├──────────►│   FastAPI + LangGraph Backend  │
│   https://clouddesk.vercel.app│           │   https://clouddesk.onrender.com   │
└───────────────────────────────┘           └────────────────────────────────┘
```

- **Frontend on Vercel**: 100% Free, Edge CDN, instant global loads, native Next.js 15 support.
- **Backend on Render**: 100% Free (750 free instance-hours/month), automatic HTTPS, Python/uv support.

---

## 🚀 Step 1: Deploy Backend to Render.com (Free)

1. Sign up / log in to [**Render.com**](https://render.com) using your GitHub account (`lokesh-repaka`).
2. On your Render Dashboard, click **New +** &rarr; **Web Service**.
3. Select **Build and deploy from a Git repository** and pick `CloudDesk`.
4. Fill in the service settings:
   - **Name**: `clouddesk-api` (or a name of your choice)
   - **Region**: Choose the closest region (e.g. `Oregon (US West)` or `Frankfurt`)
   - **Branch**: `development` (or `main`)
   - **Root Directory**: *(leave blank)*
   - **Runtime**: `Python`
   - **Build Command**:
     ```bash
     pip install uv && uv sync --frozen --no-dev
     ```
   - **Start Command**:
     ```bash
     uv run uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT
     ```
   - **Instance Type**: Select **Free** ($0/month).
5. Scroll down to **Environment Variables** and add:
   | Key | Value | Description |
   |---|---|---|
   | `ENVIRONMENT` | `production` | Production mode |
   | `DEMO_MODE` | `true` | Offline / Demo harness with pre-seeded data |
   | `LLM_PROVIDER` | `fake` | Deterministic responses without OpenAI API cost |
   | `VECTOR_STORE` | `memory` | In-memory Qdrant vector index |
   | `USE_FAKE_REDIS` | `true` | In-memory fakeredis cache |
   | `CORS_ORIGINS` | `*` | Allows your frontend to connect |
   | `DATABASE_URL` | `sqlite+aiosqlite:///./data/support.db` | SQLite database |
   | `CHECKPOINT_DB_PATH` | `./data/checkpoints.db` | Checkpoint storage |
6. Click **Create Web Service**.
7. Wait 2–3 minutes. Once deployed, Render gives you a public URL, for example:
   ```text
   https://clouddesk-api-xxxx.onrender.com
   ```
   *(Verify by opening `https://<your-backend-url>/health/live` in your browser &rarr; should return `{"status":"ok"}`).*

---

## ⚡ Step 2: Deploy Frontend to Vercel (Free)

1. Sign up / log in to [**Vercel.com**](https://vercel.com) with GitHub.
2. Click **Add New...** &rarr; **Project**.
3. Import your `CloudDesk` repository.
4. In the configuration screen:
   - **Project Name**: `clouddesk`
   - **Framework Preset**: `Next.js` (detected automatically)
   - **Root Directory**: Click **Edit** and select **`frontend`** 👈 *(Crucial)*
5. Under **Environment Variables**, add:
   | Key | Value |
   |---|---|
   | `NEXT_PUBLIC_API_URL` | `https://clouddesk-api-xxxx.onrender.com` *(your Render backend URL from Step 1)* |
6. Click **Deploy**.
7. In ~60 seconds, your site is live at:
   ```text
   https://clouddesk-xxxx.vercel.app
   ```

---

## 🛠️ Alternative Option: 1-Click Render Blueprint

If you prefer to host **both** the backend and frontend on Render using a single click:

1. In Render, click **Blueprints** in the top navigation.
2. Click **New Blueprint Instance**.
3. Connect your `CloudDesk` repository.
4. Render will read [`render.yaml`](../render.yaml) automatically and spin up both `clouddesk-api` and `clouddesk-ui`.
5. Click **Apply**.

---

## 💡 Pro-Tips for Your Portfolio

- **Add to GitHub README**: Put badges linking to your live Vercel URL at the top of your GitHub repository.
- **Render Free Tier Sleep**: On the free tier, Render sleeps after 15 minutes of inactivity. When someone clicks your portfolio link, the first backend request may take ~30 seconds to wake up, but the frontend stays instantly fast on Vercel.
- **Custom Domain**: Both Vercel and Render allow adding custom domains (e.g. `clouddesk.lokeshrepaka.dev`) 100% free with automated SSL certificates.

