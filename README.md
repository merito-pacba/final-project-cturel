[![Open in Codespaces](https://classroom.github.com/assets/launch-codespace-2972f46106e565e64193e422d61a12cf1da4916b45550586e14ef0a7c637dd04.svg)](https://classroom.github.com/open-in-codespaces?assignment_repo_id=22634378)
# Trigger

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python app.py
```

Open: `http://127.0.0.1:8000`

## Azure App Service

- Startup Command:

```text
gunicorn --bind=0.0.0.0:8000 app:app
```

- App Settings:
  - `APP_NAME`
  - `APP_ENV`
  - `SECRET_KEY`
  - `SCM_DO_BUILD_DURING_DEPLOYMENT=1`
  - `ENABLE_ORYX_BUILD=true`
  - Optional for image upload: `AZURE_STORAGE_CONNECTION_STRING`, `AZURE_STORAGE_CONTAINER`

## Azure Storage (Image Upload)

If Blob settings are configured, users can upload outfit images from the form and the app stores the file in Azure Blob Storage, then serves it by Blob URL.

- Use a container like `outfit-images`
- Keep container access as blob-level public if you want direct image rendering in the page
- If Blob settings are missing, the app still works and uses manual image URL input

## ZIP deploy (without parent folder)

```bash
zip -r deploy.zip app.py requirements.txt templates static -x "*.DS_Store" "*/__pycache__/*"
```
