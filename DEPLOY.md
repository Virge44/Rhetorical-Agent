# Deploying the Rhetorical Agent

Your host will need the app code and two **environment variables** (never commit the values):

- `OPENAI_API_KEY` — required for the LLM
- `X_BEARER_TOKEN` — required when users paste tweet URLs (optional if thread-text only is fine)

**Getting the code into a repo:** The Rhetorical Agent folder may sit next to AgenC (not inside it). To deploy you need it in Git: either create a **new repo** and push only the contents of the `Rhetorical Agent` folder, or **copy/move** that folder into the AgenC repo (e.g. `AgenC/rhetorical-agent/`), commit, and use the subdirectory option below.

- `OPENAI_API_KEY` — required for the LLM
- `X_BEARER_TOKEN` — required when users paste tweet URLs (optional if thread-text only is fine)

---

## Option A: Render (free tier)

1. Push the **Rhetorical Agent** folder to a Git repo (GitHub/GitLab). You can:
   - Create a new repo with only the contents of `Rhetorical Agent`, or
   - Use the existing AgenC repo and deploy from a **subdirectory** (see step 2).

2. Go to [render.com](https://render.com) → Sign up / Log in → **New** → **Web Service**.

3. Connect your repo. If the agent is in a subdirectory (e.g. `Rhetorical Agent` inside AgenC):
   - After connecting, set **Root Directory** to `Rhetorical Agent` (or the path to that folder in the repo).

4. Configure:
   - **Runtime:** Python 3
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn --bind 0.0.0.0:$PORT app:app`

5. **Environment:** Add variables:
   - `OPENAI_API_KEY` = your key  
   - `X_BEARER_TOKEN` = your token  

6. **Create Web Service**. Render will build and deploy. Your app will be at `https://<your-service>.onrender.com`.

**Free tier note:** The service spins down after ~15 minutes of no traffic; the first request after that may take 30–60 seconds (cold start).

---

## Option B: DigitalOcean App Platform

1. Push the Rhetorical Agent code to a Git repo (same as above — new repo or subdirectory of an existing one).

2. Go to [cloud.digitalocean.com](https://cloud.digitalocean.com) → **Apps** → **Create App**.

3. **Choose source:** GitHub/GitLab, select the repo. If the app is in a subdirectory, set **Source Directory** to that path (e.g. `Rhetorical Agent`).

4. **Resources:** DigitalOcean will detect a Python app. Ensure:
   - **Run Command:** `gunicorn --bind 0.0.0.0:$PORT app:app`
   - **Build Command:** `pip install -r requirements.txt` (or leave auto-detected)

5. **Environment Variables:** Add:
   - `OPENAI_API_KEY`  
   - `X_BEARER_TOKEN`  

6. Choose a plan (Basic is typically ~$5/mo) and **Create Resources**.

Your app will be at `https://<your-app>.ondigitalocean.app`. No spin-down; always on.

---

## Subdirectory deploy (agent lives inside AgenC repo)

If you don’t want a separate repo:

- **Render:** When adding the service, after selecting the repo, set **Root Directory** to the folder name exactly as it appears in the repo (e.g. `Rhetorical Agent`). All build/start commands run from that directory.
- **DigitalOcean:** When configuring the component, set **Source Directory** to that folder. Same idea.

Then add a **.gitignore** inside `Rhetorical Agent` (or rely on the repo root’s .gitignore) so `.env` and other secrets are never committed.
