import os
from datetime import datetime, timezone
from dotenv import load_dotenv
from flask import Flask, redirect, render_template, request, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

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

@app.get("/health")
def health():
    try:
        db.session.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}, 200
    except SQLAlchemyError:
        return {"status": "degraded", "database": "unreachable"}, 503

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
    product_link = request.form.get("product_link", "").strip() or None
    source_store = request.form.get("source_store", "Trendyol").strip() or "Trendyol"

    if not name:
        return "Outfit name is required", 400
    if category not in CATEGORIES:
        return "Invalid category", 400

    outfit = Outfit(
        name=name,
        description=description,
        category=category,
        image_url=image_url,
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
    product_link = request.form.get("product_link", "").strip() or None
    source_store = request.form.get("source_store", "Trendyol").strip() or "Trendyol"

    if not name:
        return "Outfit name is required", 400
    if category not in CATEGORIES:
        return "Invalid category", 400

    outfit.name = name
    outfit.description = description
    outfit.category = category
    outfit.image_url = image_url
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
