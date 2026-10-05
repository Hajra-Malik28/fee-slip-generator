import os
from datetime import date
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import check_password_hash

from database import init_db, get_connection

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-key")

# Make sure the tables exist (also runs when started with gunicorn)
init_db()


def format_date(iso_text):
    d = date.fromisoformat(iso_text)
    return f"{d.day} {d.strftime('%b')}, {d.year}"


ONES = [
    "", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight",
    "Nine", "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen",
    "Sixteen", "Seventeen", "Eighteen", "Nineteen",
]

TENS = [
    "", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy",
    "Eighty", "Ninety",
]


def below_thousand(n):
    words = []

    if n >= 100:
        words.append(ONES[n // 100] + " Hundred")
        n %= 100

    if n >= 20:
        t = TENS[n // 10]

        if n % 10:
            t += " " + ONES[n % 10]

        words.append(t)

    elif n > 0:
        words.append(ONES[n])

    return " ".join(words)


def amount_in_words(n):
    if n == 0:
        return "Zero Rupees Only"

    parts = []

    for value, name in [
        (10000000, "Crore"),
        (100000, "Lakh"),
        (1000, "Thousand"),
    ]:
        if n >= value:
            parts.append(below_thousand(n // value) + " " + name)
            n %= value

    if n > 0:
        parts.append(below_thousand(n))

    return " ".join(parts) + " Rupees Only"


def login_required(view_function):
    @wraps(view_function)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return view_function(*args, **kwargs)

    return wrapped_view


@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("home"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            flash("Please enter both username and password.")
            return render_template("login.html")

        conn = get_connection()

        user = conn.execute(
            """
            SELECT id, username, password_hash, role
            FROM users
            WHERE username = ?
            """,
            (username,),
        ).fetchone()

        conn.close()

        if user is None:
            flash("Incorrect username or password.")
            return render_template("login.html")

        if not check_password_hash(user["password_hash"], password):
            flash("Incorrect username or password.")
            return render_template("login.html")

        session.clear()
        session["user_id"] = user["id"]
        session["username"] = user["username"]
        session["role"] = user["role"]

        return redirect(url_for("home"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def home():
    return render_template("form.html")


@app.route("/generate", methods=["POST"])
@login_required
def generate():
    student_name = request.form["student_name"].strip()
    father_name = request.form["father_name"].strip()
    reg_no = request.form["reg_no"].strip()
    degree = request.form["degree"]
    semester = request.form["semester"]
    batch = request.form["batch"].strip()
    installment = request.form["installment"]
    fee_type = request.form["fee_type"]

    tuition_fee = int(request.form["tuition_fee"])
    security_fee = int(request.form["security_fee"])
    other_fee = int(request.form.get("other_fee") or 0)

    total_fee = tuition_fee + security_fee + other_fee

    issue_date = date.today()
    due_date = date.fromisoformat(request.form["due_date"])

    if due_date <= issue_date:
        return (
            "The due date must be after today. "
            f"<a href='{url_for('home')}'>Go back</a>",
            400,
        )

    conn = get_connection()

    cursor = conn.execute(
        """
        INSERT INTO challans (
            student_name,
            father_name,
            reg_no,
            degree,
            semester,
            batch,
            installment,
            fee_type,
            tuition_fee,
            security_fee,
            other_fee,
            total_fee,
            issue_date,
            due_date,
            created_by
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            student_name,
            father_name,
            reg_no,
            degree,
            semester,
            batch,
            installment,
            fee_type,
            tuition_fee,
            security_fee,
            other_fee,
            total_fee,
            issue_date.isoformat(),
            due_date.isoformat(),
            session.get("username"),
        ),
    )

    challan_no = cursor.lastrowid

    conn.commit()
    conn.close()

    return redirect(url_for("slip", challan_no=challan_no))


@app.route("/challans")
@login_required
def challans():
    if session.get("role") != "admin":
        return "You are not allowed to view this page.", 403

    q = request.args.get("q", "").strip()

    conn = get_connection()

    if q:
        like = f"%{q}%"
        rows = conn.execute(
            """
            SELECT challan_no, student_name, father_name, reg_no, degree,
                   semester, installment, fee_type, total_fee,
                   issue_date, due_date, created_by
            FROM challans
            WHERE student_name LIKE ?
               OR reg_no LIKE ?
               OR CAST(challan_no AS TEXT) = ?
            ORDER BY challan_no DESC
            """,
            (like, like, q),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT challan_no, student_name, father_name, reg_no, degree,
                   semester, installment, fee_type, total_fee,
                   issue_date, due_date, created_by
            FROM challans
            ORDER BY challan_no DESC
            """
        ).fetchall()

    conn.close()

    records = []
    for r in rows:
        item = dict(r)
        item["issue_date"] = format_date(r["issue_date"])
        item["due_date"] = format_date(r["due_date"])
        records.append(item)

    return render_template("challans.html", rows=records, q=q)


@app.route("/challans/<int:challan_no>/delete", methods=["POST"])
@login_required
def delete_challan(challan_no):
    if session.get("role") != "admin":
        return "You are not allowed to do this.", 403

    conn = get_connection()
    conn.execute("DELETE FROM challans WHERE challan_no = ?", (challan_no,))
    conn.commit()
    conn.close()

    flash(f"Challan {challan_no} deleted.")
    return redirect(url_for("challans"))


@app.route("/slip/<int:challan_no>")
@login_required
def slip(challan_no):
    conn = get_connection()

    row = conn.execute(
        "SELECT * FROM challans WHERE challan_no = ?",
        (challan_no,),
    ).fetchone()

    conn.close()

    if row is None:
        return "Slip not found.", 404

    slip_data = dict(row)

    slip_data["issue_date"] = format_date(row["issue_date"])
    slip_data["due_date"] = format_date(row["due_date"])
    slip_data["amount_words"] = amount_in_words(row["total_fee"])

    copies = [
        "STUDENT COPY",
        "UNIVERSITY COPY",
        "BANK COPY",
    ]

    return render_template(
        "slip.html",
        s=slip_data,
        copies=copies,
    )


if __name__ == "__main__":
    app.run()