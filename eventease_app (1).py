#!/usr/bin/env python3
"""
=============================================================================
EventEase - College Event Registration & Check-In System
=============================================================================
Built for College Hackathons & Campus Events.
A complete, self-contained single-file Python web application with zero external
dependencies (uses standard Python 3: http.server, sqlite3, json, hashlib, etc.).

Default Accounts:
- Admin:   admin@collegename.edu   / admin123
- Student: student@collegename.edu / student123

To Run:
    python3 eventease_app.py
Then open http://127.0.0.1:8000 in your web browser.
=============================================================================
"""

import sys
import os
import sqlite3
import json
import uuid
import datetime
import urllib.parse
import hashlib
import csv
import io
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from http import cookies
from socketserver import ThreadingMixIn

DB_FILE = "eventease.db"
PORT = 8000
HOST = "127.0.0.1"

# -----------------------------------------------------------------------------
# Database Setup & Helper Functions
# -----------------------------------------------------------------------------

def get_db():
    global DB_FILE
    try:
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute('CREATE TABLE IF NOT EXISTS _fs_test (id INT);')
        conn.commit()
        return conn
    except sqlite3.OperationalError:
        DB_FILE = os.path.join('/tmp', 'eventease.db')
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def init_db():
    conn = get_db()
    cur = conn.cursor()
    
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'student',
        roll_number TEXT,
        created_at TEXT NOT NULL
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT,
        category TEXT NOT NULL,
        event_date TEXT NOT NULL,
        start_time TEXT NOT NULL,
        end_time TEXT,
        venue TEXT NOT NULL,
        capacity INTEGER DEFAULT 100,
        created_at TEXT NOT NULL
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS registrations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        qr_token TEXT UNIQUE NOT NULL,
        student_id INTEGER NOT NULL,
        event_id INTEGER NOT NULL,
        registered_at TEXT NOT NULL,
        checked_in INTEGER DEFAULT 0,
        checkin_time TEXT,
        FOREIGN KEY(student_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY(event_id) REFERENCES events(id) ON DELETE CASCADE
    );
    """)

    # Create default admin and student if not exists
    cur.execute("SELECT id FROM users WHERE email = ?", ("admin@collegename.edu",))
    if not cur.fetchone():
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cur.execute("""
        INSERT INTO users (name, email, password_hash, role, roll_number, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """, ("EventEase Admin", "admin@collegename.edu", hash_password("admin123"), "admin", "ADM-001", now))

    cur.execute("SELECT id FROM users WHERE email = ?", ("student@collegename.edu",))
    if not cur.fetchone():
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cur.execute("""
        INSERT INTO users (name, email, password_hash, role, roll_number, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """, ("Alex Johnson", "student@collegename.edu", hash_password("student123"), "student", "CS202601", now))

    conn.commit()
    conn.close()

def load_demo_data():
    conn = get_db()
    cur = conn.cursor()
    now_dt = datetime.datetime.now()
    now_str = now_dt.strftime("%Y-%m-%d %H:%M:%S")
    today_str = now_dt.strftime("%Y-%m-%d")

    # Clear existing events and student data (preserve default admin)
    cur.execute("DELETE FROM registrations")
    cur.execute("DELETE FROM events")
    cur.execute("DELETE FROM users WHERE role != 'admin'")

    # Sample students
    sample_students = [
        ("Alex Johnson", "student@collegename.edu", "CS202601", "student123"),
        ("Priya Sharma", "priya.sharma@collegename.edu", "CS202602", "student123"),
        ("Aarav Patel", "aarav.patel@collegename.edu", "IT202605", "student123"),
        ("Sneha Reddy", "sneha.reddy@collegename.edu", "EC202611", "student123"),
        ("Rohan Verma", "rohan.verma@collegename.edu", "ME202619", "student123"),
        ("Ananya Iyer", "ananya.iyer@collegename.edu", "CS202624", "student123"),
        ("Vikram Singh", "vikram.singh@collegename.edu", "IT202632", "student123"),
        ("Neha Gupta", "neha.gupta@collegename.edu", "EE202640", "student123"),
    ]

    student_ids = []
    for name, email, roll, pwd in sample_students:
        cur.execute("""
        INSERT INTO users (name, email, password_hash, role, roll_number, created_at)
        VALUES (?, ?, ?, 'student', ?, ?)
        """, (name, email, hash_password(pwd), roll, now_str))
        student_ids.append(cur.lastrowid)

    # Sample events
    sample_events = [
        (
            "HackIndia 2026: College AI Hackathon",
            "36-hour flagship annual hackathon bringing together students to solve real-world problems with generative AI and agentic systems.",
            "Hackathon",
            today_str,
            "09:00",
            "21:00",
            "Main Auditorium & Innovation Lab",
            150
        ),
        (
            "Generative AI & LLM Systems Workshop",
            "Hands-on workshop exploring prompt engineering, vector databases, and fine-tuning open-source models.",
            "Workshop",
            (now_dt + datetime.timedelta(days=2)).strftime("%Y-%m-%d"),
            "14:00",
            "17:30",
            "Computer Center Lab 4",
            60
        ),
        (
            "Campus Cultural Night: Symphony",
            "Annual musical night and cultural showcase featuring university student bands, solo vocalists, and choreography teams.",
            "Cultural",
            (now_dt + datetime.timedelta(days=5)).strftime("%Y-%m-%d"),
            "18:30",
            "22:00",
            "Open Air Amphitheatre",
            400
        ),
        (
            "National Tech Symposium & Paper Presentation",
            "Inter-college technical symposium featuring IEEE paper presentations, circuit debugging, and algorithmic speed coding.",
            "Technical",
            (now_dt + datetime.timedelta(days=8)).strftime("%Y-%m-%d"),
            "10:00",
            "16:00",
            "Seminar Hall Complex B",
            120
        ),
    ]

    event_ids = []
    for title, desc, cat, edate, stime, etime, venue, cap in sample_events:
        cur.execute("""
        INSERT INTO events (title, description, category, event_date, start_time, end_time, venue, capacity, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (title, desc, cat, edate, stime, etime, venue, cap, now_str))
        event_ids.append(cur.lastrowid)

    hackathon_id = event_ids[0]
    workshop_id = event_ids[1]
    cultural_id = event_ids[2]

    # Register all students for the Hackathon
    for i, s_id in enumerate(student_ids):
        tok = str(uuid.uuid4())
        checked_in = 1 if i < 5 else 0
        checkin_t = (now_dt - datetime.timedelta(minutes=(35 - i * 5))).strftime("%Y-%m-%d %H:%M:%S") if checked_in else None
        
        cur.execute("""
        INSERT INTO registrations (qr_token, student_id, event_id, registered_at, checked_in, checkin_time)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (tok, s_id, hackathon_id, now_str, checked_in, checkin_t))

    for s_id in student_ids[:4]:
        tok = str(uuid.uuid4())
        cur.execute("""
        INSERT INTO registrations (qr_token, student_id, event_id, registered_at, checked_in, checkin_time)
        VALUES (?, ?, ?, ?, 0, NULL)
        """, (tok, s_id, workshop_id, now_str))

    for s_id in student_ids[2:7]:
        tok = str(uuid.uuid4())
        cur.execute("""
        INSERT INTO registrations (qr_token, student_id, event_id, registered_at, checked_in, checkin_time)
        VALUES (?, ?, ?, ?, 0, NULL)
        """, (tok, s_id, cultural_id, now_str))

    conn.commit()
    conn.close()

def reset_all_data():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM registrations")
    cur.execute("DELETE FROM events")
    cur.execute("DELETE FROM users WHERE role != 'admin'")
    conn.commit()
    conn.close()

# -----------------------------------------------------------------------------
# In-Memory Session Management
# -----------------------------------------------------------------------------
SESSIONS = {}
QR_LOGIN_SESSIONS = {}  # { qr_token: { 'created_at': datetime, 'status': 'pending'|'authorized', 'user': dict } }

def create_session(user_data):
    session_id = str(uuid.uuid4())
    SESSIONS[session_id] = {
        "user_id": user_data["id"],
        "name": user_data["name"],
        "email": user_data["email"],
        "role": user_data["role"],
        "roll_number": user_data["roll_number"]
    }
    return session_id

def get_current_user(headers):
    cookie_header = headers.get("Cookie")
    if not cookie_header:
        return None
    c = cookies.SimpleCookie(cookie_header)
    if "session_id" not in c:
        return None
    session_id = c["session_id"].value
    return SESSIONS.get(session_id)

def render_tmpl(template_str, **kwargs):
    res = template_str
    for k, v in kwargs.items():
        res = res.replace("{{" + k + "}}", str(v))
    return res


BASE_CSS = """
:root {
    --primary: #4f46e5;
    --primary-hover: #4338ca;
    --primary-light: #eef2ff;
    --secondary: #6366f1;
    --bg-main: #f8fafc;
    --card-bg: #ffffff;
    --text-dark: #1e293b;
    --text-muted: #64748b;
    --border: #e2e8f0;
    --success: #10b981;
    --warning: #f59e0b;
    --danger: #ef4444;
    --info: #0284c7;
}

* {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
}

body {
    background-color: var(--bg-main);
    color: var(--text-dark);
    min-height: 100vh;
    display: flex;
    flex-direction: column;
}

/* Navbar */
.navbar {
    background-color: var(--primary);
    color: white;
    padding: 0.75rem 2rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    position: sticky;
    top: 0;
    z-index: 100;
}

.nav-brand {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    font-size: 1.35rem;
    font-weight: 700;
    color: white;
    text-decoration: none;
    letter-spacing: -0.5px;
}

.nav-links {
    display: flex;
    align-items: center;
    gap: 1.25rem;
    list-style: none;
}

.nav-link {
    color: #e0e7ff;
    text-decoration: none;
    font-weight: 500;
    font-size: 0.95rem;
    padding: 0.4rem 0.75rem;
    border-radius: 6px;
    transition: all 0.15s ease-in-out;
}

.nav-link:hover, .nav-link.active {
    background-color: rgba(255, 255, 255, 0.15);
    color: white;
}

.user-menu {
    position: relative;
    cursor: pointer;
}

.user-button {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    color: white;
    font-weight: 500;
    font-size: 0.95rem;
    background: none;
    border: none;
    cursor: pointer;
}

.dropdown-content {
    display: none;
    position: absolute;
    right: 0;
    top: 130%;
    background-color: white;
    min-width: 220px;
    box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1), 0 4px 6px -2px rgba(0,0,0,0.05);
    border-radius: 8px;
    overflow: hidden;
    border: 1px solid var(--border);
    z-index: 200;
}

.user-menu:hover .dropdown-content {
    display: block;
}

.dropdown-header {
    padding: 0.75rem 1rem;
    background-color: #f8fafc;
    border-bottom: 1px solid var(--border);
}

.dropdown-header .name {
    font-weight: 600;
    color: var(--text-dark);
    font-size: 0.9rem;
}

.dropdown-header .email {
    font-size: 0.8rem;
    color: var(--text-muted);
}

.dropdown-item {
    display: block;
    padding: 0.65rem 1rem;
    color: var(--text-dark);
    text-decoration: none;
    font-size: 0.9rem;
    transition: background 0.1s;
}

.dropdown-item:hover {
    background-color: #f1f5f9;
}

.dropdown-item.text-danger {
    color: var(--danger);
}

/* Layout */
.container {
    max-width: 1200px;
    margin: 2rem auto;
    padding: 0 1.5rem;
    flex: 1;
    width: 100%;
}

.page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1.5rem;
    flex-wrap: wrap;
    gap: 1rem;
}

.page-title {
    font-size: 1.6rem;
    font-weight: 700;
    color: #0f172a;
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

.page-subtitle {
    font-size: 0.9rem;
    color: var(--text-muted);
    margin-top: 0.25rem;
}

/* Flash alerts */
.alert {
    padding: 0.85rem 1.25rem;
    border-radius: 8px;
    margin-bottom: 1.5rem;
    font-size: 0.95rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.alert-success {
    background-color: #d1fae5;
    color: #065f46;
    border: 1px solid #a7f3d0;
}

.alert-warning {
    background-color: #fef3c7;
    color: #92400e;
    border: 1px solid #fde68a;
}

.alert-danger {
    background-color: #fee2e2;
    color: #991b1b;
    border: 1px solid #fecaca;
}

/* Buttons */
.btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    padding: 0.6rem 1.15rem;
    border-radius: 8px;
    font-weight: 500;
    font-size: 0.9rem;
    cursor: pointer;
    text-decoration: none;
    border: 1px solid transparent;
    transition: all 0.15s ease-in-out;
}

.btn-primary {
    background-color: var(--primary);
    color: white;
}

.btn-primary:hover {
    background-color: var(--primary-hover);
}

.btn-secondary {
    background-color: #6366f1;
    color: white;
}

.btn-secondary:hover {
    background-color: #4f46e5;
}

.btn-outline {
    background-color: transparent;
    border-color: var(--border);
    color: var(--text-dark);
}

.btn-outline:hover {
    background-color: #f1f5f9;
}

.btn-danger-outline {
    background-color: white;
    border-color: #fca5a5;
    color: var(--danger);
}

.btn-danger-outline:hover {
    background-color: #fee2e2;
}

.btn-sm {
    padding: 0.35rem 0.75rem;
    font-size: 0.825rem;
}

/* KPI Cards */
.stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
    gap: 1.25rem;
    margin-bottom: 2rem;
}

.stat-card {
    background: var(--card-bg);
    border-radius: 12px;
    padding: 1.35rem 1.5rem;
    border: 1px solid var(--border);
    display: flex;
    align-items: center;
    justify-content: space-between;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    transition: transform 0.15s, box-shadow 0.15s;
}

.stat-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 6px -1px rgba(0,0,0,0.08);
}

.stat-info .stat-value {
    font-size: 2rem;
    font-weight: 800;
    color: #0f172a;
    line-height: 1;
}

.stat-info .stat-label {
    font-size: 0.875rem;
    color: var(--text-muted);
    margin-top: 0.4rem;
    font-weight: 500;
}

.stat-icon {
    width: 48px;
    height: 48px;
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.4rem;
}

.icon-blue { background: #e0f2fe; color: #0284c7; }
.icon-orange { background: #fef3c7; color: #d97706; }
.icon-green { background: #d1fae5; color: #059669; }
.icon-purple { background: #ede9fe; color: #7c3aed; }

/* Dashboard 2-column Grid */
.dashboard-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1.5rem;
}

@media (max-width: 868px) {
    .dashboard-grid {
        grid-template-columns: 1fr;
    }
}

.panel {
    background: var(--card-bg);
    border-radius: 12px;
    border: 1px solid var(--border);
    box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    overflow: hidden;
}

.panel-header {
    padding: 1rem 1.25rem;
    border-bottom: 1px solid var(--border);
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.panel-title {
    font-size: 1.1rem;
    font-weight: 700;
    color: #1e293b;
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

.panel-body {
    padding: 1.25rem;
}

/* Empty State */
.empty-state {
    text-align: center;
    padding: 3rem 1.5rem;
    color: var(--text-muted);
}

.empty-icon {
    font-size: 2.8rem;
    margin-bottom: 0.75rem;
    opacity: 0.8;
}

.empty-title {
    font-size: 1.1rem;
    font-weight: 600;
    color: var(--text-dark);
    margin-bottom: 0.35rem;
}

.empty-desc {
    font-size: 0.875rem;
    margin-bottom: 1.25rem;
}

/* Tables */
.table-responsive {
    overflow-x: auto;
}

table {
    width: 100%;
    border-collapse: collapse;
    text-align: left;
    font-size: 0.9rem;
}

th {
    background-color: #f8fafc;
    color: var(--text-muted);
    font-weight: 600;
    padding: 0.75rem 1rem;
    border-bottom: 1px solid var(--border);
    text-transform: uppercase;
    font-size: 0.75rem;
    letter-spacing: 0.5px;
}

td {
    padding: 0.85rem 1rem;
    border-bottom: 1px solid var(--border);
    color: var(--text-dark);
}

tr:hover td {
    background-color: #f8fafc;
}

/* Badges */
.badge {
    display: inline-block;
    padding: 0.25rem 0.55rem;
    border-radius: 9999px;
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
}

.badge-success { background: #d1fae5; color: #065f46; }
.badge-warning { background: #fef3c7; color: #92400e; }
.badge-danger { background: #fee2e2; color: #991b1b; }
.badge-primary { background: #e0e7ff; color: #3730a3; }
.badge-secondary { background: #f1f5f9; color: #475569; }

/* Forms */
.form-group {
    margin-bottom: 1.15rem;
}

.form-label {
    display: block;
    font-size: 0.875rem;
    font-weight: 600;
    color: #334155;
    margin-bottom: 0.4rem;
}

.form-control {
    width: 100%;
    padding: 0.65rem 0.9rem;
    border-radius: 8px;
    border: 1px solid var(--border);
    font-size: 0.95rem;
    color: var(--text-dark);
    outline: none;
    transition: border-color 0.15s;
}

.form-control:focus {
    border-color: var(--primary);
    box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.15);
}

/* Modals */
.modal-overlay {
    display: none;
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background-color: rgba(15, 23, 42, 0.5);
    z-index: 1000;
    align-items: center;
    justify-content: center;
    backdrop-filter: blur(2px);
}

.modal-card {
    background: white;
    border-radius: 12px;
    max-width: 550px;
    width: 90%;
    max-height: 90vh;
    overflow-y: auto;
    box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1);
}

.modal-header {
    padding: 1.25rem 1.5rem;
    border-bottom: 1px solid var(--border);
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.modal-title {
    font-size: 1.2rem;
    font-weight: 700;
    color: #0f172a;
}

.modal-close {
    background: none;
    border: none;
    font-size: 1.4rem;
    cursor: pointer;
    color: var(--text-muted);
}

.modal-body {
    padding: 1.5rem;
}

.modal-footer {
    padding: 1rem 1.5rem;
    background-color: #f8fafc;
    border-top: 1px solid var(--border);
    display: flex;
    justify-content: flex-end;
    gap: 0.75rem;
}

/* Footer */
footer {
    text-align: center;
    padding: 1.5rem 0;
    color: var(--text-muted);
    font-size: 0.85rem;
    border-top: 1px solid var(--border);
    background: white;
    margin-top: auto;
}
"""


def render_navbar(user, active_tab=""):
    if not user:
        return """
        <nav class="navbar">
            <a href="/login" class="nav-brand">
                <span>🎫 EventEase</span>
            </a>
            <div class="nav-links">
                <a href="/login" class="btn btn-outline" style="color:white; border-color:rgba(255,255,255,0.4)">Sign In</a>
            </div>
        </nav>
        """

    is_admin = (user.get("role") == "admin")
    
    if is_admin:
        act_dash = 'active' if active_tab=='dashboard' else ''
        act_ev = 'active' if active_tab=='events' else ''
        act_st = 'active' if active_tab=='students' else ''
        act_rg = 'active' if active_tab=='registrations' else ''
        act_ck = 'active' if active_tab=='check-in' else ''
        act_at = 'active' if active_tab=='attendance' else ''

        links = f"""
        <li><a href="/admin/dashboard" class="nav-link {act_dash}">📊 Dashboard</a></li>
        <li><a href="/admin/events" class="nav-link {act_ev}">📅 Events</a></li>
        <li><a href="/admin/students" class="nav-link {act_st}">👥 Students</a></li>
        <li><a href="/admin/registrations" class="nav-link {act_rg}">📋 Registrations</a></li>
        <li><a href="/admin/check-in" class="nav-link {act_ck}">📷 Check-In</a></li>
        <li><a href="/admin/attendance" class="nav-link {act_at}">📈 Attendance</a></li>
        """
    else:
        act_br = 'active' if active_tab=='browse' else ''
        act_tk = 'active' if active_tab=='my-tickets' else ''
        links = f"""
        <li><a href="/student/events" class="nav-link {act_br}">📅 Explore Events</a></li>
        <li><a href="/student/my-tickets" class="nav-link {act_tk}">🎟️ My Passes</a></li>
        """

    badge_role = 'badge-primary' if is_admin else 'badge-secondary'
    home_url = '/' if is_admin else '/student/events'

    return f"""
    <nav class="navbar">
        <a href="{home_url}" class="nav-brand">
            <span>🎫 EventEase</span>
        </a>
        <ul class="nav-links">
            {links}
        </ul>
        <div class="user-menu">
            <button class="user-button">
                <span>👤 {user['name']} ▾</span>
            </button>
            <div class="dropdown-content">
                <div class="dropdown-header">
                    <div class="name">{user['name']}</div>
                    <div class="email">{user['email']}</div>
                    <div class="role"><span class="badge {badge_role}">{user['role'].capitalize()}</span></div>
                </div>
                <a href="/logout" class="dropdown-item text-danger">🚪 Logout</a>
            </div>
        </div>
    </nav>
    """

def page_layout(title, content, user=None, active_tab="", flash_msg=None, flash_type="success"):
    flash_html = ""
    if flash_msg:
        flash_html = f"""
        <div class="alert alert-{flash_type}">
            <span>{flash_msg}</span>
            <span style="cursor:pointer;" onclick="this.parentElement.remove()">✕</span>
        </div>
        """

    navbar_html = render_navbar(user, active_tab)

    template = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{TITLE}} | EventEase</title>
    <style>{{BASE_CSS}}</style>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js"></script>
    <script src="https://unpkg.com/html5-qrcode@2.3.8/html5-qrcode.min.js"></script>
</head>
<body>
    {{NAVBAR}}
    <div class="container">
        {{FLASH}}
        {{CONTENT}}
    </div>
    <footer>
        © 2026 EventEase - Built for College Hackathon
    </footer>
</body>
</html>
"""
    return render_tmpl(template, TITLE=title, BASE_CSS=BASE_CSS, NAVBAR=navbar_html, FLASH=flash_html, CONTENT=content)



def render_mobile_qr_auth(qr_token, students, flash_msg=None):
    flash_html = f'<div class="alert alert-danger" style="margin-bottom:1rem">{flash_msg}</div>' if flash_msg else ""
    student_options = ""
    for s in students:
        roll_txt = f" ({s['roll_number']})" if s['roll_number'] else ""
        student_options += f'<option value="{s["email"]}">{s["name"]}{roll_txt} - {s["email"]}</option>'

    template = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Mobile QR Login | EventEase</title>
    <style>
        {{BASE_CSS}}
        body {
            display: flex;
            align-items: center;
            justify-content: center;
            background-color: #f1f5f9;
            padding: 1rem;
            min-height: 100vh;
        }
        .auth-container {
            max-width: 440px;
            width: 100%;
        }
        .auth-card {
            background: white;
            border-radius: 16px;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.1);
            overflow: hidden;
            border: 1px solid var(--border);
        }
        .auth-banner {
            background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);
            color: white;
            padding: 1.75rem 1.5rem;
            text-align: center;
        }
        .auth-body {
            padding: 1.75rem;
        }
    </style>
</head>
<body>
    <div class="auth-container">
        {{FLASH}}
        <div class="auth-card">
            <div class="auth-banner">
                <h1 style="font-size:1.6rem; font-weight:800;">EventEase</h1>
                <p style="font-size:0.9rem; opacity:0.95;">📱 Mobile QR Quick Login</p>
            </div>
            <div class="auth-body">
                <div style="text-align:center; margin-bottom:1.25rem;">
                    <div style="font-size:2.8rem; margin-bottom:0.25rem;">✅</div>
                    <h2 style="font-size:1.25rem; font-weight:700; color:#1e293b;">Scan Verified!</h2>
                    <p style="font-size:0.85rem; color:var(--text-muted); margin-top:0.25rem;">
                        Authorize your session to access the student dashboard and event passes.
                    </p>
                </div>

                <form method="POST" action="/qr-login">
                    <input type="hidden" name="token" value="{{QR_TOKEN}}">
                    <div class="form-group">
                        <label class="form-label">Select Your Student Profile</label>
                        <select name="student_email" class="form-control" style="font-size:0.95rem; padding:0.65rem;" required>
                            {{STUDENT_OPTIONS}}
                        </select>
                    </div>
                    <button type="submit" class="btn btn-primary" style="width:100%; padding:0.8rem; font-size:1rem; font-weight:600;">
                        ➔ Authorize & Open Dashboard
                    </button>
                </form>

                <div style="text-align:center; margin-top:1.25rem; font-size:0.8rem; color:var(--text-muted);">
                    If you scanned a kiosk or desktop screen, it will also log in automatically.
                </div>
            </div>
        </div>
    </div>
</body>
</html>
"""
    return render_tmpl(template, BASE_CSS=BASE_CSS, FLASH=flash_html, QR_TOKEN=qr_token, STUDENT_OPTIONS=student_options)


def render_login(flash_msg=None, flash_type="success", qr_token=""):
    flash_html = f'<div class="alert alert-{flash_type}" style="margin-bottom:1rem">{flash_msg}</div>' if flash_msg else ""
    template = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login | EventEase</title>
    <style>
        {{BASE_CSS}}
        body {
            display: flex;
            align-items: center;
            justify-content: center;
            background-color: #f1f5f9;
            min-height: 100vh;
            padding: 1.5rem 1rem;
        }
        .auth-container {
            max-width: 980px;
            width: 100%;
            margin: 1.5rem auto;
        }
        .auth-card {
            background: white;
            border-radius: 16px;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1);
            overflow: hidden;
            border: 1px solid var(--border);
        }
        .auth-banner {
            background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);
            color: white;
            padding: 2rem 2rem;
            text-align: center;
        }
        .auth-banner h1 {
            font-size: 2rem;
            font-weight: 800;
            letter-spacing: -0.5px;
        }
        .auth-banner p {
            font-size: 0.95rem;
            opacity: 0.92;
            margin-top: 0.35rem;
        }
        .banner-tags {
            display: flex;
            justify-content: center;
            gap: 0.75rem;
            margin-top: 0.85rem;
            flex-wrap: wrap;
        }
        .banner-tag {
            background: rgba(255, 255, 255, 0.18);
            backdrop-filter: blur(4px);
            padding: 0.35rem 0.85rem;
            border-radius: 9999px;
            font-size: 0.8rem;
            font-weight: 600;
            color: #ffffff;
            border: 1px solid rgba(255, 255, 255, 0.25);
        }
        .auth-dual-grid {
            display: grid;
            grid-template-columns: 1fr auto 1fr;
            background: white;
        }
        @media (max-width: 820px) {
            .auth-dual-grid {
                grid-template-columns: 1fr;
            }
            .auth-divider {
                flex-direction: row !important;
                padding: 1.5rem 2rem !important;
            }
            .auth-divider::before, .auth-divider::after {
                height: 1px !important;
                width: 100% !important;
            }
        }
        .auth-col {
            padding: 2.2rem 2rem;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }
        .auth-divider {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 2rem 0;
            background: #ffffff;
        }
        .auth-divider::before, .auth-divider::after {
            content: '';
            background: var(--border);
            width: 1px;
            flex: 1;
        }
        .auth-divider span {
            background: #f1f5f9;
            border: 1px solid var(--border);
            color: var(--text-muted);
            font-size: 0.75rem;
            font-weight: 700;
            padding: 0.4rem 0.65rem;
            border-radius: 50%;
            margin: 0.75rem 0;
            text-transform: uppercase;
            box-shadow: 0 1px 2px rgba(0,0,0,0.05);
        }
        .auth-title {
            font-size: 1.35rem;
            font-weight: 700;
            color: #1e293b;
            margin-bottom: 0.25rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        .auth-subtitle {
            font-size: 0.85rem;
            color: var(--text-muted);
            margin-bottom: 1.5rem;
        }
        .qr-card-box {
            text-align: center;
            background: #f8fafc;
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 1.5rem 1rem;
            margin-bottom: 1.25rem;
        }
        .qr-frame {
            display: inline-block;
            background: white;
            padding: 12px;
            border-radius: 12px;
            border: 2px solid #e2e8f0;
            box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);
            position: relative;
        }
        .qr-frame img {
            width: 190px;
            height: 190px;
            display: block;
            border-radius: 6px;
        }
        .status-pill {
            display: inline-flex;
            align-items: center;
            gap: 0.45rem;
            background: #ecfdf5;
            color: #065f46;
            border: 1px solid #a7f3d0;
            padding: 0.35rem 0.8rem;
            border-radius: 9999px;
            font-size: 0.8rem;
            font-weight: 600;
            margin-top: 1rem;
        }
        .pulse-dot {
            width: 8px;
            height: 8px;
            background-color: #10b981;
            border-radius: 50%;
            display: inline-block;
            box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7);
            animation: pulse 1.8s infinite;
        }
        @keyframes pulse {
            0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); }
            70% { transform: scale(1); box-shadow: 0 0 0 6px rgba(16, 185, 129, 0); }
            100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
        }
        .steps-box {
            background: #ffffff;
            border-radius: 8px;
            border: 1px solid var(--border);
            padding: 0.85rem 1rem;
            text-align: left;
            font-size: 0.825rem;
            color: #475569;
            line-height: 1.5;
            margin-top: 1rem;
        }
        .steps-box .step-item {
            display: flex;
            gap: 0.5rem;
            align-items: flex-start;
            margin-bottom: 0.35rem;
        }
        .steps-box .step-num {
            background: var(--primary-light);
            color: var(--primary);
            font-weight: 700;
            font-size: 0.75rem;
            width: 18px;
            height: 18px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
            margin-top: 1px;
        }
        .demo-badge {
            background: #eff6ff;
            border: 1px dashed #93c5fd;
            border-radius: 8px;
            padding: 0.75rem;
            font-size: 0.825rem;
            color: #1e40af;
            text-align: center;
            margin-top: 1rem;
            cursor: pointer;
            transition: all 0.15s;
        }
        .demo-badge:hover {
            background: #dbeafe;
        }
    </style>
    <script src="https://unpkg.com/html5-qrcode@2.3.8/html5-qrcode.min.js"></script>
</head>
<body>
    <div class="auth-container">
        {{FLASH}}
        <div class="auth-card">
            <div class="auth-banner">
                <h1>EventEase</h1>
                <p>College Event Registration & Student Check-In Portal</p>
                <div class="banner-tags">
                    <span class="banner-tag">📱 Mobile QR Fast Login</span>
                    <span class="banner-tag">💻 Manual Registration & Login</span>
                    <span class="banner-tag">🎫 Digital Passes</span>
                </div>
            </div>

            <div class="auth-dual-grid">
                <!-- LEFT COLUMN: QR CODE LOGIN -->
                <div class="auth-col" style="background: #fafcff; border-right: 1px solid #f1f5f9;">
                    <div>
                        <h2 class="auth-title">
                            <span>📱</span> Quick QR Login
                        </h2>
                        <div class="auth-subtitle">
                            For students with a mobile phone — scan and enter dashboard instantly
                        </div>

                        <div class="qr-card-box">
                            <div class="qr-frame">
                                <img src="/static/login_qr.png" alt="Scan QR to Login" id="qrImg">
                            </div>

                            <div>
                                <div class="status-pill" id="qrStatusPill">
                                    <span class="pulse-dot"></span>
                                    <span id="qrStatusText">Ready for Mobile Scan</span>
                                </div>
                            </div>

                            <div class="steps-box">
                                <div style="font-weight:700; color:#1e293b; margin-bottom:0.4rem;">How to login with your mobile:</div>
                                <div class="step-item">
                                    <span class="step-num">1</span>
                                    <span>Open your mobile camera or QR code scanner app.</span>
                                </div>
                                <div class="step-item">
                                    <span class="step-num">2</span>
                                    <span>Scan this QR code to authenticate instantly.</span>
                                </div>
                                <div class="step-item" style="margin-bottom:0;">
                                    <span class="step-num">3</span>
                                    <span>You will be automatically redirected to your dashboard!</span>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div>
                        <div style="display:flex; flex-direction:column; gap:0.5rem; margin-top:0.5rem;">
                            <button type="button" class="btn btn-secondary" onclick="simulateQrLogin()" style="width:100%; font-weight:600;">
                                ⚡ Simulate Mobile QR Scan (Instant Login)
                            </button>
                            <button type="button" class="btn btn-outline btn-sm" onclick="toggleWebcamScanner()" id="webcamBtn" style="width:100%;">
                                📷 Scan Student Ticket/Badge with Webcam
                            </button>
                        </div>

                        <div id="webcamBox" style="display:none; margin-top:1rem; padding:0.75rem; background:#ffffff; border:1px dashed var(--border); border-radius:8px; text-align:center;">
                            <div id="webcamReader" style="width:100%; max-width:240px; margin:0 auto;"></div>
                            <div style="font-size:0.75rem; color:var(--text-muted); margin-top:0.35rem;">Hold student pass QR up to camera</div>
                            <button type="button" class="btn btn-danger-outline btn-sm" style="margin-top:0.5rem;" onclick="stopWebcamScanner()">Cancel Scanner</button>
                        </div>
                    </div>
                </div>

                <!-- MIDDLE DIVIDER -->
                <div class="auth-divider">
                    <span>OR</span>
                </div>

                <!-- RIGHT COLUMN: MANUAL SIGN IN (as shown in image) -->
                <div class="auth-col">
                    <div>
                        <h2 class="auth-title">
                            <span>✍️</span> Manual Sign In
                        </h2>
                        <div class="auth-subtitle">
                            For students without mobile phones & event administrators
                        </div>

                        <form method="POST" action="/login">
                            <div class="form-group">
                                <label class="form-label">Email Address</label>
                                <input type="email" name="email" id="loginEmail" class="form-control" placeholder="you@collegename.edu" required>
                            </div>
                            <div class="form-group">
                                <label class="form-label">Password</label>
                                <input type="password" name="password" id="loginPassword" class="form-control" placeholder="••••••••" required>
                            </div>
                            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:1.25rem;">
                                <label style="font-size:0.85rem; display:flex; align-items:center; gap:0.4rem; color:var(--text-muted); cursor:pointer;">
                                    <input type="checkbox" name="remember" checked> Remember me
                                </label>
                            </div>
                            <button type="submit" class="btn btn-primary" style="width:100%; padding:0.75rem; font-size:1rem;">➔ Login</button>
                        </form>

                        <div style="text-align:center; margin-top:1.25rem; font-size:0.875rem;">
                            New student without phone? <a href="/register" style="color:var(--primary); font-weight:600; text-decoration:none;">Create an account</a>
                        </div>
                    </div>

                    <div>
                        <div class="demo-badge" onclick="fillAdmin()">
                            ℹ️ <strong>Admin Demo:</strong> admin@collegename.edu / admin123 (click to autofill)
                        </div>
                        <div class="demo-badge" style="margin-top:0.5rem; background:#f0fdf4; border-color:#86efac; color:#166534;" onclick="fillStudent()">
                            🎓 <strong>Student Demo:</strong> student@collegename.edu / student123 (click to autofill)
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        const qrSessionToken = "{{QR_TOKEN}}";
        let pollTimer = null;
        let html5Qr = null;

        function fillAdmin() {
            document.getElementById('loginEmail').value = 'admin@collegename.edu';
            document.getElementById('loginPassword').value = 'admin123';
        }
        function fillStudent() {
            document.getElementById('loginEmail').value = 'student@collegename.edu';
            document.getElementById('loginPassword').value = 'student123';
        }

        function startPolling() {
            if (!qrSessionToken) return;
            pollTimer = setInterval(async () => {
                try {
                    const res = await fetch('/api/qr-poll?token=' + encodeURIComponent(qrSessionToken));
                    const data = await res.json();
                    if (data.status === 'authorized') {
                        clearInterval(pollTimer);
                        document.getElementById('qrStatusText').innerHTML = '✅ Authorized! Redirecting...';
                        document.getElementById('qrStatusPill').style.background = '#d1fae5';
                        document.getElementById('qrStatusPill').style.color = '#065f46';
                        setTimeout(() => {
                            window.location.href = data.redirect || '/student/events';
                        }, 500);
                    }
                } catch (e) {}
            }, 1500);
        }
        startPolling();

        async function simulateQrLogin() {
            const statusText = document.getElementById('qrStatusText');
            statusText.innerText = '⚡ Connecting to mobile scan...';
            try {
                const res = await fetch('/api/qr-simulate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ token: qrSessionToken })
                });
                const data = await res.json();
                if (data.status === 'ok') {
                    statusText.innerText = '✅ Verified! Redirecting to student dashboard...';
                    setTimeout(() => {
                        window.location.href = data.redirect || '/student/events';
                    }, 500);
                } else {
                    statusText.innerText = 'Scan error. Please try again.';
                }
            } catch (err) {
                statusText.innerText = 'Error: ' + err.message;
            }
        }

        function toggleWebcamScanner() {
            const box = document.getElementById('webcamBox');
            if (box.style.display === 'none') {
                box.style.display = 'block';
                if (!html5Qr) {
                    html5Qr = new Html5Qrcode("webcamReader");
                }
                html5Qr.start(
                    { facingMode: "user" },
                    { fps: 10, qrbox: { width: 180, height: 180 } },
                    async (decodedText) => {
                        html5Qr.stop();
                        box.style.display = 'none';
                        const res = await fetch('/api/qr-badge-login', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ query: decodedText, token: qrSessionToken })
                        });
                        const data = await res.json();
                        if (data.status === 'success') {
                            window.location.href = data.redirect || '/student/events';
                        } else {
                            alert("Invalid pass/badge: " + (data.message || "Student not found"));
                        }
                    },
                    (err) => {}
                ).catch(err => {
                    alert("Camera error: " + err);
                    box.style.display = 'none';
                });
            } else {
                stopWebcamScanner();
            }
        }

        function stopWebcamScanner() {
            if (html5Qr) {
                html5Qr.stop().then(() => {
                    document.getElementById('webcamBox').style.display = 'none';
                }).catch(() => {
                    document.getElementById('webcamBox').style.display = 'none';
                });
            } else {
                document.getElementById('webcamBox').style.display = 'none';
            }
        }
    </script>
</body>
</html>
"""
    return render_tmpl(template, BASE_CSS=BASE_CSS, FLASH=flash_html, QR_TOKEN=qr_token)


def render_register(flash_msg=None, flash_type="danger"):
    flash_html = f'<div class="alert alert-{flash_type}" style="margin-bottom:1rem">{flash_msg}</div>' if flash_msg else ""
    template = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Student Registration | EventEase</title>
    <style>
        {{BASE_CSS}}
        body {
            display: flex;
            align-items: center;
            justify-content: center;
            background-color: #f1f5f9;
        }
        .auth-container {
            max-width: 460px;
            width: 100%;
            margin: 2rem 1rem;
        }
        .auth-card {
            background: white;
            border-radius: 16px;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.1);
            overflow: hidden;
            border: 1px solid var(--border);
        }
        .auth-banner {
            background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);
            color: white;
            padding: 2rem;
            text-align: center;
        }
        .auth-body {
            padding: 2rem;
        }
    </style>
</head>
<body>
    <div class="auth-container">
        {{FLASH}}
        <div class="auth-card">
            <div class="auth-banner">
                <h1 style="font-size:1.6rem; font-weight:800;">EventEase</h1>
                <p style="font-size:0.9rem; opacity:0.9;">Student Account Registration</p>
            </div>
            <div class="auth-body">
                <h2 style="text-align:center; font-size:1.3rem; margin-bottom:1.25rem;">Create Account</h2>
                <form method="POST" action="/register">
                    <div class="form-group">
                        <label class="form-label">Full Name</label>
                        <input type="text" name="name" class="form-control" placeholder="e.g. John Doe" required>
                    </div>
                    <div class="form-group">
                        <label class="form-label">Roll Number / Student ID</label>
                        <input type="text" name="roll_number" class="form-control" placeholder="e.g. CS202615" required>
                    </div>
                    <div class="form-group">
                        <label class="form-label">College Email</label>
                        <input type="email" name="email" class="form-control" placeholder="you@collegename.edu" required>
                    </div>
                    <div class="form-group">
                        <label class="form-label">Password</label>
                        <input type="password" name="password" class="form-control" placeholder="••••••••" required>
                    </div>
                    <button type="submit" class="btn btn-primary" style="width:100%; padding:0.75rem; font-size:0.95rem;">Register Now</button>
                </form>
                <div style="text-align:center; margin-top:1.25rem; font-size:0.875rem;">
                    Already have an account? <a href="/login" style="color:var(--primary); font-weight:600; text-decoration:none;">Sign In</a>
                </div>
            </div>
        </div>
    </div>
</body>
</html>
"""
    return render_tmpl(template, BASE_CSS=BASE_CSS, FLASH=flash_html)


def render_create_event_modal():
    return """
    <div id="eventModal" class="modal-overlay">
        <div class="modal-card">
            <div class="modal-header">
                <h3 class="modal-title">Create New College Event</h3>
                <button class="modal-close" onclick="closeEventModal()">✕</button>
            </div>
            <form method="POST" action="/admin/events/create">
                <div class="modal-body">
                    <div class="form-group">
                        <label class="form-label">Event Title</label>
                        <input type="text" name="title" class="form-control" placeholder="e.g. Annual Hackathon 2026" required>
                    </div>
                    <div class="form-group">
                        <label class="form-label">Category</label>
                        <select name="category" class="form-control" required>
                            <option value="Hackathon">Hackathon</option>
                            <option value="Technical">Technical</option>
                            <option value="Workshop">Workshop</option>
                            <option value="Cultural">Cultural</option>
                            <option value="Sports">Sports</option>
                            <option value="Seminar">Seminar</option>
                        </select>
                    </div>
                    <div style="display:grid; grid-template-columns:1fr 1fr; gap:1rem;">
                        <div class="form-group">
                            <label class="form-label">Date</label>
                            <input type="date" name="event_date" class="form-control" required>
                        </div>
                        <div class="form-group">
                            <label class="form-label">Start Time</label>
                            <input type="time" name="start_time" class="form-control" required>
                        </div>
                    </div>
                    <div style="display:grid; grid-template-columns:2fr 1fr; gap:1rem;">
                        <div class="form-group">
                            <label class="form-label">Venue / Room</label>
                            <input type="text" name="venue" class="form-control" placeholder="e.g. Auditorium Hall A" required>
                        </div>
                        <div class="form-group">
                            <label class="form-label">Max Seats</label>
                            <input type="number" name="capacity" class="form-control" value="100" min="10" required>
                        </div>
                    </div>
                    <div class="form-group">
                        <label class="form-label">Description</label>
                        <textarea name="description" class="form-control" rows="3" placeholder="Brief event description and guidelines..."></textarea>
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-outline" onclick="closeEventModal()">Cancel</button>
                    <button type="submit" class="btn btn-primary">+ Save & Publish Event</button>
                </div>
            </form>
        </div>
    </div>
    """

def render_admin_dashboard(user, flash_msg=None):
    conn = get_db()
    cur = conn.cursor()

    total_events = cur.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    total_registrations = cur.execute("SELECT COUNT(*) FROM registrations").fetchone()[0]
    total_students = cur.execute("SELECT COUNT(*) FROM users WHERE role = 'student'").fetchone()[0]
    
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
    checkins_today = cur.execute("""
        SELECT COUNT(*) FROM registrations 
        WHERE checked_in = 1 AND checkin_time LIKE ?
    """, (f"{today_str}%",)).fetchone()[0]

    events = cur.execute("""
        SELECT e.*, COUNT(r.id) as reg_count 
        FROM events e 
        LEFT JOIN registrations r ON e.id = r.event_id 
        GROUP BY e.id 
        ORDER BY e.event_date ASC 
        LIMIT 5
    """).fetchall()

    recent_regs = cur.execute("""
        SELECT r.id, r.registered_at, r.checked_in, u.name as student_name, u.roll_number, e.title as event_title
        FROM registrations r
        JOIN users u ON r.student_id = u.id
        JOIN events e ON r.event_id = e.id
        ORDER BY r.id DESC
        LIMIT 6
    """).fetchall()
    conn.close()

    if events:
        events_html = '<div style="display:flex; flex-direction:column; gap:0.75rem;">'
        for ev in events:
            events_html += f"""
            <div style="border:1px solid var(--border); border-radius:8px; padding:0.85rem 1rem; display:flex; justify-content:space-between; align-items:center;">
                <div>
                    <div style="font-weight:600; color:#0f172a;">{ev['title']}</div>
                    <div style="font-size:0.8rem; color:var(--text-muted); margin-top:0.2rem;">
                        📅 {ev['event_date']} at {ev['start_time']} • 📍 {ev['venue']}
                    </div>
                </div>
                <div style="text-align:right;">
                    <span class="badge badge-primary">{ev['reg_count']} / {ev['capacity']} Regs</span>
                </div>
            </div>
            """
        events_html += '</div>'
    else:
        events_html = """
        <div class="empty-state">
            <div class="empty-icon">📅</div>
            <div class="empty-title">No upcoming events.</div>
            <div class="empty-desc">Create your first event to kickstart registrations.</div>
            <button class="btn btn-primary btn-sm" onclick="openEventModal()">+ Create Event</button>
        </div>
        """

    if recent_regs:
        regs_html = """
        <div class="table-responsive">
            <table>
                <thead>
                    <tr>
                        <th>Student</th>
                        <th>Event</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
        """
        for r in recent_regs:
            status_badge = '<span class="badge badge-success">Checked-In</span>' if r['checked_in'] else '<span class="badge badge-warning">Registered</span>'
            regs_html += f"""
            <tr>
                <td>
                    <div style="font-weight:600;">{r['student_name']}</div>
                    <div style="font-size:0.75rem; color:var(--text-muted);">{r['roll_number']}</div>
                </td>
                <td>{r['event_title']}</td>
                <td>{status_badge}</td>
            </tr>
            """
        regs_html += "</tbody></table></div>"
    else:
        regs_html = """
        <div class="empty-state">
            <div class="empty-icon">📋</div>
            <div class="empty-title">No registrations yet.</div>
            <div class="empty-desc">Student event signups will appear here in real time.</div>
        </div>
        """

    modal_html = render_create_event_modal()

    content = f"""
    <div class="page-header">
        <div>
            <h1 class="page-title">Admin Dashboard</h1>
            <div class="page-subtitle">Overview of EventEase platform activity</div>
        </div>
        <div style="display:flex; gap:0.75rem;">
            <button class="btn btn-secondary" onclick="loadDemoData()">
                ⚡ Load Demo Data (Judges Quick Start)
            </button>
            <button class="btn btn-danger-outline" onclick="resetAllData()">
                🔄 Reset All Data
            </button>
        </div>
    </div>

    <!-- 4 KPI Cards -->
    <div class="stats-grid">
        <div class="stat-card">
            <div class="stat-info">
                <div class="stat-value">{total_events}</div>
                <div class="stat-label">Total Events</div>
            </div>
            <div class="stat-icon icon-blue">📅</div>
        </div>
        <div class="stat-card">
            <div class="stat-info">
                <div class="stat-value">{total_registrations}</div>
                <div class="stat-label">Registrations</div>
            </div>
            <div class="stat-icon icon-orange">📋</div>
        </div>
        <div class="stat-card">
            <div class="stat-info">
                <div class="stat-value">{total_students}</div>
                <div class="stat-label">Students</div>
            </div>
            <div class="stat-icon icon-purple">👥</div>
        </div>
        <div class="stat-card">
            <div class="stat-info">
                <div class="stat-value">{checkins_today}</div>
                <div class="stat-label">Check-ins Today</div>
            </div>
            <div class="stat-icon icon-green">✅</div>
        </div>
    </div>

    <!-- 2 Column Dashboard Panels -->
    <div class="dashboard-grid">
        <div class="panel">
            <div class="panel-header">
                <div class="panel-title">📅 Upcoming Events</div>
                <div style="display:flex; gap:0.5rem;">
                    <button class="btn btn-primary btn-sm" onclick="openEventModal()">+ New Event</button>
                    <a href="/admin/events" class="btn btn-outline btn-sm">All</a>
                </div>
            </div>
            <div class="panel-body">
                {events_html}
            </div>
        </div>

        <div class="panel">
            <div class="panel-header">
                <div class="panel-title">📋 Recent Registrations</div>
                <a href="/admin/registrations" class="btn btn-outline btn-sm">All ➔</a>
            </div>
            <div class="panel-body">
                {regs_html}
            </div>
        </div>
    </div>

    {modal_html}

    <script>
        function openEventModal() {{
            document.getElementById('eventModal').style.display = 'flex';
        }}
        function closeEventModal() {{
            document.getElementById('eventModal').style.display = 'none';
        }}
        async function loadDemoData() {{
            if (confirm("Load realistic hackathon demo data (events, students, registrations & check-ins)?")) {{
                const res = await fetch("/api/demo-data", {{ method: "POST" }});
                if (res.ok) window.location.reload();
            }}
        }}
        async function resetAllData() {{
            if (confirm("Are you sure you want to reset all data back to clean state?")) {{
                const res = await fetch("/api/reset-data", {{ method: "POST" }});
                if (res.ok) window.location.reload();
            }}
        }}
    </script>
    """
    return page_layout("Admin Dashboard", content, user, active_tab="dashboard", flash_msg=flash_msg)

def render_admin_events(user, search_query="", flash_msg=None):
    conn = get_db()
    cur = conn.cursor()

    if search_query:
        cur.execute("""
            SELECT e.*, COUNT(r.id) as reg_count 
            FROM events e 
            LEFT JOIN registrations r ON e.id = r.event_id 
            WHERE e.title LIKE ? OR e.venue LIKE ? OR e.category LIKE ?
            GROUP BY e.id 
            ORDER BY e.event_date ASC
        """, (f"%{search_query}%", f"%{search_query}%", f"%{search_query}%"))
    else:
        cur.execute("""
            SELECT e.*, COUNT(r.id) as reg_count 
            FROM events e 
            LEFT JOIN registrations r ON e.id = r.event_id 
            GROUP BY e.id 
            ORDER BY e.event_date ASC
        """)
    events = cur.fetchall()
    conn.close()

    total_events = len(events)

    if events:
        events_table = """
        <div class="panel">
            <div class="table-responsive">
                <table>
                    <thead>
                        <tr>
                            <th>Event Details</th>
                            <th>Category</th>
                            <th>Date & Time</th>
                            <th>Venue</th>
                            <th>Capacity / Regs</th>
                            <th>Action</th>
                        </tr>
                    </thead>
                    <tbody>
        """
        for ev in events:
            pct = min(100, int((ev['reg_count'] / ev['capacity']) * 100)) if ev['capacity'] > 0 else 0
            events_table += f"""
            <tr>
                <td>
                    <div style="font-weight:700; color:#0f172a; font-size:0.95rem;">{ev['title']}</div>
                    <div style="font-size:0.8rem; color:var(--text-muted);">{ev['description'][:80]}...</div>
                </td>
                <td><span class="badge badge-primary">{ev['category']}</span></td>
                <td>{ev['event_date']}<br><span style="font-size:0.8rem; color:var(--text-muted);">{ev['start_time']}</span></td>
                <td>{ev['venue']}</td>
                <td>
                    <div style="font-weight:600;">{ev['reg_count']} / {ev['capacity']}</div>
                    <div style="width:100%; background:#e2e8f0; height:6px; border-radius:3px; margin-top:4px;">
                        <div style="background:var(--primary); height:6px; border-radius:3px; width:{pct}%;"></div>
                    </div>
                </td>
                <td>
                    <form method="POST" action="/admin/events/delete" style="display:inline;" onsubmit="return confirm('Delete event {ev['title']}?');">
                        <input type="hidden" name="event_id" value="{ev['id']}">
                        <button type="submit" class="btn btn-outline btn-sm text-danger" title="Delete">🗑️ Delete</button>
                    </form>
                </td>
            </tr>
            """
        events_table += "</tbody></table></div></div>"
    else:
        events_table = """
        <div class="panel">
            <div class="empty-state">
                <div class="empty-icon">📅</div>
                <div class="empty-title">No events yet</div>
                <div class="empty-desc">Create your first event to get started.</div>
                <button class="btn btn-primary" onclick="openEventModal()">+ Create Event</button>
            </div>
        </div>
        """

    modal_html = render_create_event_modal()
    clear_btn = f'<a href="/admin/events" class="btn btn-outline btn-sm">Clear</a>' if search_query else ''

    content = f"""
    <div class="page-header">
        <div>
            <h1 class="page-title">Manage Events</h1>
            <div class="page-subtitle">{total_events} events total</div>
        </div>
        <div style="display:flex; gap:0.75rem; align-items:center;">
            <form method="GET" action="/admin/events" style="display:flex; gap:0.4rem;">
                <input type="text" name="q" value="{search_query}" class="form-control" style="width:240px;" placeholder="Search events...">
                <button type="submit" class="btn btn-primary btn-sm">Go</button>
                {clear_btn}
            </form>
            <button class="btn btn-primary" onclick="openEventModal()">+ New Event</button>
        </div>
    </div>

    {events_table}
    {modal_html}

    <script>
        function openEventModal() {{
            document.getElementById('eventModal').style.display = 'flex';
        }}
        function closeEventModal() {{
            document.getElementById('eventModal').style.display = 'none';
        }}
    </script>
    """
    return page_layout("Manage Events", content, user, active_tab="events", flash_msg=flash_msg)

def render_admin_students(user, search_query="", flash_msg=None):
    conn = get_db()
    cur = conn.cursor()

    if search_query:
        cur.execute("""
            SELECT u.*, COUNT(r.id) as reg_count 
            FROM users u
            LEFT JOIN registrations r ON u.id = r.student_id
            WHERE u.role = 'student' AND (u.name LIKE ? OR u.email LIKE ? OR u.roll_number LIKE ?)
            GROUP BY u.id
            ORDER BY u.id DESC
        """, (f"%{search_query}%", f"%{search_query}%", f"%{search_query}%"))
    else:
        cur.execute("""
            SELECT u.*, COUNT(r.id) as reg_count 
            FROM users u
            LEFT JOIN registrations r ON u.id = r.student_id
            WHERE u.role = 'student'
            GROUP BY u.id
            ORDER BY u.id DESC
        """)
    students = cur.fetchall()
    conn.close()

    total_students = len(students)

    if students:
        table_html = """
        <div class="panel">
            <div class="table-responsive">
                <table>
                    <thead>
                        <tr>
                            <th>Student Name</th>
                            <th>Roll Number</th>
                            <th>Email Address</th>
                            <th>Events Registered</th>
                            <th>Joined Date</th>
                        </tr>
                    </thead>
                    <tbody>
        """
        for s in students:
            table_html += f"""
            <tr>
                <td><strong>{s['name']}</strong></td>
                <td><span class="badge badge-secondary">{s['roll_number']}</span></td>
                <td>{s['email']}</td>
                <td><span class="badge badge-primary">{s['reg_count']} Events</span></td>
                <td>{s['created_at'][:10]}</td>
            </tr>
            """
        table_html += "</tbody></table></div></div>"
    else:
        table_html = """
        <div class="panel">
            <div class="empty-state">
                <div class="empty-icon">👥</div>
                <div class="empty-title">No students found</div>
                <div class="empty-desc">Students will appear here once they sign up.</div>
            </div>
        </div>
        """

    clear_btn = f'<a href="/admin/students" class="btn btn-outline btn-sm">Clear</a>' if search_query else ''

    content = f"""
    <div class="page-header">
        <div>
            <h1 class="page-title">Registered Students</h1>
            <div class="page-subtitle">{total_students} students</div>
        </div>
        <div>
            <form method="GET" action="/admin/students" style="display:flex; gap:0.4rem;">
                <input type="text" name="q" value="{search_query}" class="form-control" style="width:260px;" placeholder="Name / Email / Roll">
                <button type="submit" class="btn btn-primary btn-sm">Filter</button>
                {clear_btn}
            </form>
        </div>
    </div>

    {table_html}
    """
    return page_layout("Registered Students", content, user, active_tab="students", flash_msg=flash_msg)

def render_admin_registrations(user, event_filter=None, flash_msg=None):
    conn = get_db()
    cur = conn.cursor()

    events = cur.execute("SELECT id, title FROM events ORDER BY title ASC").fetchall()

    if event_filter and event_filter != "all":
        cur.execute("""
            SELECT r.*, u.name as student_name, u.roll_number, u.email as student_email, e.title as event_title
            FROM registrations r
            JOIN users u ON r.student_id = u.id
            JOIN events e ON r.event_id = e.id
            WHERE r.event_id = ?
            ORDER BY r.id DESC
        """, (event_filter,))
    else:
        cur.execute("""
            SELECT r.*, u.name as student_name, u.roll_number, u.email as student_email, e.title as event_title
            FROM registrations r
            JOIN users u ON r.student_id = u.id
            JOIN events e ON r.event_id = e.id
            ORDER BY r.id DESC
        """)
    regs = cur.fetchall()
    conn.close()

    total_regs = len(regs)

    options_html = '<option value="all">All Events</option>'
    for ev in events:
        sel = 'selected' if str(ev['id']) == str(event_filter) else ''
        options_html += f'<option value="{ev["id"]}" {sel}>{ev["title"]}</option>'

    if regs:
        table_html = """
        <div class="panel">
            <div class="table-responsive">
                <table>
                    <thead>
                        <tr>
                            <th>Reg ID</th>
                            <th>Student</th>
                            <th>Event</th>
                            <th>QR Token</th>
                            <th>Registered At</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody>
        """
        for r in regs:
            status_badge = '<span class="badge badge-success">Checked-In</span>' if r['checked_in'] else '<span class="badge badge-warning">Registered</span>'
            table_html += f"""
            <tr>
                <td><strong>#{r['id']}</strong></td>
                <td>
                    <div style="font-weight:600;">{r['student_name']}</div>
                    <div style="font-size:0.8rem; color:var(--text-muted);">{r['roll_number']}</div>
                </td>
                <td>{r['event_title']}</td>
                <td><code style="background:#f1f5f9; padding:2px 6px; border-radius:4px; font-size:0.75rem;">{r['qr_token'][:8]}...</code></td>
                <td>{r['registered_at'][:16]}</td>
                <td>{status_badge}</td>
            </tr>
            """
        table_html += "</tbody></table></div></div>"
    else:
        table_html = """
        <div class="panel">
            <div class="empty-state">
                <div class="empty-icon">📋</div>
                <div class="empty-title">No registrations found</div>
                <div class="empty-desc">Registrations will appear here once students sign up for events.</div>
            </div>
        </div>
        """

    content = f"""
    <div class="page-header">
        <div>
            <h1 class="page-title">Registrations</h1>
            <div class="page-subtitle">{total_regs} total registrations</div>
        </div>
        <div>
            <form method="GET" action="/admin/registrations" style="display:flex; gap:0.5rem;">
                <select name="event" class="form-control" style="width:260px;">
                    {options_html}
                </select>
                <button type="submit" class="btn btn-primary btn-sm">Filter</button>
            </form>
        </div>
    </div>

    {table_html}
    """
    return page_layout("Registrations", content, user, active_tab="registrations", flash_msg=flash_msg)

def render_admin_checkin(user, flash_msg=None):
    conn = get_db()
    cur = conn.cursor()
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")

    checkins_today = cur.execute("""
        SELECT COUNT(*) FROM registrations 
        WHERE checked_in = 1 AND checkin_time LIKE ?
    """, (f"{today_str}%",)).fetchone()[0]

    recent_checkins = cur.execute("""
        SELECT r.id, r.checkin_time, u.name as student_name, u.roll_number, e.title as event_title
        FROM registrations r
        JOIN users u ON r.student_id = u.id
        JOIN events e ON r.event_id = e.id
        WHERE r.checked_in = 1
        ORDER BY r.checkin_time DESC
        LIMIT 8
    """).fetchall()
    conn.close()

    if recent_checkins:
        recent_html = '<div style="display:flex; flex-direction:column; gap:0.5rem;">'
        for rc in recent_checkins:
            recent_html += f"""
            <div style="padding:0.6rem 0.8rem; background:#f8fafc; border-radius:6px; border:1px solid var(--border); font-size:0.85rem;">
                <div style="display:flex; justify-content:space-between; font-weight:600;">
                    <span>{rc['student_name']} ({rc['roll_number']})</span>
                    <span style="color:var(--success);">✅ Verified</span>
                </div>
                <div style="font-size:0.75rem; color:var(--text-muted); margin-top:2px;">
                    {rc['event_title']} • {rc['checkin_time'][11:19]}
                </div>
            </div>
            """
        recent_html += '</div>'
    else:
        recent_html = '<div style="color:var(--text-muted); font-size:0.875rem; text-align:center; padding:1.5rem 0;">No check-ins yet today.</div>'

    template = """
    <div class="page-header">
        <div>
            <h1 class="page-title">Event Check-In Station</h1>
            <div class="page-subtitle">Verify student attendance via QR code scan or manual token entry</div>
        </div>
    </div>

    <div style="display:grid; grid-template-columns: 1.2fr 0.8fr; gap:1.5rem;">
        <!-- Left: Scan or Manual Entry Card -->
        <div class="panel">
            <div style="display:flex; border-bottom:1px solid var(--border);">
                <button id="tabScannerBtn" class="btn" style="flex:1; border-radius:0; background:#f8fafc; font-weight:600; border-bottom:2px solid var(--primary);" onclick="switchTab('scanner')">
                    📷 Scan QR Code
                </button>
                <button id="tabManualBtn" class="btn" style="flex:1; border-radius:0; background:white; font-weight:600; color:var(--text-muted);" onclick="switchTab('manual')">
                    📝 Manual Entry
                </button>
            </div>
            <div class="panel-body">
                <!-- Camera QR Scanner View -->
                <div id="scannerTab">
                    <div style="position:relative; width:100%; max-width:440px; margin:0 auto; background:#0f172a; border-radius:12px; overflow:hidden; aspect-ratio:4/3; display:flex; align-items:center; justify-content:center;">
                        <div id="reader" style="width:100%;"></div>
                        <div style="position:absolute; width:180px; height:180px; border:2px dashed rgba(255,255,255,0.7); border-radius:12px; pointer-events:none; box-shadow:0 0 0 9999px rgba(0,0,0,0.35);"></div>
                    </div>
                    <div style="text-align:center; margin-top:1rem;">
                        <button id="cameraToggleBtn" class="btn btn-outline btn-sm" onclick="toggleCamera()">📹 Start / Stop Camera</button>
                        <div style="font-size:0.8rem; color:var(--text-muted); margin-top:0.4rem;">
                            Position the student's ticket QR code within the viewfinder.
                        </div>
                    </div>
                </div>

                <!-- Manual Entry View -->
                <div id="manualTab" style="display:none; padding:1.5rem 0.5rem;">
                    <h3 style="font-size:1.05rem; margin-bottom:0.75rem;">Enter Registration ID or Token</h3>
                    <div class="form-group">
                        <input type="text" id="manualQueryInput" class="form-control" style="font-size:1rem; padding:0.8rem;" placeholder="Registration ID or QR token (UUID)" autofocus>
                    </div>
                    <button class="btn btn-primary" style="width:100%; padding:0.75rem;" onclick="submitManualCheckin()">
                        Verify & Check In
                    </button>
                    <div style="font-size:0.8rem; color:var(--text-muted); margin-top:0.75rem; text-align:center;">
                        Use this if camera isn't available. Enter the numeric Registration ID (e.g. 1) or the full QR token.
                    </div>
                </div>
            </div>
        </div>

        <!-- Right: Check-In Result & Recent Feed -->
        <div class="panel">
            <div class="panel-header">
                <div class="panel-title">Check-In Result</div>
                <span class="badge badge-success" id="todayBadge">{{CHECKINS_TODAY}} today</span>
            </div>
            <div class="panel-body">
                <div id="resultBox" style="margin-bottom:1.5rem; text-align:center; padding:1.75rem 1rem; border:1px dashed var(--border); border-radius:10px; background:#f8fafc;">
                    <div style="font-size:2.5rem; margin-bottom:0.5rem; opacity:0.6;">🔲</div>
                    <div style="font-weight:600; color:var(--text-dark);">Ready to Check In</div>
                    <div style="font-size:0.85rem; color:var(--text-muted); margin-top:0.25rem;">Scan a QR code or enter ID to begin.</div>
                </div>

                <h4 style="font-size:0.95rem; font-weight:700; color:#1e293b; margin-bottom:0.75rem;">Recent Check-ins</h4>
                <div id="recentFeed">
                    {{RECENT_HTML}}
                </div>
            </div>
        </div>
    </div>

    <script>
        let html5QrCode = null;
        let isCameraRunning = false;

        function switchTab(tab) {
            if (tab === 'scanner') {
                document.getElementById('scannerTab').style.display = 'block';
                document.getElementById('manualTab').style.display = 'none';
                document.getElementById('tabScannerBtn').style.background = '#f8fafc';
                document.getElementById('tabScannerBtn').style.borderBottom = '2px solid var(--primary)';
                document.getElementById('tabScannerBtn').style.color = 'var(--text-dark)';
                document.getElementById('tabManualBtn').style.background = 'white';
                document.getElementById('tabManualBtn').style.borderBottom = 'none';
                document.getElementById('tabManualBtn').style.color = 'var(--text-muted)';
            } else {
                document.getElementById('scannerTab').style.display = 'none';
                document.getElementById('manualTab').style.display = 'block';
                document.getElementById('tabManualBtn').style.background = '#f8fafc';
                document.getElementById('tabManualBtn').style.borderBottom = '2px solid var(--primary)';
                document.getElementById('tabManualBtn').style.color = 'var(--text-dark)';
                document.getElementById('tabScannerBtn').style.background = 'white';
                document.getElementById('tabScannerBtn').style.borderBottom = 'none';
                document.getElementById('tabScannerBtn').style.color = 'var(--text-muted)';
                document.getElementById('manualQueryInput').focus();
            }
        }

        async function verifyCheckin(queryStr) {
            if (!queryStr || queryStr.trim() === '') return;
            const resultBox = document.getElementById('resultBox');
            resultBox.innerHTML = '<div style="font-size:1.5rem;">⏳</div><div>Verifying registration...</div>';

            try {
                const res = await fetch('/api/check-in', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ query: queryStr.trim() })
                });
                const data = await res.json();
                
                if (data.status === 'success') {
                    resultBox.style.background = '#ecfdf5';
                    resultBox.style.borderColor = '#6ee7b7';
                    resultBox.innerHTML = `
                        <div style="font-size:2.5rem; margin-bottom:0.25rem;">✅</div>
                        <div style="font-size:1.15rem; font-weight:700; color:#065f46;">Check-In Successful!</div>
                        <div style="font-weight:600; font-size:1rem; color:#0f172a; margin-top:0.4rem;">${data.student_name}</div>
                        <div style="font-size:0.85rem; color:#374151;">Roll: <strong>${data.roll_number}</strong> • ID: #${data.reg_id}</div>
                        <div style="font-size:0.85rem; color:#4b5563; margin-top:0.35rem;">Event: <strong>${data.event_title}</strong></div>
                        <div style="font-size:0.75rem; color:#059669; margin-top:0.4rem;">Checked in at ${data.checkin_time}</div>
                    `;
                    prependRecent(data);
                } else if (data.status === 'warning') {
                    resultBox.style.background = '#fffbeb';
                    resultBox.style.borderColor = '#fcd34d';
                    resultBox.innerHTML = `
                        <div style="font-size:2.5rem; margin-bottom:0.25rem;">⚠️</div>
                        <div style="font-size:1.15rem; font-weight:700; color:#92400e;">Already Checked In</div>
                        <div style="font-weight:600; font-size:1rem; color:#0f172a; margin-top:0.4rem;">${data.student_name}</div>
                        <div style="font-size:0.85rem; color:#374151;">Roll: <strong>${data.roll_number}</strong> • Event: <strong>${data.event_title}</strong></div>
                        <div style="font-size:0.8rem; color:#b45309; margin-top:0.4rem;">Previously checked in at: ${data.checkin_time}</div>
                    `;
                } else {
                    resultBox.style.background = '#fef2f2';
                    resultBox.style.borderColor = '#fca5a5';
                    resultBox.innerHTML = `
                        <div style="font-size:2.5rem; margin-bottom:0.25rem;">❌</div>
                        <div style="font-size:1.15rem; font-weight:700; color:#991b1b;">Invalid Registration</div>
                        <div style="font-size:0.85rem; color:#b91c1c; margin-top:0.35rem;">${data.message || 'No matching registration found for this ID/Token.'}</div>
                    `;
                }
            } catch (err) {
                resultBox.innerHTML = `<div style="color:var(--danger)">Error: ${err.message}</div>`;
            }
        }

        function prependRecent(data) {
            const feed = document.getElementById('recentFeed');
            const item = document.createElement('div');
            item.style.cssText = 'padding:0.6rem 0.8rem; background:#f0fdf4; border-radius:6px; border:1px solid #bbf7d0; font-size:0.85rem; margin-bottom:0.5rem; animation:fadeIn 0.3s;';
            item.innerHTML = `
                <div style="display:flex; justify-content:space-between; font-weight:600;">
                    <span>${data.student_name} (${data.roll_number})</span>
                    <span style="color:var(--success);">✅ Verified</span>
                </div>
                <div style="font-size:0.75rem; color:var(--text-muted); margin-top:2px;">
                    ${data.event_title} • Just now
                </div>
            `;
            feed.prepend(item);
        }

        function submitManualCheckin() {
            const input = document.getElementById('manualQueryInput');
            verifyCheckin(input.value);
            input.value = '';
        }

        document.getElementById('manualQueryInput')?.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                submitManualCheckin();
            }
        });

        function toggleCamera() {
            if (isCameraRunning) {
                if (html5QrCode) {
                    html5QrCode.stop().then(() => {
                        isCameraRunning = false;
                        document.getElementById('cameraToggleBtn').innerText = '📹 Start Camera';
                    });
                }
            } else {
                html5QrCode = new Html5Qrcode("reader");
                html5QrCode.start(
                    { facingMode: "environment" },
                    { fps: 10, qrbox: { width: 220, height: 220 } },
                    (decodedText, decodedResult) => {
                        verifyCheckin(decodedText);
                    },
                    (errorMessage) => {}
                ).then(() => {
                    isCameraRunning = true;
                    document.getElementById('cameraToggleBtn').innerText = '🛑 Stop Camera';
                }).catch(err => {
                    alert("Camera access failed or permission denied: " + err);
                });
            }
        }
    </script>
    """
    content = render_tmpl(template, CHECKINS_TODAY=str(checkins_today), RECENT_HTML=recent_html)
    return page_layout("Check-In Station", content, user, active_tab="check-in", flash_msg=flash_msg)

def render_admin_attendance(user, event_id=None, flash_msg=None):
    conn = get_db()
    cur = conn.cursor()

    events = cur.execute("SELECT id, title, event_date, venue FROM events ORDER BY event_date ASC").fetchall()

    selected_event = None
    attendees = []
    total_reg = 0
    attended_count = 0
    absent_count = 0
    attendance_rate = 0

    if event_id:
        selected_event = cur.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
        if selected_event:
            attendees = cur.execute("""
                SELECT r.id as reg_id, r.qr_token, r.registered_at, r.checked_in, r.checkin_time,
                       u.name as student_name, u.roll_number, u.email as student_email
                FROM registrations r
                JOIN users u ON r.student_id = u.id
                WHERE r.event_id = ?
                ORDER BY r.checked_in DESC, u.roll_number ASC
            """, (event_id,)).fetchall()
            
            total_reg = len(attendees)
            attended_count = sum(1 for a in attendees if a['checked_in'] == 1)
            absent_count = total_reg - attended_count
            attendance_rate = round((attended_count / total_reg * 100), 1) if total_reg > 0 else 0

    conn.close()

    options_html = '<option value="">-- Choose an event --</option>'
    for ev in events:
        sel = 'selected' if str(ev['id']) == str(event_id) else ''
        options_html += f'<option value="{ev["id"]}" {sel}>{ev["title"]} ({ev["event_date"]})</option>'

    if selected_event:
        table_rows = ""
        for att in attendees:
            status_badge = '<span class="badge badge-success">Attended</span>' if att['checked_in'] else '<span class="badge badge-danger">Absent</span>'
            time_display = att['checkin_time'] if att['checkin_time'] else '-'
            table_rows += f"""
            <tr>
                <td><strong>{att['student_name']}</strong></td>
                <td><span class="badge badge-secondary">{att['roll_number']}</span></td>
                <td>{att['student_email']}</td>
                <td>{status_badge}</td>
                <td>{time_display}</td>
                <td>{att['registered_at'][:16]}</td>
            </tr>
            """

        report_content = f"""
        <div class="stats-grid" style="margin-top:1.5rem;">
            <div class="stat-card">
                <div class="stat-info">
                    <div class="stat-value">{total_reg}</div>
                    <div class="stat-label">Total Registered</div>
                </div>
                <div class="stat-icon icon-blue">📋</div>
            </div>
            <div class="stat-card">
                <div class="stat-info">
                    <div class="stat-value" style="color:var(--success);">{attended_count}</div>
                    <div class="stat-label">Attended / Checked-In</div>
                </div>
                <div class="stat-icon icon-green">✅</div>
            </div>
            <div class="stat-card">
                <div class="stat-info">
                    <div class="stat-value" style="color:var(--danger);">{absent_count}</div>
                    <div class="stat-label">Absent</div>
                </div>
                <div class="stat-icon icon-orange">❌</div>
            </div>
            <div class="stat-card">
                <div class="stat-info">
                    <div class="stat-value">{attendance_rate}%</div>
                    <div class="stat-label">Turnout Rate</div>
                </div>
                <div class="stat-icon icon-purple">📈</div>
            </div>
        </div>

        <div class="panel">
            <div class="panel-header">
                <div class="panel-title">Attendee Roster: {selected_event['title']}</div>
                <div style="display:flex; gap:0.5rem;">
                    <a href="/api/attendance/export?event_id={selected_event['id']}" class="btn btn-outline btn-sm">
                        📥 Export to CSV
                    </a>
                    <button onclick="window.print()" class="btn btn-outline btn-sm">
                        🖨️ Print Report
                    </button>
                </div>
            </div>
            <div class="table-responsive">
                <table>
                    <thead>
                        <tr>
                            <th>Student</th>
                            <th>Roll Number</th>
                            <th>Email</th>
                            <th>Status</th>
                            <th>Check-In Time</th>
                            <th>Registration Date</th>
                        </tr>
                    </thead>
                    <tbody>
                        {table_rows}
                    </tbody>
                </table>
            </div>
        </div>
        """
    elif not events:
        report_content = """
        <div class="panel" style="margin-top:1.5rem;">
            <div class="empty-state">
                <div class="empty-icon">📅</div>
                <div class="empty-title">No events yet</div>
                <div class="empty-desc">Create an event first to view its attendance report.</div>
                <a href="/admin/events" class="btn btn-primary">+ Create Event</a>
            </div>
        </div>
        """
    else:
        report_content = """
        <div class="panel" style="margin-top:1.5rem;">
            <div class="empty-state">
                <div class="empty-icon">📊</div>
                <div class="empty-title">Select an event above</div>
                <div class="empty-desc">Choose an event from the dropdown to review turnout rates and download rosters.</div>
            </div>
        </div>
        """

    content = f"""
    <div class="page-header">
        <div>
            <h1 class="page-title">Attendance Reports</h1>
            <div class="page-subtitle">View and export attendance per event</div>
        </div>
    </div>

    <div class="panel">
        <div class="panel-body">
            <form method="GET" action="/admin/attendance" style="display:flex; gap:1rem; align-items:flex-end; flex-wrap:wrap;">
                <div style="flex:1; min-width:280px;">
                    <label class="form-label">Select Event</label>
                    <select name="event_id" class="form-control" required>
                        {options_html}
                    </select>
                </div>
                <button type="submit" class="btn btn-primary" style="padding:0.65rem 1.5rem;">View Report</button>
            </form>
        </div>
    </div>

    {report_content}
    """
    return page_layout("Attendance Reports", content, user, active_tab="attendance", flash_msg=flash_msg)


def render_student_events(user, flash_msg=None):
    conn = get_db()
    cur = conn.cursor()

    events = cur.execute("""
        SELECT e.*, 
               (SELECT COUNT(*) FROM registrations WHERE event_id = e.id) as reg_count,
               (SELECT id FROM registrations WHERE event_id = e.id AND student_id = ?) as my_reg_id
        FROM events e
        ORDER BY e.event_date ASC
    """, (user['user_id'],)).fetchall()
    conn.close()

    cards_html = ""
    for ev in events:
        is_registered = ev['my_reg_id'] is not None
        reg_btn = ""
        if is_registered:
            reg_btn = '<span class="badge badge-success" style="padding:0.4rem 0.8rem; font-size:0.85rem;">✅ You are Registered!</span>'
        elif ev['reg_count'] >= ev['capacity']:
            reg_btn = '<span class="badge badge-danger">Sold Out / Full</span>'
        else:
            reg_btn = f"""
            <form method="POST" action="/student/register-event">
                <input type="hidden" name="event_id" value="{ev['id']}">
                <button type="submit" class="btn btn-primary btn-sm">Register Now</button>
            </form>
            """

        cards_html += f"""
        <div class="panel" style="display:flex; flex-direction:column; justify-content:space-between;">
            <div class="panel-body">
                <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:0.5rem;">
                    <span class="badge badge-primary">{ev['category']}</span>
                    <span style="font-size:0.8rem; color:var(--text-muted);">{ev['reg_count']} / {ev['capacity']} filled</span>
                </div>
                <h3 style="font-size:1.15rem; color:#0f172a; margin-bottom:0.5rem;">{ev['title']}</h3>
                <p style="font-size:0.875rem; color:var(--text-muted); line-height:1.4; margin-bottom:1rem;">{ev['description']}</p>
                <div style="font-size:0.825rem; color:#334155; display:flex; flex-direction:column; gap:0.25rem;">
                    <div>📅 <strong>Date:</strong> {ev['event_date']} at {ev['start_time']}</div>
                    <div>📍 <strong>Venue:</strong> {ev['venue']}</div>
                </div>
            </div>
            <div style="padding:0.75rem 1.25rem; background:#f8fafc; border-top:1px solid var(--border); display:flex; justify-content:flex-end;">
                {reg_btn}
            </div>
        </div>
        """

    if not events:
        cards_html = """
        <div class="panel" style="grid-column: 1 / -1;">
            <div class="empty-state">
                <div class="empty-icon">🎟️</div>
                <div class="empty-title">No events open for registration yet</div>
                <div class="empty-desc">Check back soon for hackathons, workshops, and college fests!</div>
            </div>
        </div>
        """

    content = f"""
    <div class="page-header">
        <div>
            <h1 class="page-title">Explore College Events</h1>
            <div class="page-subtitle">Discover hackathons, workshops, and campus activities</div>
        </div>
    </div>
    <div style="display:grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap:1.5rem;">
        {cards_html}
    </div>
    """
    return page_layout("Explore Events", content, user, active_tab="browse", flash_msg=flash_msg)

def render_student_tickets(user, flash_msg=None):
    conn = get_db()
    cur = conn.cursor()

    tickets = cur.execute("""
        SELECT r.*, e.title, e.event_date, e.start_time, e.venue, e.category
        FROM registrations r
        JOIN events e ON r.event_id = e.id
        WHERE r.student_id = ?
        ORDER BY e.event_date ASC
    """, (user['user_id'],)).fetchall()
    conn.close()

    tickets_html = ""
    for tk in tickets:
        status_badge = '<span class="badge badge-success">Checked-In</span>' if tk['checked_in'] else '<span class="badge badge-warning">Active Pass</span>'
        tickets_html += f"""
        <div class="panel" style="margin-bottom:1.5rem; display:grid; grid-template-columns: 2fr 1fr; border-left: 6px solid var(--primary);">
            <div class="panel-body" style="padding:1.5rem;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.5rem;">
                    <span class="badge badge-primary">{tk['category']}</span>
                    {status_badge}
                </div>
                <h2 style="font-size:1.35rem; color:#0f172a; margin-bottom:0.75rem;">{tk['title']}</h2>
                <div style="font-size:0.9rem; color:#334155; line-height:1.6;">
                    <div>📅 <strong>Date:</strong> {tk['event_date']} at {tk['start_time']}</div>
                    <div>📍 <strong>Venue:</strong> {tk['venue']}</div>
                    <div>👤 <strong>Attendee:</strong> {user['name']} (Roll: {user['roll_number']})</div>
                    <div>🎫 <strong>Registration ID:</strong> #{tk['id']}</div>
                </div>
                <div style="margin-top:1rem; font-size:0.75rem; color:var(--text-muted);">
                    Present this QR code or Registration ID at the venue entrance check-in desk.
                </div>
            </div>
            <div style="background:#f8fafc; border-left:1px dashed var(--border); display:flex; flex-direction:column; align-items:center; justify-content:center; padding:1.5rem; text-align:center;">
                <div id="qrcode_{tk['id']}" style="background:white; padding:8px; border-radius:8px; border:1px solid var(--border);"></div>
                <div style="font-size:0.75rem; font-family:monospace; margin-top:0.5rem; color:var(--text-muted); word-break:break-all;">
                    Token: {tk['qr_token'][:12]}...
                </div>
                <script>
                    new QRCode(document.getElementById("qrcode_{tk['id']}"), {{
                        text: "{tk['qr_token']}",
                        width: 120,
                        height: 120,
                        correctLevel: QRCode.CorrectLevel.M
                    }});
                </script>
            </div>
        </div>
        """

    if not tickets:
        tickets_html = """
        <div class="panel">
            <div class="empty-state">
                <div class="empty-icon">🎟️</div>
                <div class="empty-title">You have no registered event passes</div>
                <div class="empty-desc">Head over to the events catalog and sign up for upcoming events!</div>
                <a href="/student/events" class="btn btn-primary">Browse Events</a>
            </div>
        </div>
        """

    content = f"""
    <div class="page-header">
        <div>
            <h1 class="page-title">My Event Passes</h1>
            <div class="page-subtitle">Your digital registration badges and check-in QR codes</div>
        </div>
    </div>

    <div>
        {tickets_html}
    </div>
    """
    return page_layout("My Passes", content, user, active_tab="my-tickets", flash_msg=flash_msg)


class EventEaseHandler(BaseHTTPRequestHandler):
    def send_html(self, content, status=200, cookie_header=None):
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        if cookie_header:
            self.send_header("Set-Cookie", cookie_header)
        self.end_headers()
        self.wfile.write(content.encode("utf-8"))

    def send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def redirect(self, location, cookie_header=None):
        self.send_response(302)
        self.send_header("Location", location)
        if cookie_header:
            self.send_header("Set-Cookie", cookie_header)
        self.end_headers()

    def parse_body_form(self):
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length).decode("utf-8")
        return urllib.parse.parse_qs(post_data)

    def parse_body_json(self):
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length).decode("utf-8")
        try:
            return json.loads(post_data)
        except Exception:
            return {}

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)
        user = get_current_user(self.headers)

        if path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return

        if path == "/static/login_qr.png":
            qr_path = "login_qr_opt.png" if os.path.exists("login_qr_opt.png") else "login_qr.png"
            if not os.path.exists(qr_path) and os.path.exists("user_uploaded_files/ttl=63d/user_uploaded/image_e156fe.png"):
                qr_path = "user_uploaded_files/ttl=63d/user_uploaded/image_e156fe.png"
            try:
                with open(qr_path, "rb") as f:
                    data = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.send_header("Cache-Control", "public, max-age=86400")
                self.end_headers()
                self.wfile.write(data)
            except Exception as e:
                self.send_html("Image error", 500)
            return

        if path == "/login":
            if user:
                dest = "/admin/dashboard" if user["role"] == "admin" else "/student/events"
                self.redirect(dest)
                return
            flash = query.get("msg", [None])[0]
            flash_type = query.get("type", ["success"])[0]
            qr_token = str(uuid.uuid4())
            QR_LOGIN_SESSIONS[qr_token] = {
                "created_at": datetime.datetime.now(),
                "status": "pending",
                "user": None
            }
            self.send_html(render_login(flash, flash_type, qr_token))
            return

        if path == "/qr-login":
            qr_token = query.get("token", [""])[0]
            conn = get_db()
            cur = conn.cursor()
            students = cur.execute("SELECT id, name, email, roll_number FROM users WHERE role = 'student' ORDER BY name ASC").fetchall()
            conn.close()
            self.send_html(render_mobile_qr_auth(qr_token, students))
            return

        if path == "/api/qr-poll":
            qr_token = query.get("token", [""])[0]
            sess_data = QR_LOGIN_SESSIONS.get(qr_token)
            if sess_data and sess_data.get("status") == "authorized" and sess_data.get("user"):
                auth_user = sess_data["user"]
                session_id = create_session(auth_user)
                cookie_header = f"session_id={session_id}; Path=/; HttpOnly"
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Set-Cookie", cookie_header)
                self.end_headers()
                self.wfile.write(json.dumps({
                    "status": "authorized",
                    "redirect": "/student/events",
                    "student_name": auth_user["name"]
                }).encode("utf-8"))
                return
            self.send_json({"status": "waiting"})
            return

        if path == "/register":
            if user:
                self.redirect("/student/events")
                return
            flash = query.get("msg", [None])[0]
            self.send_html(render_register(flash, "danger"))
            return

        if path == "/logout":
            cookie_header = "session_id=; Path=/; Expires=Thu, 01 Jan 1970 00:00:00 GMT"
            self.redirect("/login?msg=You+have+been+logged+out+successfully.&type=success", cookie_header)
            return

        if path == "/":
            if not user:
                self.redirect("/login")
            elif user["role"] == "admin":
                self.redirect("/admin/dashboard")
            else:
                self.redirect("/student/events")
            return

        if not user:
            self.redirect("/login?msg=Please+sign+in+to+continue.&type=warning")
            return

        # Admin routes
        if path.startswith("/admin") or path.startswith("/api/attendance/export"):
            if user["role"] != "admin":
                self.redirect("/student/events?msg=Unauthorized+access.&type=danger")
                return

            if path == "/admin/dashboard":
                self.send_html(render_admin_dashboard(user))
            elif path == "/admin/events":
                q = query.get("q", [""])[0]
                self.send_html(render_admin_events(user, q))
            elif path == "/admin/students":
                q = query.get("q", [""])[0]
                self.send_html(render_admin_students(user, q))
            elif path == "/admin/registrations":
                ev_id = query.get("event", ["all"])[0]
                self.send_html(render_admin_registrations(user, ev_id))
            elif path == "/admin/check-in":
                self.send_html(render_admin_checkin(user))
            elif path == "/admin/attendance":
                ev_id = query.get("event_id", [None])[0]
                self.send_html(render_admin_attendance(user, ev_id))
            elif path == "/api/attendance/export":
                self.handle_export_csv(query)
            else:
                self.send_html("<h1>404 Not Found</h1>", 404)
            return

        # Student routes
        if path.startswith("/student"):
            if path == "/student/events":
                self.send_html(render_student_events(user))
            elif path == "/student/my-tickets":
                self.send_html(render_student_tickets(user))
            else:
                self.send_html("<h1>404 Not Found</h1>", 404)
            return

        self.send_html("<h1>404 Not Found</h1>", 404)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        user = get_current_user(self.headers)

        if path == "/qr-login":
            form = self.parse_body_form()
            qr_token = form.get("token", [""])[0]
            student_email = form.get("student_email", [""])[0].strip().lower()

            conn = get_db()
            cur = conn.cursor()
            student_user = cur.execute("SELECT * FROM users WHERE email = ? AND role = 'student'", (student_email,)).fetchone()
            conn.close()

            if not student_user:
                self.send_html("Student not found", 400)
                return

            user_dict = dict(student_user)
            if qr_token and qr_token in QR_LOGIN_SESSIONS:
                QR_LOGIN_SESSIONS[qr_token]["status"] = "authorized"
                QR_LOGIN_SESSIONS[qr_token]["user"] = user_dict

            session_id = create_session(user_dict)
            cookie_header = f"session_id={session_id}; Path=/; HttpOnly"
            self.redirect("/student/events", cookie_header)
            return

        if path == "/api/qr-simulate":
            data = self.parse_body_json()
            qr_token = data.get("token", "")

            conn = get_db()
            cur = conn.cursor()
            student_user = cur.execute("SELECT * FROM users WHERE role = 'student' ORDER BY id ASC LIMIT 1").fetchone()
            conn.close()

            if not student_user:
                self.send_json({"status": "error", "message": "No student accounts found."})
                return

            user_dict = dict(student_user)
            if qr_token and qr_token in QR_LOGIN_SESSIONS:
                QR_LOGIN_SESSIONS[qr_token]["status"] = "authorized"
                QR_LOGIN_SESSIONS[qr_token]["user"] = user_dict

            session_id = create_session(user_dict)
            cookie_header = f"session_id={session_id}; Path=/; HttpOnly"

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Set-Cookie", cookie_header)
            self.end_headers()
            self.wfile.write(json.dumps({
                "status": "ok",
                "redirect": "/student/events",
                "student_name": user_dict["name"]
            }).encode("utf-8"))
            return

        if path == "/api/qr-badge-login":
            data = self.parse_body_json()
            query_val = data.get("query", "").strip()
            qr_token = data.get("token", "")

            if not query_val:
                self.send_json({"status": "error", "message": "Empty scan query."})
                return

            conn = get_db()
            cur = conn.cursor()
            student_user = None

            reg = cur.execute("""
                SELECT u.* FROM registrations r
                JOIN users u ON r.student_id = u.id
                WHERE r.qr_token = ?
            """, (query_val,)).fetchone()

            if reg:
                student_user = reg
            else:
                student_user = cur.execute("""
                    SELECT * FROM users 
                    WHERE role = 'student' AND (roll_number = ? OR email = ?)
                """, (query_val, query_val.lower())).fetchone()

            conn.close()

            if not student_user:
                self.send_json({"status": "error", "message": "Student pass or ID not recognized."})
                return

            user_dict = dict(student_user)
            if qr_token and qr_token in QR_LOGIN_SESSIONS:
                QR_LOGIN_SESSIONS[qr_token]["status"] = "authorized"
                QR_LOGIN_SESSIONS[qr_token]["user"] = user_dict

            session_id = create_session(user_dict)
            cookie_header = f"session_id={session_id}; Path=/; HttpOnly"

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Set-Cookie", cookie_header)
            self.end_headers()
            self.wfile.write(json.dumps({
                "status": "success",
                "redirect": "/student/events",
                "student_name": user_dict["name"]
            }).encode("utf-8"))
            return

        if path == "/login":
            form = self.parse_body_form()
            email = form.get("email", [""])[0].strip().lower()
            password = form.get("password", [""])[0]

            conn = get_db()
            cur = conn.cursor()
            db_user = cur.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
            conn.close()

            if db_user and db_user["password_hash"] == hash_password(password):
                session_id = create_session(dict(db_user))
                cookie_header = f"session_id={session_id}; Path=/; HttpOnly"
                dest = "/admin/dashboard" if db_user["role"] == "admin" else "/student/events"
                self.redirect(dest, cookie_header)
            else:
                self.send_html(render_login("Invalid email or password. Please try again.", "danger"), 401)
            return

        if path == "/register":
            form = self.parse_body_form()
            name = form.get("name", [""])[0].strip()
            roll = form.get("roll_number", [""])[0].strip()
            email = form.get("email", [""])[0].strip().lower()
            password = form.get("password", [""])[0]

            if not (name and roll and email and password):
                self.send_html(render_register("All fields are required.", "danger"), 400)
                return

            conn = get_db()
            cur = conn.cursor()
            existing = cur.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
            if existing:
                conn.close()
                self.send_html(render_register("Email is already registered. Please login.", "danger"), 400)
                return

            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cur.execute("""
                INSERT INTO users (name, email, password_hash, role, roll_number, created_at)
                VALUES (?, ?, ?, 'student', ?, ?)
            """, (name, email, hash_password(password), roll, now))
            new_id = cur.lastrowid
            conn.commit()
            
            new_user = cur.execute("SELECT * FROM users WHERE id = ?", (new_id,)).fetchone()
            conn.close()

            session_id = create_session(dict(new_user))
            cookie_header = f"session_id={session_id}; Path=/; HttpOnly"
            self.redirect("/student/events", cookie_header)
            return

        if not user:
            self.send_json({"error": "Unauthorized"}, 401)
            return

        if path == "/student/register-event":
            form = self.parse_body_form()
            event_id = form.get("event_id", [None])[0]
            if not event_id:
                self.redirect("/student/events")
                return

            conn = get_db()
            cur = conn.cursor()
            
            existing = cur.execute("SELECT id FROM registrations WHERE student_id = ? AND event_id = ?",
                                   (user["user_id"], event_id)).fetchone()
            if not existing:
                qr_tok = str(uuid.uuid4())
                now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cur.execute("""
                    INSERT INTO registrations (qr_token, student_id, event_id, registered_at, checked_in)
                    VALUES (?, ?, ?, ?, 0)
                """, (qr_tok, user["user_id"], event_id, now_str))
                conn.commit()
            conn.close()

            self.redirect("/student/my-tickets")
            return

        if user["role"] == "admin":
            if path == "/admin/events/create":
                form = self.parse_body_form()
                title = form.get("title", [""])[0].strip()
                cat = form.get("category", ["Technical"])[0]
                edate = form.get("event_date", [""])[0]
                stime = form.get("start_time", [""])[0]
                venue = form.get("venue", [""])[0].strip()
                cap = int(form.get("capacity", [100])[0])
                desc = form.get("description", [""])[0].strip()
                now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                conn = get_db()
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO events (title, description, category, event_date, start_time, venue, capacity, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (title, desc, cat, edate, stime, venue, cap, now_str))
                conn.commit()
                conn.close()

                self.redirect("/admin/events")
                return

            if path == "/admin/events/delete":
                form = self.parse_body_form()
                event_id = form.get("event_id", [None])[0]
                if event_id:
                    conn = get_db()
                    cur = conn.cursor()
                    cur.execute("DELETE FROM registrations WHERE event_id = ?", (event_id,))
                    cur.execute("DELETE FROM events WHERE id = ?", (event_id,))
                    conn.commit()
                    conn.close()
                self.redirect("/admin/events")
                return

            if path == "/api/check-in":
                data = self.parse_body_json()
                query_val = data.get("query", "").strip()

                if not query_val:
                    self.send_json({"status": "error", "message": "Empty scan query."})
                    return

                conn = get_db()
                cur = conn.cursor()

                reg = None
                if query_val.isdigit():
                    reg = cur.execute("""
                        SELECT r.*, u.name as student_name, u.roll_number, e.title as event_title
                        FROM registrations r
                        JOIN users u ON r.student_id = u.id
                        JOIN events e ON r.event_id = e.id
                        WHERE r.id = ?
                    """, (int(query_val),)).fetchone()

                if not reg:
                    reg = cur.execute("""
                        SELECT r.*, u.name as student_name, u.roll_number, e.title as event_title
                        FROM registrations r
                        JOIN users u ON r.student_id = u.id
                        JOIN events e ON r.event_id = e.id
                        WHERE r.qr_token = ?
                    """, (query_val,)).fetchone()

                if not reg:
                    conn.close()
                    self.send_json({
                        "status": "error",
                        "message": f"No registration matching '{query_val}' found."
                    })
                    return

                if reg["checked_in"] == 1:
                    conn.close()
                    self.send_json({
                        "status": "warning",
                        "message": "Already checked in!",
                        "reg_id": reg["id"],
                        "student_name": reg["student_name"],
                        "roll_number": reg["roll_number"],
                        "event_title": reg["event_title"],
                        "checkin_time": reg["checkin_time"]
                    })
                    return

                now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cur.execute("""
                    UPDATE registrations 
                    SET checked_in = 1, checkin_time = ? 
                    WHERE id = ?
                """, (now_str, reg["id"]))
                conn.commit()
                conn.close()

                self.send_json({
                    "status": "success",
                    "message": "Check-in successful!",
                    "reg_id": reg["id"],
                    "student_name": reg["student_name"],
                    "roll_number": reg["roll_number"],
                    "event_title": reg["event_title"],
                    "checkin_time": now_str
                })
                return

            if path == "/api/demo-data":
                load_demo_data()
                self.send_json({"status": "ok"})
                return

            if path == "/api/reset-data":
                reset_all_data()
                self.send_json({"status": "ok"})
                return

        self.send_json({"error": "Endpoint not found"}, 404)

    def handle_export_csv(self, query):
        event_id = query.get("event_id", [None])[0]
        if not event_id:
            self.send_html("Event ID required", 400)
            return

        conn = get_db()
        cur = conn.cursor()
        event = cur.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
        if not event:
            conn.close()
            self.send_html("Event not found", 404)
            return

        attendees = cur.execute("""
            SELECT r.id as reg_id, u.name, u.roll_number, u.email, r.checked_in, r.checkin_time, r.registered_at
            FROM registrations r
            JOIN users u ON r.student_id = u.id
            WHERE r.event_id = ?
            ORDER BY u.roll_number ASC
        """, (event_id,)).fetchall()
        conn.close()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Reg ID", "Student Name", "Roll Number", "Email", "Status", "Check-In Time", "Registered Date"])

        for a in attendees:
            status = "Attended" if a["checked_in"] else "Absent"
            writer.writerow([
                a["reg_id"],
                a["name"],
                a["roll_number"],
                a["email"],
                status,
                a["checkin_time"] or "",
                a["registered_at"]
            ])

        csv_data = output.getvalue()
        filename = f"attendance_event_{event_id}_{event['title'][:20].replace(' ', '_')}.csv"

        self.send_response(200)
        self.send_header("Content-Type", "text/csv; charset=utf-8")
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.end_headers()
        self.wfile.write(csv_data.encode("utf-8"))


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

def main():
    init_db()
    print("=" * 70)
    print(" EventEase - College Event Registration & Check-In System")
    print("=" * 70)
    print(f" * Server running on: http://{HOST}:{PORT}")
    print(f" * Admin credentials:  admin@collegename.edu / admin123")
    print(f" * Student credentials: student@collegename.edu / student123")
    print(f" * Database file:      {os.path.abspath(DB_FILE)}")
    print("=" * 70)
    print(" Press Ctrl+C to stop the server.")

    try:
        webbrowser.open(f"http://{HOST}:{PORT}")
    except Exception:
        pass

    server = ThreadedHTTPServer((HOST, PORT), EventEaseHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping EventEase server. Goodbye!")
        server.server_close()

if __name__ == "__main__":
    main()
