# 🚀 Deployment Guide — Bharat Scouts & Guides Sangareddy

This guide provides clear, step-by-step instructions to deploy the BSG Sangareddy Enrollment Portal to production.

---

## 🌟 Option 1: Render.com (Recommended — Fast, Free Tier & Zero-Maintenance)

Render is the simplest and most reliable platform for deploying this Django application.

### Step 1: Push Project to GitHub
1. Initialize a git repository if not already done:
   ```bash
   git init
   git add .
   git commit -m "Initial commit for BSG Sangareddy deployment"
   ```
2. Create a new repository on [GitHub](https://github.com) (e.g., `bsg-sangareddy`).
3. Push your code:
   ```bash
   git remote add origin https://github.com/<YOUR_USERNAME>/bsg-sangareddy.git
   git branch -M main
   git push -u origin main
   ```

### Step 2: Deploy on Render
1. Log in to [Render.com](https://render.com).
2. Click **New +** -> **Web Service**.
3. Connect your GitHub repository `bsg-sangareddy`.
4. Render will auto-detect the configuration, or configure it with:
   - **Name**: `bsg-sangareddy`
   - **Runtime**: `Python 3`
   - **Build Command**: `bash build.sh`
   - **Start Command**: `gunicorn bsg_sangareddy.wsgi:application`
   - **Plan**: `Free`
5. In **Advanced -> Environment Variables**, add:
   - `PYTHON_VERSION`: `3.10.12`
   - `DJANGO_DEBUG`: `False`
   - `SECRET_KEY`: *(Click Generate or paste a secure random string)*
   - `ALLOWED_HOSTS`: `*`
6. Click **Deploy Web Service**.
7. Once deployed, Render will provide a live HTTPS URL (e.g., `https://bsg-sangareddy.onrender.com`).

---

## 🐍 Option 2: PythonAnywhere (Great for Python / SQLite)

1. Sign up at [PythonAnywhere](https://www.pythonanywhere.com/).
2. Open a **Bash Console** in your PythonAnywhere dashboard.
3. Clone your GitHub repository:
   ```bash
   git clone https://github.com/<YOUR_USERNAME>/bsg-sangareddy.git
   cd bsg-sangareddy
   ```
4. Create and activate a virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
5. Run migrations and collect static files:
   ```bash
   python manage.py migrate
   python manage.py collectstatic --no-input
   python manage.py load_official_sanctioned_schools
   ```
6. In PythonAnywhere's **Web** tab:
   - Add a new web app (Manual configuration with Python 3.10).
   - Set **Source code**: `/home/<your-username>/bsg-sangareddy`
   - Set **Working directory**: `/home/<your-username>/bsg-sangareddy`
   - Set **Virtualenv**: `/home/<your-username>/bsg-sangareddy/venv`
   - Edit the **WSGI configuration file** to point to your Django settings:
     ```python
     import os
     import sys
     path = '/home/<your-username>/bsg-sangareddy'
     if path not in sys.path:
         sys.path.append(path)
     os.environ['DJANGO_SETTINGS_MODULE'] = 'bsg_sangareddy.settings'
     from django.core.wsgi import get_wsgi_application
     application = get_wsgi_application()
     ```
   - Set Static Files mappings:
     - URL: `/static/` -> Directory: `/home/<your-username>/bsg-sangareddy/staticfiles`
7. Click **Reload <your-username>.pythonanywhere.com**.

---

## 🚂 Option 3: Railway.app

1. Sign up on [Railway.app](https://railway.app/).
2. Click **New Project** -> **Deploy from GitHub repo**.
3. Select `bsg-sangareddy`.
4. In Railway project settings, add the Environment Variables:
   - `DJANGO_DEBUG`: `False`
   - `SECRET_KEY`: *(Secure key)*
   - `ALLOWED_HOSTS`: `*`
5. Railway reads `Procfile` and `requirements.txt` automatically.
6. Generate a public domain under service **Settings -> Networking -> Generate Domain**.

---

## 🔑 Default Administrator Credentials

Once deployed and the database is initialized:
- **Admin Portal**: `<YOUR_URL>/login/` (or `<YOUR_URL>/admin/`)
- **Username**: `admin`
- **Password**: `Admin@Sangareddy2026`

All 174+ sanctioned schools across Sangareddy mandals will be automatically provisioned with their respective UDISE logins and default credentials (`BSG@Sangareddy2026`).
