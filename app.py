import os
from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Hard Requirement: Database configuration from environment variables
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Database Model for CRUD operations
class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.String(200), nullable=False)

@app.route('/')
def index():
    tasks = Task.query.all()
    return render_template('index.html', tasks=tasks)

if __name__ == '__main__':


with app.app_context():
    db.create_all()


@app.route('/add', methods=['POST'])
def add_task():
    content = request.form.get('content')
    new_task = Task(content=content)
    db.session.add(new_task)
    db.session.commit()
    return redirect(url_for('index'))