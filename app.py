import os
from datetime import datetime, timezone
from uuid import uuid4
from dotenv import load_dotenv
from flask import Flask, redirect, render_template, request, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.utils import secure_filename
from azure.storage.blob import BlobServiceClient, ContainerClient, ContentSettings

if load_dotenv:
    load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")

app = Flask(__name__, template_folder=TEMPLATE_DIR)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-only-change-me")

database_url = os.getenv("DATABASE_URL") or os.getenv("SQLALCHEMY_DATABASE_URI")
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql+psycopg://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"pool_pre_ping": True}

if not app.config["SQLALCHEMY_DATABASE_URI"]:
    raise RuntimeError("DATABASE_URL is required. Set it in .env or App Service configuration.")

if os.getenv("WEBSITE_HOSTNAME"):
    app.config["PREFERRED_URL_SCHEME"] = "https"

db = SQLAlchemy(app)

class Outfit(db.Model):
    __tablename__ = "outfits"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    category = db.Column(db.String(100), nullable=False, default="casual")
    image_url = db.Column(db.String(1024), nullable=True)
    product_link = db.Column(db.String(1024), nullable=True)
    source_store = db.Column(db.String(100), nullable=False, default="Trendyol")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


CATEGORIES = {"casual", "office", "evening", "streetwear", "sport"}


def upload_file_to_blob(file_storage):
    if not file_storage or not file_storage.filename:
        return None

    sas_url = os.getenv("AZURE_STORAGE_SAS_URL", "").strip()
    if not sas_url:
        return None

    filename = secure_filename(file_storage.filename)
    if not filename:
        return None

    extension = os.path.splitext(filename)[1]
    blob_name = f"outfits/{uuid4().hex}{extension}"
    content_type = file_storage.content_type or "application/octet-stream"

    try:
        container_client = ContainerClient.from_container_url(sas_url)
        blob_client = container_client.get_blob_client(blob_name)
        blob_client.upload_blob(
            file_storage.stream,
            overwrite=True,
            content_settings=ContentSettings(content_type=content_type),
        )
        # Build the read URL: <container_base_url>/<blob_name>?<sas_token>
        # sas_url format: https://<account>.blob.core.windows.net/<container>?<sas_token>
        if "?" in sas_url:
            container_base, sas_token = sas_url.split("?", 1)
            return f"{container_base}/{blob_name}?{sas_token}"
        return f"{sas_url}/{blob_name}"
    except Exception as exc:
        app.logger.exception("Blob upload failed: %s", exc)
        return None

@app.get("/health")
def health():
    try:
        db.session.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}, 200
    except SQLAlchemyError:
        return {"status": "degraded", "database": "unreachable"}, 503

@app.get("/test-blob")
def test_blob():
    """Diagnostic route — visit /test-blob to see exactly why uploads are failing."""
    import traceback
    sas_url = os.getenv("AZURE_STORAGE_SAS_URL", "").strip()
    if not sas_url:
        return {"status": "error", "reason": "AZURE_STORAGE_SAS_URL env var is not set"}, 500

    has_sip = "sip=" in sas_url
    try:
        container_client = ContainerClient.from_container_url(sas_url)
        # Try uploading a tiny test blob
        test_blob_name = "outfits/_connection_test.txt"
        blob_client = container_client.get_blob_client(test_blob_name)
        blob_client.upload_blob(b"ok", overwrite=True)
        blob_client.delete_blob()
        return {
            "status": "ok",
            "message": "Upload and delete succeeded. Azure Storage is working.",
            "sip_restriction_present": has_sip,
        }, 200
    except Exception as exc:
        return {
            "status": "error",
            "reason": str(exc),
            "sip_restriction_present": has_sip,
            "hint": "If reason contains 'AuthorizationFailure' or 'IP address', regenerate the SAS token without the 'Allowed IP addresses' field.",
            "trace": traceback.format_exc(),
        }, 500



@app.post("/init-db")
def init_db():
    try:
        db.create_all()
        return {"status": "ok", "message": "Database tables created."}, 200
    except SQLAlchemyError as exc:
        return {"status": "error", "message": str(exc)}, 500


@app.get("/")
def index():
    try:
        outfits = Outfit.query.order_by(Outfit.created_at.desc()).all()
        return render_template("index.html", outfits=outfits, db_error=None)
    except SQLAlchemyError:
        return render_template(
            "index.html",
            outfits=[],
            db_error="Database is unreachable. Check DATABASE_URL and network/firewall settings.",
        )

@app.get("/outfits/new")
def new_outfit_form():
    return render_template(
        "outfit_form.html",
        outfit=None,
        categories=sorted(CATEGORIES),
        form_action=url_for("create_outfit"),
        submit_label="Add Outfit",
    )


@app.post("/outfits")
def create_outfit():
    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip() or None
    category = request.form.get("category", "casual")
    image_url = request.form.get("image_url", "").strip() or None
    uploaded_image = request.files.get("image")
    product_link = request.form.get("product_link", "").strip() or None
    source_store = request.form.get("source_store", "Trendyol").strip() or "Trendyol"

    if not name:
        return "Outfit name is required", 400
    if category not in CATEGORIES:
        return "Invalid category", 400

    uploaded_url = upload_file_to_blob(uploaded_image)
    final_image_url = uploaded_url or image_url

    outfit = Outfit(
        name=name,
        description=description,
        category=category,
        image_url=final_image_url,
        product_link=product_link,
        source_store=source_store,
    )
    db.session.add(outfit)
    db.session.commit()
    return redirect(url_for("index"))


@app.get("/outfits/<int:outfit_id>/edit")
def edit_outfit_form(outfit_id: int):
    outfit = Outfit.query.get_or_404(outfit_id)
    return render_template(
        "outfit_form.html",
        outfit=outfit,
        categories=sorted(CATEGORIES),
        form_action=url_for("update_outfit", outfit_id=outfit.id),
        submit_label="Update Outfit",
    )


@app.post("/outfits/<int:outfit_id>")
def update_outfit(outfit_id: int):
    outfit = Outfit.query.get_or_404(outfit_id)
    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip() or None
    category = request.form.get("category", "casual")
    image_url = request.form.get("image_url", "").strip() or None
    uploaded_image = request.files.get("image")
    product_link = request.form.get("product_link", "").strip() or None
    source_store = request.form.get("source_store", "Trendyol").strip() or "Trendyol"

    if not name:
        return "Outfit name is required", 400
    if category not in CATEGORIES:
        return "Invalid category", 400

    uploaded_url = upload_file_to_blob(uploaded_image)
    final_image_url = uploaded_url or image_url or outfit.image_url

    outfit.name = name
    outfit.description = description
    outfit.category = category
    outfit.image_url = final_image_url
    outfit.product_link = product_link
    outfit.source_store = source_store

    db.session.commit()
    return redirect(url_for("index"))


@app.post("/outfits/<int:outfit_id>/delete")
def delete_outfit(outfit_id: int):
    outfit = Outfit.query.get_or_404(outfit_id)
    db.session.delete(outfit)
    db.session.commit()
    return redirect(url_for("index"))


with app.app_context():
    try:
        db.create_all()
    except SQLAlchemyError:
        pass

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=os.getenv("FLASK_DEBUG", "0") == "1")
