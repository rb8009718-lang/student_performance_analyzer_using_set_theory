from database import get_db_connection, init_db
from werkzeug.security import generate_password_hash


init_db()

conn = get_db_connection()


# =====================================================
# DIVISIONS
# =====================================================

divisions = [
    ("Division A", "B.Tech CSE", 3, "2026-27"),
    ("Division B", "B.Tech CSE", 3, "2026-27")
]

for division in divisions:

    exists = conn.execute("""
        SELECT id
        FROM divisions
        WHERE division_name = ?
    """, (division[0],)).fetchone()

    if not exists:

        conn.execute("""
            INSERT INTO divisions
            (division_name, course, semester, academic_year)
            VALUES (?, ?, ?, ?)
        """, division)


# =====================================================
# SUBJECTS
# =====================================================

subjects = [
    ("CS301", "Python Programming", 100, 40),
    ("CS302", "Database Management System", 100, 40),
    ("CS303", "Mathematics", 100, 40),
    ("CS304", "Artificial Intelligence", 100, 40),
    ("CS305", "Data Structures", 100, 40)
]

for subject in subjects:

    exists = conn.execute("""
        SELECT id
        FROM subjects
        WHERE subject_code = ?
    """, (subject[0],)).fetchone()

    if not exists:

        conn.execute("""
            INSERT INTO subjects
            (subject_code, subject_name, max_marks, passing_marks)
            VALUES (?, ?, ?, ?)
        """, subject)


# =====================================================
# TEACHER
# =====================================================

teacher = conn.execute("""
    SELECT id
    FROM users
    WHERE username = 'teacher01'
""").fetchone()

if not teacher:

    conn.execute("""
        INSERT INTO users
        (username, password_hash, role)
        VALUES (?, ?, 'teacher')
    """, (
        "teacher01",
        generate_password_hash("teacher123")
    ))


conn.commit()
conn.close()


print("Safe setup completed.")
print("Teacher Login:")
print("Username: teacher01")
print("Password: teacher123")