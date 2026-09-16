from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
import os
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash

from database import get_db_connection, init_db

app = Flask(__name__)

app.secret_key = "student-performance-analyzer-secret-key"

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATABASE = os.path.join(BASE_DIR, "database", "student_performance.db")


# =========================================================
# DATABASE
# =========================================================

init_db()


# =========================================================
# AUTHENTICATION HELPERS
# =========================================================

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)

    return decorated_function


def teacher_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))

        if session.get("role") != "teacher":
            flash("Teacher access required.", "danger")
            return redirect(url_for("student_dashboard"))

        return f(*args, **kwargs)

    return decorated_function


def student_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))

        if session.get("role") != "student":
            flash("Student access required.", "danger")
            return redirect(url_for("teacher_dashboard"))

        return f(*args, **kwargs)

    return decorated_function


# =========================================================
# HOME
# =========================================================

@app.route("/")
def index():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") == "teacher":
        return redirect(url_for("teacher_dashboard"))

    return redirect(url_for("student_dashboard"))


# =========================================================
# LOGIN
# =========================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if not username or not password:
            flash("Please enter username and password.", "danger")
            return render_template("login.html")

        conn = get_db_connection()

        user = conn.execute(
            "SELECT * FROM users WHERE username = ?",
            (username,)
        ).fetchone()

        conn.close()

        if user and check_password_hash(user["password_hash"], password):

            session.clear()

            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = user["role"]
            session["student_id"] = user["student_id"]

            if user["role"] == "teacher":
                return redirect(url_for("teacher_dashboard"))

            return redirect(url_for("student_dashboard"))

        flash("Invalid username or password.", "danger")

    return render_template("login.html")


# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
def logout():

    session.clear()

    flash("You have been logged out.", "success")

    return redirect(url_for("login"))


# =========================================================
# TEACHER DASHBOARD
# =========================================================

@app.route("/teacher/dashboard")
@teacher_required
def teacher_dashboard():

    conn = get_db_connection()

    student_count = conn.execute(
        "SELECT COUNT(*) AS count FROM students"
    ).fetchone()["count"]

    subject_count = conn.execute(
        "SELECT COUNT(*) AS count FROM subjects"
    ).fetchone()["count"]

    division_count = conn.execute(
        "SELECT COUNT(*) AS count FROM divisions"
    ).fetchone()["count"]

    marks_count = conn.execute(
        "SELECT COUNT(*) AS count FROM marks"
    ).fetchone()["count"]

    recent_students = conn.execute("""
        SELECT
            students.*,
            divisions.division_name
        FROM students
        LEFT JOIN divisions
        ON students.division_id = divisions.id
        ORDER BY students.id DESC
        LIMIT 5
    """).fetchall()

    conn.close()

    return render_template(
        "teacher/dashboard.html",
        student_count=student_count,
        subject_count=subject_count,
        division_count=division_count,
        marks_count=marks_count,
        recent_students=recent_students
    )


# =========================================================
# TEACHER - STUDENTS
# =========================================================

@app.route("/teacher/students")
@teacher_required
def teacher_students():

    division_id = request.args.get("division_id")

    conn = get_db_connection()

    divisions = conn.execute(
        "SELECT * FROM divisions ORDER BY division_name"
    ).fetchall()

    if division_id:
        students = conn.execute("""
            SELECT
                students.*,
                divisions.division_name
            FROM students
            LEFT JOIN divisions
            ON students.division_id = divisions.id
            WHERE students.division_id = ?
            ORDER BY students.student_roll
        """, (division_id,)).fetchall()

    else:
        students = conn.execute("""
            SELECT
                students.*,
                divisions.division_name
            FROM students
            LEFT JOIN divisions
            ON students.division_id = divisions.id
            ORDER BY students.student_roll
        """).fetchall()

    conn.close()

    return render_template(
        "teacher/students.html",
        students=students,
        divisions=divisions,
        selected_division=division_id
    )


# =========================================================
# ADD STUDENT
# =========================================================

@app.route("/teacher/students/add", methods=["GET", "POST"])
@teacher_required
def add_student():

    conn = get_db_connection()

    divisions = conn.execute(
        "SELECT * FROM divisions ORDER BY division_name"
    ).fetchall()

    if request.method == "POST":

        roll = request.form.get("student_roll", "").strip()
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        course = request.form.get("course", "").strip()
        semester = request.form.get("semester", "").strip()
        division_id = request.form.get("division_id")
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if not all([
            roll, name, email, course,
            semester, division_id,
            username, password
        ]):
            conn.close()
            flash("Please fill all fields.", "danger")
            return render_template(
                "teacher/add_student.html",
                divisions=divisions
            )

        try:

            cursor = conn.execute("""
                INSERT INTO students
                (student_roll, name, email, course, semester, division_id)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                roll,
                name,
                email,
                course,
                int(semester),
                int(division_id)
            ))

            student_id = cursor.lastrowid

            password_hash = generate_password_hash(password)

            conn.execute("""
                INSERT INTO users
                (username, password_hash, role, student_id)
                VALUES (?, ?, 'student', ?)
            """, (
                username,
                password_hash,
                student_id
            ))

            conn.commit()

            conn.close()

            flash("Student and login account created successfully.", "success")

            return redirect(url_for("teacher_students"))

        except sqlite3.IntegrityError as e:

            conn.rollback()
            conn.close()

            flash(
                "Student roll/email/username may already exist.",
                "danger"
            )

    conn.close()

    return render_template(
        "teacher/add_student.html",
        divisions=divisions
    )


# =========================================================
# DELETE STUDENT
# =========================================================

@app.route("/teacher/students/delete/<int:student_id>", methods=["POST"])
@teacher_required
def delete_student(student_id):

    conn = get_db_connection()

    conn.execute(
        "DELETE FROM users WHERE student_id = ?",
        (student_id,)
    )

    conn.execute(
        "DELETE FROM students WHERE id = ?",
        (student_id,)
    )

    conn.commit()
    conn.close()

    flash("Student deleted successfully.", "success")

    return redirect(url_for("teacher_students"))


# =========================================================
# TEACHER - SUBJECTS
# =========================================================

@app.route("/teacher/subjects", methods=["GET", "POST"])
@teacher_required
def teacher_subjects():

    conn = get_db_connection()

    if request.method == "POST":

        code = request.form.get("subject_code", "").strip()
        name = request.form.get("subject_name", "").strip()
        max_marks = request.form.get("max_marks", "100")
        passing_marks = request.form.get("passing_marks", "40")

        if not code or not name:
            flash("Subject code and name are required.", "danger")

        else:

            try:

                conn.execute("""
                    INSERT INTO subjects
                    (subject_code, subject_name, max_marks, passing_marks)
                    VALUES (?, ?, ?, ?)
                """, (
                    code,
                    name,
                    float(max_marks),
                    float(passing_marks)
                ))

                conn.commit()

                flash("Subject added successfully.", "success")

            except sqlite3.IntegrityError:

                flash("Subject code already exists.", "danger")

    subjects = conn.execute(
        "SELECT * FROM subjects ORDER BY subject_code"
    ).fetchall()

    conn.close()

    return render_template(
        "teacher/subjects.html",
        subjects=subjects
    )


# =========================================================
# DELETE SUBJECT
# =========================================================

@app.route("/teacher/subjects/delete/<int:subject_id>", methods=["POST"])
@teacher_required
def delete_subject(subject_id):

    conn = get_db_connection()

    conn.execute(
        "DELETE FROM subjects WHERE id = ?",
        (subject_id,)
    )

    conn.commit()
    conn.close()

    flash("Subject deleted successfully.", "success")

    return redirect(url_for("teacher_subjects"))


# =========================================================
# TEACHER MARKS
# =========================================================

@app.route("/teacher/marks")
@teacher_required
def teacher_marks():

    conn = get_db_connection()

    students = conn.execute("""
        SELECT
            students.*,
            divisions.division_name
        FROM students
        LEFT JOIN divisions
        ON students.division_id = divisions.id
        ORDER BY students.student_roll
    """).fetchall()

    conn.close()

    return render_template(
        "teacher/marks.html",
        students=students
    )


# =========================================================
# MANAGE MARKS
# =========================================================

@app.route("/teacher/marks/<int:student_id>", methods=["GET", "POST"])
@teacher_required
def manage_marks(student_id):

    conn = get_db_connection()

    student = conn.execute("""
        SELECT
            students.*,
            divisions.division_name
        FROM students
        LEFT JOIN divisions
        ON students.division_id = divisions.id
        WHERE students.id = ?
    """, (student_id,)).fetchone()

    if not student:
        conn.close()
        flash("Student not found.", "danger")
        return redirect(url_for("teacher_marks"))

    subjects = conn.execute(
        "SELECT * FROM subjects ORDER BY subject_code"
    ).fetchall()

    if request.method == "POST":

        subject_id = request.form.get("subject_id")
        marks = request.form.get("marks")
        exam_type = request.form.get("exam_type", "Final")

        try:

            marks_value = float(marks)

            subject = conn.execute(
                "SELECT * FROM subjects WHERE id = ?",
                (subject_id,)
            ).fetchone()

            if not subject:
                flash("Invalid subject.", "danger")

            elif marks_value < 0 or marks_value > subject["max_marks"]:
                flash(
                    f"Marks must be between 0 and {subject['max_marks']}.",
                    "danger"
                )

            else:

                existing = conn.execute("""
                    SELECT id
                    FROM marks
                    WHERE student_id = ?
                    AND subject_id = ?
                    AND exam_type = ?
                """, (
                    student_id,
                    subject_id,
                    exam_type
                )).fetchone()

                if existing:

                    conn.execute("""
                        UPDATE marks
                        SET marks = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """, (
                        marks_value,
                        existing["id"]
                    ))

                else:

                    conn.execute("""
                        INSERT INTO marks
                        (student_id, subject_id, marks, exam_type)
                        VALUES (?, ?, ?, ?)
                    """, (
                        student_id,
                        subject_id,
                        marks_value,
                        exam_type
                    ))

                conn.commit()

                flash("Marks saved successfully.", "success")

        except ValueError:

            flash("Enter valid marks.", "danger")

    marks_data = conn.execute("""
        SELECT
            marks.*,
            subjects.subject_code,
            subjects.subject_name,
            subjects.max_marks,
            subjects.passing_marks
        FROM marks
        JOIN subjects
        ON marks.subject_id = subjects.id
        WHERE marks.student_id = ?
        ORDER BY subjects.subject_code, marks.exam_type
    """, (student_id,)).fetchall()

    conn.close()

    return render_template(
        "teacher/manage_marks.html",
        student=student,
        subjects=subjects,
        marks=marks_data
    )


# =========================================================
# DELETE MARK
# =========================================================

@app.route("/teacher/marks/delete/<int:mark_id>/<int:student_id>", methods=["POST"])
@teacher_required
def delete_mark(mark_id, student_id):

    conn = get_db_connection()

    conn.execute(
        "DELETE FROM marks WHERE id = ?",
        (mark_id,)
    )

    conn.commit()
    conn.close()

    flash("Marks deleted.", "success")

    return redirect(
        url_for(
            "manage_marks",
            student_id=student_id
        )
    )


# =========================================================
# TEACHER ATTENDANCE
# =========================================================

@app.route("/teacher/attendance", methods=["GET", "POST"])
@teacher_required
def teacher_attendance():

    conn = get_db_connection()

    students = conn.execute("""
        SELECT
            students.*,
            divisions.division_name
        FROM students
        LEFT JOIN divisions
        ON students.division_id = divisions.id
        ORDER BY students.student_roll
    """).fetchall()

    subjects = conn.execute(
        "SELECT * FROM subjects ORDER BY subject_code"
    ).fetchall()

    if request.method == "POST":

        student_id = request.form.get("student_id")
        subject_id = request.form.get("subject_id")
        date = request.form.get("date")
        status = request.form.get("status")

        if not all([
            student_id,
            subject_id,
            date,
            status
        ]):
            flash("Please fill all attendance fields.", "danger")

        else:

            existing = conn.execute("""
                SELECT id
                FROM attendance
                WHERE student_id = ?
                AND subject_id = ?
                AND date = ?
            """, (
                student_id,
                subject_id,
                date
            )).fetchone()

            if existing:

                conn.execute("""
                    UPDATE attendance
                    SET status = ?
                    WHERE id = ?
                """, (
                    status,
                    existing["id"]
                ))

            else:

                conn.execute("""
                    INSERT INTO attendance
                    (student_id, subject_id, date, status)
                    VALUES (?, ?, ?, ?)
                """, (
                    student_id,
                    subject_id,
                    date,
                    status
                ))

            conn.commit()

            flash("Attendance saved successfully.", "success")

    recent_attendance = conn.execute("""
        SELECT
            attendance.*,
            students.student_roll,
            students.name,
            subjects.subject_code,
            subjects.subject_name
        FROM attendance
        JOIN students
        ON attendance.student_id = students.id
        JOIN subjects
        ON attendance.subject_id = subjects.id
        ORDER BY attendance.date DESC, attendance.id DESC
        LIMIT 50
    """).fetchall()

    conn.close()

    return render_template(
        "teacher/attendance.html",
        students=students,
        subjects=subjects,
        attendance=recent_attendance
    )


# =========================================================
# DELETE ATTENDANCE
# =========================================================

@app.route("/teacher/attendance/delete/<int:attendance_id>", methods=["POST"])
@teacher_required
def delete_attendance(attendance_id):

    conn = get_db_connection()

    conn.execute(
        "DELETE FROM attendance WHERE id = ?",
        (attendance_id,)
    )

    conn.commit()
    conn.close()

    flash("Attendance record deleted.", "success")

    return redirect(url_for("teacher_attendance"))


# =========================================================
# STUDENT DASHBOARD
# =========================================================

@app.route("/student/dashboard")
@student_required
def student_dashboard():

    student_id = session.get("student_id")

    conn = get_db_connection()

    student = conn.execute("""
        SELECT
            students.*,
            divisions.division_name
        FROM students
        LEFT JOIN divisions
        ON students.division_id = divisions.id
        WHERE students.id = ?
    """, (student_id,)).fetchone()

    if not student:
        conn.close()
        session.clear()
        flash("Student profile not found.", "danger")
        return redirect(url_for("login"))

    subject_count = conn.execute(
        "SELECT COUNT(*) AS count FROM subjects"
    ).fetchone()["count"]

    marks_count = conn.execute("""
        SELECT COUNT(*) AS count
        FROM marks
        WHERE student_id = ?
    """, (student_id,)).fetchone()["count"]

    attendance_count = conn.execute("""
        SELECT COUNT(*) AS count
        FROM attendance
        WHERE student_id = ?
    """, (student_id,)).fetchone()["count"]

    passed_subjects = conn.execute("""
        SELECT COUNT(*) AS count
        FROM (
            SELECT
                subjects.id,
                AVG(marks.marks) AS avg_marks,
                subjects.passing_marks
            FROM marks
            JOIN subjects
            ON marks.subject_id = subjects.id
            WHERE marks.student_id = ?
            GROUP BY subjects.id
        )
        WHERE avg_marks >= passing_marks
    """, (student_id,)).fetchone()["count"]

    conn.close()

    return render_template(
        "student/dashboard.html",
        student=student,
        subject_count=subject_count,
        marks_count=marks_count,
        attendance_count=attendance_count,
        passed_subjects=passed_subjects
    )


# =========================================================
# STUDENT MARKS
# =========================================================

@app.route("/student/marks")
@student_required
def student_marks():

    student_id = session.get("student_id")

    conn = get_db_connection()

    student = conn.execute(
        "SELECT * FROM students WHERE id = ?",
        (student_id,)
    ).fetchone()

    marks = conn.execute("""
        SELECT
            marks.*,
            subjects.subject_code,
            subjects.subject_name,
            subjects.max_marks,
            subjects.passing_marks
        FROM marks
        JOIN subjects
        ON marks.subject_id = subjects.id
        WHERE marks.student_id = ?
        ORDER BY subjects.subject_code, marks.exam_type
    """, (student_id,)).fetchall()

    conn.close()

    return render_template(
        "student/marks.html",
        student=student,
        marks=marks
    )


# =========================================================
# STUDENT ATTENDANCE
# =========================================================

@app.route("/student/attendance")
@student_required
def student_attendance():

    student_id = session.get("student_id")

    conn = get_db_connection()

    student = conn.execute(
        "SELECT * FROM students WHERE id = ?",
        (student_id,)
    ).fetchone()

    attendance_summary = conn.execute("""
        SELECT
            subjects.subject_code,
            subjects.subject_name,
            COUNT(attendance.id) AS total_classes,
            SUM(
                CASE
                    WHEN attendance.status = 'Present'
                    THEN 1
                    ELSE 0
                END
            ) AS present_classes
        FROM subjects
        LEFT JOIN attendance
        ON subjects.id = attendance.subject_id
        AND attendance.student_id = ?
        GROUP BY subjects.id
        ORDER BY subjects.subject_code
    """, (student_id,)).fetchall()

    attendance_records = conn.execute("""
        SELECT
            attendance.*,
            subjects.subject_code,
            subjects.subject_name
        FROM attendance
        JOIN subjects
        ON attendance.subject_id = subjects.id
        WHERE attendance.student_id = ?
        ORDER BY attendance.date DESC
    """, (student_id,)).fetchall()

    conn.close()

    return render_template(
        "student/attendance.html",
        student=student,
        attendance_summary=attendance_summary,
        attendance_records=attendance_records
    )


# =========================================================
# STUDENT PERFORMANCE
# =========================================================

@app.route("/student/performance")
@student_required
def student_performance():

    student_id = session.get("student_id")

    conn = get_db_connection()

    student = conn.execute(
        "SELECT * FROM students WHERE id = ?",
        (student_id,)
    ).fetchone()

    performance = conn.execute("""
        SELECT
            subjects.subject_code,
            subjects.subject_name,
            subjects.max_marks,
            subjects.passing_marks,
            AVG(marks.marks) AS average_marks
        FROM subjects
        LEFT JOIN marks
        ON subjects.id = marks.subject_id
        AND marks.student_id = ?
        GROUP BY subjects.id
        ORDER BY subjects.subject_code
    """, (student_id,)).fetchall()

    conn.close()

    chart_labels = []
    chart_values = []

    total_percentage = 0
    valid_subjects = 0

    for row in performance:

        if row["average_marks"] is not None:

            percentage = (
                row["average_marks"]
                / row["max_marks"]
            ) * 100

            chart_labels.append(row["subject_code"])
            chart_values.append(round(percentage, 2))

            total_percentage += percentage
            valid_subjects += 1

    overall_percentage = (
        total_percentage / valid_subjects
        if valid_subjects
        else 0
    )

    return render_template(
        "student/performance.html",
        student=student,
        performance=performance,
        chart_labels=chart_labels,
        chart_values=chart_values,
        overall_percentage=round(overall_percentage, 2)
    )


# =========================================================
# SET THEORY ANALYSIS
# =========================================================

@app.route("/student/set-analysis")
@student_required
def set_analysis():

    student_id = session.get("student_id")

    conn = get_db_connection()

    student = conn.execute(
        "SELECT * FROM students WHERE id = ?",
        (student_id,)
    ).fetchone()

    subject_data = conn.execute("""
        SELECT
            subjects.id,
            subjects.subject_code,
            subjects.subject_name,
            subjects.max_marks,
            subjects.passing_marks,

            AVG(marks.marks) AS average_marks,

            COUNT(attendance.id) AS total_attendance,

            SUM(
                CASE
                    WHEN attendance.status = 'Present'
                    THEN 1
                    ELSE 0
                END
            ) AS present_attendance

        FROM subjects

        LEFT JOIN marks
        ON subjects.id = marks.subject_id
        AND marks.student_id = ?

        LEFT JOIN attendance
        ON subjects.id = attendance.subject_id
        AND attendance.student_id = ?

        GROUP BY subjects.id

        ORDER BY subjects.subject_code
    """, (
        student_id,
        student_id
    )).fetchall()

    conn.close()

    # -----------------------------------------------------
    # SET DEFINITIONS
    # -----------------------------------------------------

    # A = Subjects where student passed
    # B = Subjects where attendance >= 75%
    # C = Subjects where performance >= 80%

    A = set()
    B = set()
    C = set()

    subject_details = []

    for row in subject_data:

        code = row["subject_code"]

        avg_marks = row["average_marks"]

        total_attendance = row["total_attendance"] or 0
        present_attendance = row["present_attendance"] or 0

        if avg_marks is not None:
            percentage = (
                avg_marks /
                row["max_marks"]
            ) * 100
        else:
            percentage = 0

        if total_attendance > 0:
            attendance_percentage = (
                present_attendance /
                total_attendance
            ) * 100
        else:
            attendance_percentage = 0

        passed = (
            avg_marks is not None
            and avg_marks >= row["passing_marks"]
        )

        good_attendance = (
            attendance_percentage >= 75
        )

        high_performance = (
            percentage >= 80
        )

        if passed:
            A.add(code)

        if good_attendance:
            B.add(code)

        if high_performance:
            C.add(code)

        subject_details.append({
            "code": code,
            "name": row["subject_name"],
            "percentage": round(percentage, 2),
            "attendance": round(attendance_percentage, 2),
            "passed": passed,
            "good_attendance": good_attendance,
            "high_performance": high_performance
        })

    # -----------------------------------------------------
    # SET OPERATIONS
    # -----------------------------------------------------

    union_AB = sorted(A | B)
    intersection_AB = sorted(A & B)
    difference_AB = sorted(A - B)

    union_ABC = sorted(A | B | C)
    intersection_ABC = sorted(A & B & C)

    only_A = sorted(A - B - C)
    only_B = sorted(B - A - C)
    only_C = sorted(C - A - B)

    return render_template(
        "student/set_analysis.html",

        student=student,

        subjects=subject_details,

        A=sorted(A),
        B=sorted(B),
        C=sorted(C),

        union_AB=union_AB,
        intersection_AB=intersection_AB,
        difference_AB=difference_AB,

        union_ABC=union_ABC,
        intersection_ABC=intersection_ABC,

        only_A=only_A,
        only_B=only_B,
        only_C=only_C
    )


# =========================================================
# CREATE DEMO LOGIN IF DATABASE HAS NO USERS
# =========================================================

def create_default_teacher():

    conn = get_db_connection()

    teacher = conn.execute("""
        SELECT id
        FROM users
        WHERE username = 'teacher01'
    """).fetchone()

    if not teacher:

        password_hash = generate_password_hash("teacher123")

        conn.execute("""
            INSERT INTO users
            (username, password_hash, role)
            VALUES (?, ?, 'teacher')
        """, (
            "teacher01",
            password_hash
        ))

        conn.commit()

    conn.close()


# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":

    init_db()

    create_default_teacher()

    print()
    print("=" * 50)
    print(" STUDENT PERFORMANCE ANALYZER")
    print("=" * 50)
    print(" Server: http://127.0.0.1:5000")
    print(" Teacher: teacher01 / teacher123")
    print("=" * 50)
    print()

    app.run(
        debug=True,
        host="127.0.0.1",
        port=5000
    )