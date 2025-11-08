# debt_manager_flask_app.py
from flask import Flask, render_template_string, request, redirect, url_for, session, flash, g
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///debt_manager.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    name = db.Column(db.String(120), nullable=True)
    def check_password(self, pw):
        return check_password_hash(self.password_hash, pw)

class Debt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    employee_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    original_amount = db.Column(db.Float, nullable=False)
    start_date = db.Column(db.Date, default=datetime.utcnow)
    notes = db.Column(db.Text, nullable=True)
    employee = db.relationship('User')
    transactions = db.relationship('Transaction', backref='debt', cascade='all, delete-orphan')
    def outstanding(self):
        total = 0.0
        for t in self.transactions:
            if t.direction == 'Debit':
                total += t.amount
            else:
                total -= t.amount
        return total

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    debt_id = db.Column(db.Integer, db.ForeignKey('debt.id'), nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    amount = db.Column(db.Float, nullable=False)
    direction = db.Column(db.String(10), nullable=False)
    modified_by = db.Column(db.String(80))
    notes = db.Column(db.Text)

class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.Column(db.String(80))
    action = db.Column(db.String(120))
    details = db.Column(db.Text)

@app.before_request
def load_logged_in_user():
    g.user = None
    if 'user_id' in session:
        g.user = User.query.get(session['user_id'])

def audit(user, action, details):
    a = AuditLog(user=user, action=action, details=details)
    db.session.add(a)
    db.session.commit()

@app.route('/login', methods=['GET','POST'])
def login():
    template = "<h2>تسجيل الدخول</h2><form method=post><input name=username required><input name=password type=password required><button>دخول</button></form>"
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            session.clear()
            session['user_id'] = user.id
            audit(user.username, 'Login', f'User {user.username} logged in')
            return redirect(url_for('dashboard'))
        else:
            flash('بيانات الدخول غير صحيحة')
    return render_template_string(template)

@app.route('/logout')
def logout():
    if g.user:
        audit(g.user.username, 'Logout', f'User {g.user.username} logged out')
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if not g.user:
        return redirect(url_for('login'))
    users = User.query.filter(User.role=='employee').all()
    summary = []
    for u in users:
        user_debts = Debt.query.filter_by(employee_id=u.id).all()
        total_original = sum(d.original_amount for d in user_debts)
        total_outstanding = sum(d.outstanding() for d in user_debts)
        summary.append({'user': u, 'total_original': total_original, 'outstanding': total_outstanding, 'debts': user_debts})
    html = '<h1>لوحة المدير / الموظف</h1><a href=\"/logout\">تسجيل خروج</a><br/>'
    for s in summary:
        html += f"<div>{s['user'].name or s['user'].username} - إجمالي: {s['total_original']:.2f} - متبقي: {s['outstanding']:.2f}</div>"
    return html

@app.cli.command('initdb')
def initdb_command():
    db.drop_all()
    db.create_all()
    u1 = User(username='manager', password_hash=generate_password_hash('managerpass'), role='manager', name='المدير')
    u2 = User(username='emp1', password_hash=generate_password_hash('emp1pass'), role='employee', name='الموظف 1')
    u3 = User(username='emp2', password_hash=generate_password_hash('emp2pass'), role='employee', name='الموظف 2')
    db.session.add_all([u1,u2,u3])
    db.session.commit()
    print('Initialized the database and created default users.')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
