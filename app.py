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

# Azure Environment Variable'dan URL'i al
database_url = os.getenv('DATABASE_URL')
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)

with app.app_context():
    db.create_all()

@app.route('/')
def index():
    # Templates içinde 'outfits' ismini kullandığımız için burayı güncelledik
    all_outfits = Task.query.all()
    return render_template('index.html', outfits=all_outfits)

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
