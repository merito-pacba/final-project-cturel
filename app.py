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

with app.app_context():
    db.create_all()


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

@app.route('/add', methods=['GET', 'POST'])
def add():
    if request.method == 'POST':
        outfit_name = request.form.get('content')
        if outfit_name:
            new_outfit = Task(name=outfit_name)
            db.session.add(new_outfit)
            db.session.commit()
            return redirect(url_for('index'))
    return render_template('add.html')

if __name__ == '__main__':
    app.run()
