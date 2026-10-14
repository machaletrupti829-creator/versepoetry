import os
import random
import secrets
import mysql.connector
import hashlib
import io
import base64

from datetime import datetime, timedelta
from functools import wraps

import qrcode

from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, session, jsonify, send_from_directory, abort
)

from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename


# ==================================================
# FLASK CONFIGURATION
# ==================================================

app = Flask(
    __name__,
    static_folder="statics",
    static_url_path="/static"
)

app.secret_key = os.environ.get(
    "FLASK_SECRET_KEY",
    "change-this-secret-key-for-your-project"
)

app.config.update(
    MAIL_SERVER="smtp.gmail.com",
    MAIL_PORT=587,
    MAIL_USE_TLS=True,
    MAIL_USE_SSL=False,
    MAIL_USERNAME=os.environ.get("MAIL_USERNAME", ""),
    MAIL_PASSWORD=os.environ.get("MAIL_PASSWORD", ""),
    MAIL_DEFAULT_SENDER=os.environ.get("MAIL_USERNAME", "")
)

mail = Mail(app)

# MySQL configuration. Set MYSQL_PASSWORD in your terminal before running the app.
MYSQL_CONFIG = {
    "host": os.environ.get("MYSQL_HOST", "localhost"),
    "user": os.environ.get("MYSQL_USER", "root"),
    "password": os.environ.get("MYSQL_PASSWORD", ""),
    "database": os.environ.get("MYSQL_DATABASE", "versepoetry_db"),
    "autocommit": False,
}

UPLOAD_FOLDER = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "uploads"
)
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ALLOWED_POEM_EXTENSIONS = {"txt", "pdf", "docx"}
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10 MB per request

OTP_EXPIRY_MINUTES = 5
QR_EXPIRY_MINUTES = 3
OTP_MAX_ATTEMPTS = 5

# Admin registration key
ADMIN_SETUP_KEY = os.environ.get(
    "ADMIN_SETUP_KEY",
    "VersePoetryAdmin2026"
)


# ==================================================
# DATABASE
# ==================================================

class MySQLDatabase:
    """Small compatibility wrapper so existing db.execute(...) calls keep working."""

    def __init__(self):
        self.connection = mysql.connector.connect(**MYSQL_CONFIG)
        self.cursor = self.connection.cursor(dictionary=True)

    def execute(self, query, params=None):
        # Convert SQLite parameter markers to MySQL Connector markers.
        query = query.replace("?", "%s")
        # Keep the existing code's generated-ID query working with MySQL.
        if "last_insert_rowid()" in query.lower():
            query = "SELECT LAST_INSERT_ID() AS last_insert_rowid"
        self.cursor.execute(query, params or ())
        return self.cursor

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            if exc_type is None:
                self.connection.commit()
            else:
                self.connection.rollback()
        finally:
            self.cursor.close()
            self.connection.close()
        return False


def get_db():
    return MySQLDatabase()


# ==================================================
# HELPER FUNCTIONS
# ==================================================

def hash_value(value):
    return hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()


def admin_required(view):

    @wraps(view)
    def wrapped(*args, **kwargs):

        if "admin_id" not in session:
            flash("Please log in as Admin first.", "error")
            return redirect(url_for("admin_dashboard"))

        return view(*args, **kwargs)

    return wrapped


def login_required(view):

    @wraps(view)
    def wrapped(*args, **kwargs):

        if "user_id" not in session:
            flash("Please log in first.", "error")
            return redirect(url_for("login"))

        return view(*args, **kwargs)

    return wrapped


def send_otp_email(email, otp):

    message = Message(
        subject="VersePoetry Login OTP",
        recipients=[email],
        body=(
            f"Your VersePoetry OTP is {otp}.\n\n"
            f"This OTP expires in {OTP_EXPIRY_MINUTES} minutes."
        )
    )

    mail.send(message)


def clear_otp_session():

    for key in (
        "pending_otp",
        "pending_email",
        "pending_name",
        "otp_created_at",
        "otp_attempts"
    ):
        session.pop(key, None)


def get_current_user():

    user_id = session.get("user_id")

    if not user_id:
        return None

    with get_db() as db:

        return db.execute(
            """
            SELECT user_id, name, email, registration_date
            FROM users
            WHERE user_id = ?
            """,
            (user_id,)
        ).fetchone()


def create_qr_image(url):

    qr = qrcode.QRCode(
        box_size=8,
        border=3
    )

    qr.add_data(url)
    qr.make(fit=True)

    image = qr.make_image(
        fill_color="black",
        back_color="white"
    )

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")

    return (
        "data:image/png;base64,"
        + base64.b64encode(
            buffer.getvalue()
        ).decode("ascii")
    )


# ==================================================
# HOME PAGE
# ==================================================

@app.route("/")
@app.route("/index")
def index():
    return render_template("index.html")


# ==================================================
# ABOUT PAGE
# ==================================================

@app.route("/about")
def about():
    return render_template("about.html")


# ==================================================
# CONTACT PAGE
# ==================================================

@app.route("/contact", methods=["GET", "POST"])
def contact():

    if request.method == "POST":

        name = request.form.get(
            "name", ""
        ).strip()

        email = request.form.get(
            "email", ""
        ).strip().lower()

        message = request.form.get(
            "message", ""
        ).strip()

        if not name or not email or not message:

            flash(
                "Please fill in all fields.",
                "error"
            )

            return redirect(url_for("contact"))

        with get_db() as db:

            db.execute(
                """
                INSERT INTO contact_messages
                (name, email, message, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    name,
                    email,
                    message,
                    datetime.now().strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )
                )
            )

        flash(
            "Your message has been saved successfully.",
            "success"
        )

        return redirect(url_for("contact"))

    return render_template("contact.html")


# ==================================================
# ADMIN DASHBOARD / LOGIN PAGE
# ==================================================

@app.route("/admin", methods=["GET"])
def admin_dashboard():

    if "admin_id" in session:
        return redirect(url_for("admin_panel"))

    with get_db() as db:

        admin_exists = db.execute(
            "SELECT admin_id FROM admins LIMIT 1"
        ).fetchone()

    registration_open = (
        admin_exists is None and bool(ADMIN_SETUP_KEY)
    )

    setup_key_configured = (
        admin_exists is not None or bool(ADMIN_SETUP_KEY)
    )

    return render_template(
        "admin_login.html",
        registration_open=registration_open,
        setup_key_configured=setup_key_configured,
        logged_in=False
    )


# ==================================================
# ADMIN REGISTRATION
# ==================================================

@app.route("/admin/register", methods=["POST"])
def admin_register():

    admin_name = request.form.get(
        "admin_name", ""
    ).strip()

    username = request.form.get(
        "username", ""
    ).strip()

    password = request.form.get(
        "password", ""
    )

    confirm_password = request.form.get(
        "confirm_password", ""
    )

    setup_key = request.form.get(
        "setup_key", ""
    )

    if not ADMIN_SETUP_KEY:

        flash(
            "Admin registration is disabled.",
            "error"
        )

        return redirect(url_for("admin_dashboard"))

    if not secrets.compare_digest(
        setup_key, ADMIN_SETUP_KEY
    ):

        flash(
            "Invalid admin setup key.",
            "error"
        )

        return redirect(url_for("admin_dashboard"))

    if not admin_name or not username or not password:

        flash(
            "Please fill in all fields.",
            "error"
        )

        return redirect(url_for("admin_dashboard"))

    if len(password) < 8:

        flash(
            "Password must contain at least 8 characters.",
            "error"
        )

        return redirect(url_for("admin_dashboard"))

    if password != confirm_password:

        flash(
            "Passwords do not match.",
            "error"
        )

        return redirect(url_for("admin_dashboard"))

    with get_db() as db:

        existing_admin = db.execute(
            "SELECT admin_id FROM admins LIMIT 1"
        ).fetchone()

        if existing_admin:

            flash(
                "Admin registration is already closed.",
                "error"
            )

            return redirect(url_for("admin_dashboard"))

        db.execute(
            """
            INSERT INTO admins
            (admin_name, username, password_hash, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                admin_name,
                username,
                generate_password_hash(password),
                datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            )
        )

    flash(
        "Admin account created successfully. Please log in.",
        "success"
    )

    return redirect(url_for("admin_dashboard"))


# ==================================================
# ADMIN LOGIN
# ==================================================

@app.route("/admin/login", methods=["POST"])
def admin_login():

    username = request.form.get(
        "username", ""
    ).strip()

    password = request.form.get(
        "password", ""
    )

    with get_db() as db:

        admin = db.execute(
            """
            SELECT admin_id, admin_name, password_hash
            FROM admins
            WHERE username = ?
            """,
            (username,)
        ).fetchone()

    if not admin or not check_password_hash(
        admin["password_hash"], password
    ):

        flash(
            "Invalid admin username or password.",
            "error"
        )

        return redirect(url_for("admin_dashboard"))

    session.clear()

    session["admin_id"] = admin["admin_id"]
    session["admin_name"] = admin["admin_name"]

    return redirect(url_for("admin_panel"))


# ==================================================
# ADMIN PANEL
# ==================================================

@app.route("/admin/panel")
@admin_required
def admin_panel():

    with get_db() as db:

        pending_poems = db.execute("""
            SELECT
                poems.poem_id AS id,
                poems.title,
                poems.content,
                poems.file_path,
                poems.created_at,
                users.name AS author_name
            FROM poems
            JOIN users
                ON poems.user_id = users.user_id
            WHERE poems.status = 'Pending'
            ORDER BY poems.poem_id DESC
        """).fetchall()

        approved_poems = db.execute("""
            SELECT
                poems.poem_id AS id,
                poems.title,
                poems.content,
                poems.file_path,
                poems.created_at,
                users.name AS author_name
            FROM poems
            JOIN users ON poems.user_id = users.user_id
            WHERE poems.status = 'Approved'
            ORDER BY poems.poem_id DESC
        """).fetchall()

        rejected_poems = db.execute("""
            SELECT
                poems.poem_id AS id,
                poems.title,
                poems.content,
                poems.file_path,
                poems.created_at,
                users.name AS author_name
            FROM poems
            JOIN users ON poems.user_id = users.user_id
            WHERE poems.status = 'Rejected'
            ORDER BY poems.poem_id DESC
        """).fetchall()

    return render_template(
        "admin_dashboard.html",
        logged_in=True,
        admin_name=session.get("admin_name", "Admin"),
        pending_poems=pending_poems,
        approved_poems=approved_poems,
        rejected_poems=rejected_poems,
        pending_count=len(pending_poems),
        approved_count=len(approved_poems),
        rejected_count=len(rejected_poems)
    )


# ==================================================
# VIEW UPLOADED POEM FILE (ADMIN ONLY)
# ==================================================

@app.route("/admin/poem-file/<int:poem_id>")
@admin_required
def view_poem_file(poem_id):
    with get_db() as db:
        poem = db.execute(
            "SELECT file_path FROM poems WHERE poem_id = ?",
            (poem_id,)
        ).fetchone()

    if poem is None or not poem["file_path"]:
        flash("No uploaded file was found for this poem.", "error")
        return redirect(url_for("admin_panel"))

    # Only serve a filename stored in the database, never a user-supplied path.
    filename = os.path.basename(poem["file_path"])
    if not filename or secure_filename(filename) != filename:
        abort(404)

    full_path = os.path.join(UPLOAD_FOLDER, filename)
    if not os.path.isfile(full_path):
        flash("The uploaded file is missing from the uploads folder.", "error")
        return redirect(url_for("admin_panel"))

    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    # Browsers can display PDF/TXT inline. DOCX is downloaded to open in Word.
    return send_from_directory(
        UPLOAD_FOLDER,
        filename,
        as_attachment=(extension == "docx"),
        download_name=filename
    )


# ==================================================
# ADMIN POEM APPROVAL / REJECTION
# ==================================================

@app.route(
    "/admin/review/<int:poem_id>",
    methods=["POST"]
)
@admin_required
def review_poem(poem_id):

    action = request.form.get(
        "action", ""
    ).strip().lower()

    if action not in ("approve", "reject"):

        flash(
            "Invalid action.",
            "error"
        )

        return redirect(url_for("admin_panel"))

    new_status = (
        "Approved"
        if action == "approve"
        else "Rejected"
    )

    with get_db() as db:

        poem = db.execute(
            "SELECT poem_id FROM poems WHERE poem_id = ?",
            (poem_id,)
        ).fetchone()

        if poem is None:

            flash(
                "Poem not found.",
                "error"
            )

            return redirect(url_for("admin_panel"))

        db.execute(
            """
            UPDATE poems
            SET status = ?
            WHERE poem_id = ?
            """,
            (new_status, poem_id)
        )

    flash(
        f"Poem {new_status.lower()} successfully.",
        "success"
    )

    return redirect(url_for("admin_panel"))


# ==================================================
# ADMIN EDIT POEM
# ==================================================

@app.route("/admin/edit-poem/<int:poem_id>", methods=["GET", "POST"])
@admin_required
def edit_poem(poem_id):
    with get_db() as db:
        poem = db.execute(
            "SELECT poem_id AS id, title, content, status FROM poems WHERE poem_id = ?",
            (poem_id,)
        ).fetchone()

        if poem is None:
            flash("Poem not found.", "error")
            return redirect(url_for("admin_panel"))

        if request.method == "POST":
            title = request.form.get("title", "").strip()
            content = request.form.get("content", "").strip()
            if not title or not content:
                flash("Title and poem content are required.", "error")
                return render_template("edit_poem.html", poem=poem)

            db.execute(
                "UPDATE poems SET title = ?, content = ? WHERE poem_id = ?",
                (title, content, poem_id)
            )

        else:
            return render_template("edit_poem.html", poem=poem)

    flash("Poem updated successfully.", "success")
    return redirect(url_for("admin_panel"))


# ==================================================
# ADMIN LOGOUT
# ==================================================

@app.route("/admin/logout", methods=["POST"])
@admin_required
def admin_logout():

    session.clear()

    flash(
        "Admin logged out successfully.",
        "success"
    )

    return redirect(url_for("admin_dashboard"))


# ==================================================
# PHONE REGISTRATION / LOGIN
# ==================================================

def create_remembered_device(user_id):
    """Create a random token that remembers this browser for future QR scans."""
    token = secrets.token_urlsafe(32)
    with get_db() as db:
        db.execute(
            "INSERT INTO remembered_devices (user_id, token_hash, created_at) VALUES (?, ?, ?)",
            (user_id, hash_value(token), datetime.utcnow().isoformat())
        )
    return token


def approve_pending_qr_for_user(user_id):
    """If login/register was opened from a QR scan, approve that laptop request."""
    token = session.pop("pending_qr_token", None)
    if not token:
        return
    token_hash = hash_value(token)
    with get_db() as db:
        row = db.execute(
            "SELECT request_id, expires_at, status FROM qr_login_requests WHERE token_hash = ?",
            (token_hash,)
        ).fetchone()
        if not row or row["status"] != "pending":
            return
        try:
            expiry = datetime.fromisoformat(row["expires_at"])
        except (ValueError, TypeError):
            return
        if datetime.utcnow() <= expiry:
            db.execute(
                "UPDATE qr_login_requests SET status = 'approved', user_id = ? WHERE request_id = ? AND status = 'pending'",
                (user_id, row["request_id"])
            )


def phone_auth_redirect(user_id):
    pending_qr = session.get("pending_qr_token")
    pending_flashes = session.get("_flashes", [])
    session.clear()
    session["user_id"] = user_id
    if pending_qr:
        session["pending_qr_token"] = pending_qr
    if pending_flashes:
        session["_flashes"] = pending_flashes
    device_token = create_remembered_device(user_id)
    approve_pending_qr_for_user(user_id)
    response = redirect(url_for("poem_submission"))
    response.set_cookie(
        "vp_device_token", device_token,
        max_age=60 * 60 * 24 * 365,
        httponly=True, samesite="Lax",
        secure=request.is_secure
    )
    return response


@app.route("/register", methods=["POST"])
def register():
    name = request.form.get("name", "").strip()
    contact_number = request.form.get("contact_number", "").strip()
    password = request.form.get("password", "")
    confirm_password = request.form.get("confirm_password", "")

    if not name or not contact_number or not password:
        flash("Please fill in all registration fields.", "error")
        return redirect(url_for("login"))
    if not contact_number.isdigit() or len(contact_number) != 10:
        flash("Enter a valid 10-digit contact number.", "error")
        return redirect(url_for("login"))
    if len(password) < 8:
        flash("Password must contain at least 8 characters.", "error")
        return redirect(url_for("login"))
    if password != confirm_password:
        flash("Passwords do not match.", "error")
        return redirect(url_for("login"))

    # Existing database requires email; use a unique internal placeholder for phone-only accounts.
    internal_email = f"phone_{contact_number}@users.versepoetry.local"
    try:
        with get_db() as db:
            existing = db.execute(
                "SELECT user_id FROM users WHERE contact_number = ?", (contact_number,)
            ).fetchone()
            if existing:
                flash("This contact number is already registered. Please log in.", "error")
                return redirect(url_for("login"))
            db.execute(
                "INSERT INTO users (name, email, registration_date, contact_number, password_hash) VALUES (?, ?, ?, ?, ?)",
                (name, internal_email, datetime.now().strftime("%Y-%m-%d"),
                 contact_number, generate_password_hash(password))
            )
            user_id = db.execute("SELECT last_insert_rowid()").fetchone()["last_insert_rowid"]
    except mysql.connector.IntegrityError:
        flash("This contact number is already registered. Please log in.", "error")
        return redirect(url_for("login"))

    # Preserve the QR token when the form was opened on a phone by scanning a QR code.
    pending_qr = session.get("pending_qr_token")
    session.clear()
    if pending_qr:
        session["pending_qr_token"] = pending_qr
    flash("Account created successfully. Welcome to VersePoetry!", "success")
    return phone_auth_redirect(user_id)


@app.route("/phone-login", methods=["POST"])
def phone_login():
    contact_number = request.form.get("contact_number", "").strip()
    password = request.form.get("password", "")

    if not contact_number or not password:
        flash("Enter your contact number and password.", "error")
        return redirect(url_for("login"))

    with get_db() as db:
        user = db.execute(
            "SELECT user_id, password_hash FROM users WHERE contact_number = ?",
            (contact_number,)
        ).fetchone()

    if not user or not user["password_hash"] or not check_password_hash(user["password_hash"], password):
        flash("Incorrect contact number or password.", "error")
        return redirect(url_for("login"))

    pending_qr = session.get("pending_qr_token")
    session.clear()
    if pending_qr:
        session["pending_qr_token"] = pending_qr
    flash("Login successful.", "success")
    return phone_auth_redirect(user["user_id"])


# ==================================================
# USER LOGIN - EMAIL OTP
# ==================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "GET":
        return render_template("login.html")

    email = request.form.get(
        "email", ""
    ).strip().lower()

    if not email:

        flash(
            "Please enter your email address.",
            "error"
        )

        return redirect(url_for("login"))

    if (
        not app.config["MAIL_USERNAME"]
        or not app.config["MAIL_PASSWORD"]
    ):

        flash(
            "Email configuration is missing. "
            "Set MAIL_USERNAME and MAIL_PASSWORD.",
            "error"
        )

        return redirect(url_for("login"))

    otp = f"{random.SystemRandom().randint(0, 999999):06d}"

    session["pending_email"] = email
    session["pending_otp"] = otp
    session["otp_created_at"] = datetime.utcnow().isoformat()
    session["otp_attempts"] = 0

    try:
        send_otp_email(email, otp)

    except Exception:

        app.logger.exception(
            "Failed to send login OTP"
        )

        clear_otp_session()

        flash(
            "OTP email could not be sent. Check Gmail settings.",
            "error"
        )

        return redirect(url_for("login"))

    flash(
        "OTP sent. Check your inbox and spam folder.",
        "success"
    )

    return redirect(url_for("otp_verification"))


# ==================================================
# OTP VERIFICATION
# ==================================================

@app.route(
    "/otp-verification",
    methods=["GET", "POST"]
)
def otp_verification():

    if (
        not session.get("pending_email")
        or not session.get("pending_otp")
    ):

        flash(
            "Please request an OTP first.",
            "error"
        )

        return redirect(url_for("login"))

    if request.method == "GET":

        return render_template(
            "otp_verification.html",
            email=session["pending_email"]
        )

    entered_otp = request.form.get(
        "otp", ""
    ).strip()

    try:

        created = datetime.fromisoformat(
            session.get("otp_created_at", "")
        )

    except (ValueError, TypeError):

        created = datetime.min

    if datetime.utcnow() - created > timedelta(
        minutes=OTP_EXPIRY_MINUTES
    ):

        clear_otp_session()

        flash(
            "OTP expired. Please request a new OTP.",
            "error"
        )

        return redirect(url_for("login"))

    if session.get("otp_attempts", 0) >= OTP_MAX_ATTEMPTS:

        clear_otp_session()

        flash(
            "Too many attempts. Request a new OTP.",
            "error"
        )

        return redirect(url_for("login"))

    if not secrets.compare_digest(
        entered_otp,
        session["pending_otp"]
    ):

        session["otp_attempts"] += 1

        flash(
            "Incorrect OTP. Please try again.",
            "error"
        )

        return render_template(
            "otp_verification.html",
            email=session["pending_email"]
        )

    email = session["pending_email"]

    with get_db() as db:

        user = db.execute(
            "SELECT user_id FROM users WHERE email = ?",
            (email,)
        ).fetchone()

        if user:

            user_id = user["user_id"]

        else:

            db.execute(
                """
                INSERT INTO users
                (name, email, registration_date)
                VALUES (?, ?, ?)
                """,
                (
                    "",
                    email,
                    datetime.now().strftime("%Y-%m-%d")
                )
            )

            user_id = db.execute(
                "SELECT last_insert_rowid()"
            ).fetchone()["last_insert_rowid"]

    session.clear()
    session["user_id"] = user_id

    flash(
        "Email verified successfully.",
        "success"
    )

    return redirect(url_for("poem_submission"))


# ==================================================
# QR LOGIN
# ==================================================

@app.route("/qr-login")
def qr_login():

    token = secrets.token_urlsafe(32)
    token_hash = hash_value(token)

    now = datetime.utcnow()
    expiry = now + timedelta(
        minutes=QR_EXPIRY_MINUTES
    )

    with get_db() as db:

        db.execute(
            """
            INSERT INTO qr_login_requests
            (token_hash, status, created_at, expires_at)
            VALUES (?, 'pending', ?, ?)
            """,
            (
                token_hash,
                now.isoformat(),
                expiry.isoformat()
            )
        )

    phone_url = (
        request.host_url.rstrip("/")
        + url_for("qr_approve", token=token)
    )

    return render_template(
        "qr_login.html",
        qr_data=create_qr_image(phone_url),
        token=token,
        expires_in=QR_EXPIRY_MINUTES
    )


@app.route("/qr-approve/<token>")
def qr_approve(token):

    token_hash = hash_value(token)

    with get_db() as db:

        row = db.execute(
            """
            SELECT *
            FROM qr_login_requests
            WHERE token_hash = ?
            """,
            (token_hash,)
        ).fetchone()

        if not row:
            return "Invalid QR code.", 404

        if row["status"] != "pending":
            return "This QR code has already been used.", 410

        try:

            expiry = datetime.fromisoformat(
                row["expires_at"]
            )

        except (ValueError, TypeError):

            return "Invalid QR expiry.", 410

        if datetime.utcnow() > expiry:

            return (
                "QR code expired. Generate a new one.",
                410
            )

        # Reuse the account remembered by this phone, rather than creating a new QR user.
        device_token = request.cookies.get("vp_device_token", "")
        remembered_user = None
        if device_token:
            remembered_user = db.execute(
                "SELECT user_id FROM remembered_devices WHERE token_hash = ?",
                (hash_value(device_token),)
            ).fetchone()

        if remembered_user:
            db.execute(
                "UPDATE qr_login_requests SET status = 'approved', user_id = ? WHERE token_hash = ? AND status = 'pending'",
                (remembered_user["user_id"], token_hash)
            )
            return redirect(url_for("index"))

    # First-time scan on this phone: ask the user to register or log in.
    # After successful phone login, the pending QR request is approved for that account.
    session["pending_qr_token"] = token
    flash("Please log in or register on this phone to continue QR login.", "info")
    return redirect(url_for("login"))


@app.route("/qr-status/<token>")
def qr_status(token):

    token_hash = hash_value(token)

    with get_db() as db:

        row = db.execute(
            """
            SELECT *
            FROM qr_login_requests
            WHERE token_hash = ?
            """,
            (token_hash,)
        ).fetchone()

        if not row:
            return jsonify(status="expired")

        if datetime.utcnow() > datetime.fromisoformat(
            row["expires_at"]
        ):
            return jsonify(status="expired")

        if row["status"] == "approved" and row["user_id"]:

            user_id = row["user_id"]

            db.execute(
                """
                UPDATE qr_login_requests
                SET status = 'used'
                WHERE token_hash = ? AND status = 'approved'
                """,
                (token_hash,)
            )

            session.clear()
            session["user_id"] = user_id

            return jsonify(
                status="approved",
                redirect=url_for("poem_submission")
            )

        return jsonify(status=row["status"])


# ==================================================
# USER PROFILE
# ==================================================

@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():

    user = get_current_user()

    if user is None:

        session.clear()

        return redirect(url_for("login"))

    if request.method == "POST":

        name = request.form.get(
            "name", ""
        ).strip()

        if not name:

            flash(
                "Please enter your name.",
                "error"
            )

        else:

            with get_db() as db:

                db.execute(
                    """
                    UPDATE users
                    SET name = ?
                    WHERE user_id = ?
                    """,
                    (name, user["user_id"])
                )

            flash(
                "Profile updated successfully.",
                "success"
            )

            return redirect(url_for("profile"))

    user = get_current_user()

    with get_db() as db:

        counts = db.execute(
            """
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN status = 'Pending' THEN 1 ELSE 0 END) AS pending,
                SUM(CASE WHEN status = 'Approved' THEN 1 ELSE 0 END) AS approved,
                SUM(CASE WHEN status = 'Rejected' THEN 1 ELSE 0 END) AS rejected
            FROM poems
            WHERE user_id = ?
            """,
            (user["user_id"],)
        ).fetchone()

        poems = db.execute(
            """
            SELECT poem_id, title, status, created_at, file_path
            FROM poems
            WHERE user_id = ?
            ORDER BY poem_id DESC
            """,
            (user["user_id"],)
        ).fetchall()

    poem_counts = {
        key: counts[key] or 0
        for key in ("total", "pending", "approved", "rejected")
    }

    return render_template(
        "profile.html",
        user=user,
        poems=poems,
        poem_counts=poem_counts
    )


# ==================================================
# POEM SUBMISSION
# ==================================================

@app.route("/poem-submission", methods=["GET", "POST"])
@login_required
def poem_submission():

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        content = request.form.get("content", "").strip()
        poem_file = request.files.get("poem_file")

        if not title:
            flash("Please enter the poem title.", "error")
            return redirect(url_for("poem_submission"))

        file_path = None

        if poem_file and poem_file.filename:
            original_name = secure_filename(poem_file.filename)

            if not original_name or "." not in original_name:
                flash("Please choose a valid TXT, PDF or DOCX file.", "error")
                return redirect(url_for("poem_submission"))

            extension = original_name.rsplit(".", 1)[1].lower()
            if extension not in ALLOWED_POEM_EXTENSIONS:
                flash("Upload only TXT, PDF or DOCX files.", "error")
                return redirect(url_for("poem_submission"))

            unique_filename = f"{secrets.token_hex(8)}_{original_name}"
            poem_file.save(os.path.join(UPLOAD_FOLDER, unique_filename))
            file_path = unique_filename

        if not content and not file_path:
            flash("Please enter your poem or upload a poem file.", "error")
            return redirect(url_for("poem_submission"))

        with get_db() as db:
            db.execute(
                """
                INSERT INTO poems
                    (user_id, title, content, status, created_at, file_path)
                VALUES (?, ?, ?, 'Pending', ?, ?)
                """,
                (
                    session["user_id"],
                    title,
                    content,
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    file_path
                )
            )

        flash("Your poem was submitted successfully.", "success")
        return redirect(url_for("poem_submission"))

    with get_db() as db:
        poems = db.execute(
            """
            SELECT poem_id, title, status, created_at
            FROM poems
            WHERE user_id = ?
            ORDER BY poem_id DESC
            """,
            (session["user_id"],)
        ).fetchall()

    return render_template("poem_submission.html", poems=poems)


# ==================================================
# USER LOGOUT
# ==================================================

@app.route("/logout")
def logout():

    session.clear()

    flash(
        "You have been logged out.",
        "success"
    )

    return redirect(url_for("login"))


# ==================================================
# START FLASK SERVER
# ==================================================

@app.errorhandler(413)
def file_too_large(_error):
    return "Uploaded file is too large. Maximum size is 10 MB.", 413


if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )