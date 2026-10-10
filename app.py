import os
import sqlite3
import datetime
import jwt
from functools import wraps
from flask import Flask, request, jsonify, g

app = Flask(__name__)
DB = "tracker.db"
STATUSES = ["Applied", "Interview", "Offer", "Rejected"]

# must be the SAME value the auth service signs with
JWT_SECRET = os.environ.get("JWT_SECRET")
if not JWT_SECRET:
    raise SystemExit("Set JWT_SECRET first (same value as auth-service).")


def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            company TEXT NOT NULL,
            role TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Applied',
            applied_date TEXT NOT NULL,
            notes TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_applications_user ON applications(user_id)")
    conn.commit()
    conn.close()


def row_to_dict(row):
    return {
        "id": row["id"],
        "company": row["company"],
        "role": row["role"],
        "status": row["status"],
        "applied_date": row["applied_date"],
        "notes": row["notes"],
    }


def token_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return jsonify(error="Missing token."), 401
        try:
            claims = jwt.decode(
                header[7:], JWT_SECRET, algorithms=["HS256"],
                options={"require": ["exp", "sub"]},
            )
        except jwt.InvalidTokenError:       # bad signature, expired, malformed
            return jsonify(error="Invalid or expired token."), 401

        # a temporary 2FA token must never open the tracker
        if claims.get("purpose") != "access":
            return jsonify(error="Invalid or expired token."), 401

        g.user_id = int(claims["sub"])
        g.email = claims["email"]
        return f(*args, **kwargs)
    return wrapper


@app.route("/api/me")
@token_required
def me():
    return jsonify(user_id=g.user_id, email=g.email)


@app.route("/api/applications", methods=["POST"])
@token_required
def create_application():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        data = {}

    company = str(data.get("company", "")).strip()
    role = str(data.get("role", "")).strip()
    status = str(data.get("status", "Applied")).strip()
    notes = str(data.get("notes", "")).strip()
    applied_date = str(data.get("applied_date", "")).strip() or datetime.date.today().isoformat()

    if not company or not role:
        return jsonify(error="Company and role are required."), 400
    if len(company) > 100 or len(role) > 100:
        return jsonify(error="Company and role must be 100 characters or fewer."), 400
    if status not in STATUSES:
        return jsonify(error="Status must be one of: " + ", ".join(STATUSES)), 400
    if len(notes) > 1000:
        return jsonify(error="Notes must be 1000 characters or fewer."), 400
    try:
        datetime.date.fromisoformat(applied_date)
    except ValueError:
        return jsonify(error="applied_date must look like 2026-10-12."), 400

    # the owner always comes from the verified token, never from the request body
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO applications (user_id, company, role, status, applied_date, notes, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (g.user_id, company, role, status, applied_date, notes,
         datetime.datetime.now(datetime.timezone.utc).isoformat()),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM applications WHERE id = ?", (cur.lastrowid,)).fetchone()
    conn.close()
    return jsonify(row_to_dict(row)), 201


@app.route("/api/applications")
@token_required
def list_applications():
    status = request.args.get("status")
    query = "SELECT * FROM applications WHERE user_id = ?"
    params = [g.user_id]

    if status:
        if status not in STATUSES:
            return jsonify(error="Status must be one of: " + ", ".join(STATUSES)), 400
        query += " AND status = ?"
        params.append(status)

    query += " ORDER BY applied_date DESC, id DESC"
    conn = get_db()
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return jsonify([row_to_dict(r) for r in rows])
@app.route("/api/applications/<int:app_id>", methods=["PATCH"])
@token_required
def update_application(app_id):
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not data:
        return jsonify(error="Send at least one field to update."), 400

    # only these five fields can ever be changed; anything else (like user_id) is ignored
    fields = {}
    if "company" in data:
        v = str(data["company"]).strip()
        if not v or len(v) > 100:
            return jsonify(error="Company must be 1 to 100 characters."), 400
        fields["company"] = v
    if "role" in data:
        v = str(data["role"]).strip()
        if not v or len(v) > 100:
            return jsonify(error="Role must be 1 to 100 characters."), 400
        fields["role"] = v
    if "status" in data:
        v = str(data["status"]).strip()
        if v not in STATUSES:
            return jsonify(error="Status must be one of: " + ", ".join(STATUSES)), 400
        fields["status"] = v
    if "applied_date" in data:
        v = str(data["applied_date"]).strip()
        try:
            datetime.date.fromisoformat(v)
        except ValueError:
            return jsonify(error="applied_date must look like 2026-10-12."), 400
        fields["applied_date"] = v
    if "notes" in data:
        v = str(data["notes"]).strip()
        if len(v) > 1000:
            return jsonify(error="Notes must be 1000 characters or fewer."), 400
        fields["notes"] = v

    if not fields:
        return jsonify(error="No valid fields to update."), 400

    # the column names come from the fixed list above, never from the user's text
    set_clause = ", ".join(f"{col} = ?" for col in fields)
    params = list(fields.values()) + [app_id, g.user_id]

    conn = get_db()
    cur = conn.execute(
        f"UPDATE applications SET {set_clause} WHERE id = ? AND user_id = ?", params
    )
    conn.commit()
    if cur.rowcount == 0:
        conn.close()
        return jsonify(error="Application not found."), 404
    row = conn.execute("SELECT * FROM applications WHERE id = ?", (app_id,)).fetchone()
    conn.close()
    return jsonify(row_to_dict(row))


@app.route("/api/applications/<int:app_id>", methods=["DELETE"])
@token_required
def delete_application(app_id):
    conn = get_db()
    cur = conn.execute(
        "DELETE FROM applications WHERE id = ? AND user_id = ?", (app_id, g.user_id)
    )
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        return jsonify(error="Application not found."), 404
    return jsonify(message="Deleted.")


if __name__ == "__main__":
    init_db()
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1", port=5002)