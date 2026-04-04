from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import pymysql
from datetime import date
from functools import wraps
from werkzeug.security import check_password_hash

app = Flask(__name__)
app.secret_key = "student_management_secret"

# ---------------- DATABASE CONNECTION ----------------
conn = pymysql.connect(
    host="YOUR-RDS-ENDPOINT",
    user="admin",
    password="password123",
    database="studentdb"
    cursorclass=pymysql.cursors.Cursor
)
cursor = conn.cursor()

# ---------------- LOGIN REQUIRED DECORATOR ----------------
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

# ---------------- LOGIN ----------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]

        cursor.execute(
            "SELECT UserId, PasswordHash FROM Users WHERE Username = ?",
            (username,)
        )
        user = cursor.fetchone()

        if user and check_password_hash(user[1], password):
            session["user_id"] = user[0]
            session["username"] = username
            return redirect(url_for("dashboard"))
        else:
            return render_template("login.html", error="Invalid username or password")

    return render_template("login.html")

# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ---------------- DASHBOARD ----------------
@app.route("/")
@login_required
def dashboard():
    cursor.execute("SELECT COUNT(*) FROM Students")
    total_students = cursor.fetchone()[0]

    cursor.execute("""
        SELECT Status, COUNT(*) 
        FROM Attendance 
        GROUP BY Status
    """)
    rows = cursor.fetchall()

    present_count = 0
    absent_count = 0
    for status, count in rows:
        if status == "Present":
            present_count = count
        elif status == "Absent":
            absent_count = count

    cursor.execute("SELECT AVG(Total) FROM Results")
    avg_marks = cursor.fetchone()[0] or 0

    return render_template(
        "dashboard.html",
        total_students=total_students,
        present_count=present_count,
        absent_count=absent_count,
        avg_marks=round(avg_marks, 2)
    )

# ---------------- ATTENDANCE PAGE ----------------
@app.route("/attendance")
@login_required
def attendance():
    cursor.execute("""
        SELECT StudentId, StudentName
        FROM Students
        ORDER BY StudentName
    """)
    students = cursor.fetchall()

    return render_template(
        "attendance.html",
        students=students,
        today=date.today()
    )

# ---------------- SAVE ATTENDANCE ----------------
@app.route("/mark-attendance", methods=["POST"])
@login_required
def mark_attendance():
    student_ids = request.form.getlist("student_id[]")
    statuses = request.form.getlist("status[]")

    for sid, status in zip(student_ids, statuses):
        if status:
            cursor.execute("""
                INSERT INTO Attendance (StudentId, AttendanceDate, Status)
                VALUES (?, ?, ?)
            """, (sid, date.today(), status))

    conn.commit()
    return redirect(url_for("attendance"))

# ---------------- MONTHLY ATTENDANCE API ----------------
@app.route("/api/monthly-attendance/<int:student_id>/<int:year>/<int:month>")
@login_required
def monthly_attendance(student_id, year, month):
    cursor.execute("""
        SELECT AttendanceDate, Status
        FROM Attendance
        WHERE StudentId = ?
          AND YEAR(AttendanceDate) = ?
          AND MONTH(AttendanceDate) = ?
        ORDER BY AttendanceDate
    """, (student_id, year, month))

    rows = cursor.fetchall()

    present = 0
    absent = 0
    days = []

    for att_date, status in rows:
        if status == "Present":
            present += 1
        elif status == "Absent":
            absent += 1

        days.append({
            "date": att_date.strftime("%d-%m-%Y"),
            "status": status
        })

    return jsonify({
        "present": present,
        "absent": absent,
        "days": days
    })

# ---------------- STUDENTS ----------------
@app.route("/students")
@login_required
def students():
    cursor.execute("SELECT * FROM Students")
    students = cursor.fetchall()
    return render_template("students.html", students=students)

@app.route("/add-student", methods=["POST"])
@login_required
def add_student():
    cursor.execute("""
        INSERT INTO Students (StudentName, StudentClass, Gender, DateOfBirth)
        VALUES (?, ?, ?, ?)
    """, (
        request.form["name"],
        request.form["class"],
        request.form["gender"],
        request.form["dob"]
    ))
    conn.commit()
    return redirect(url_for("students"))

@app.route("/update-student", methods=["POST"])
@login_required
def update_student():
    cursor.execute("""
        UPDATE Students
        SET StudentName = ?, StudentClass = ?, Gender = ?, DateOfBirth = ?
        WHERE StudentId = ?
    """, (
        request.form["name"],
        request.form["class"],
        request.form["gender"],
        request.form["dob"],
        request.form["student_id"]
    ))
    conn.commit()
    return redirect(url_for("students"))

@app.route("/delete-student/<int:id>")
@login_required
def delete_student(id):
    try:
        # 🔹 Delete child records first
        cursor.execute("DELETE FROM Fees WHERE StudentId = ?", (id,))
        cursor.execute("DELETE FROM Attendance WHERE StudentId = ?", (id,))
        cursor.execute("DELETE FROM Results WHERE StudentId = ?", (id,))

        # 🔹 Now delete student
        cursor.execute("DELETE FROM Students WHERE StudentId = ?", (id,))

        conn.commit()
        return redirect(url_for("students"))

    except Exception as e:
        conn.rollback()
        return f"Error deleting student: {str(e)}"


# ---------------- EXAMS ----------------
@app.route("/exams")
@login_required
def exams():
    cursor.execute("SELECT * FROM Exams")
    exams = cursor.fetchall()
    return render_template("exams.html", exams=exams)

@app.route("/add-exam", methods=["POST"])
@login_required
def add_exam():
    cursor.execute("""
        INSERT INTO Exams (ExamName, ExamDate)
        VALUES (?, ?)
    """, (request.form["exam_name"], request.form["exam_date"]))
    conn.commit()
    return redirect(url_for("exams"))

@app.route("/update-exam", methods=["POST"])
@login_required
def update_exam():
    cursor.execute("""
        UPDATE Exams
        SET ExamName = ?, ExamDate = ?
        WHERE ExamId = ?
    """, (
        request.form["exam_name"],
        request.form["exam_date"],
        request.form["exam_id"]
    ))
    conn.commit()
    return redirect(url_for("exams"))

@app.route("/delete-exam/<int:id>")
@login_required
def delete_exam(id):
    cursor.execute("DELETE FROM Results WHERE ExamId = ?", (id,))
    cursor.execute("DELETE FROM Exams WHERE ExamId = ?", (id,))
    conn.commit()
    return redirect(url_for("exams"))

# ---------------- RESULTS ----------------
def calculate_grade(total):
    if total >= 250:
        return "A"
    elif total >= 200:
        return "B"
    elif total >= 150:
        return "C"
    else:
        return "D"

@app.route("/results")
@login_required
def results():
    cursor.execute("""
        SELECT r.ResultId, s.StudentName, e.ExamName,
               r.Maths, r.Science, r.English, r.Total, r.Grade
        FROM Results r
        JOIN Students s ON r.StudentId = s.StudentId
        JOIN Exams e ON r.ExamId = e.ExamId
    """)
    results = cursor.fetchall()

    cursor.execute("SELECT * FROM Students")
    students = cursor.fetchall()

    cursor.execute("SELECT * FROM Exams")
    exams = cursor.fetchall()

    return render_template(
        "results.html",
        results=results,
        students=students,
        exams=exams
    )

@app.route("/add-result", methods=["POST"])
@login_required
def add_result():
    maths = int(request.form["maths"])
    science = int(request.form["science"])
    english = int(request.form["english"])

    total = maths + science + english
    grade = calculate_grade(total)

    cursor.execute("""
        INSERT INTO Results
        (StudentId, ExamId, Maths, Science, English, Total, Grade)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        request.form["student_id"],
        request.form["exam_id"],
        maths, science, english,
        total, grade
    ))





    conn.commit()
    return redirect(url_for("results"))






@app.route("/update-result", methods=["POST"])
@login_required
def update_result():
    maths = int(request.form["maths"])
    science = int(request.form["science"])
    english = int(request.form["english"])

    total = maths + science + english
    grade = calculate_grade(total)

    cursor.execute("""
        UPDATE Results
        SET StudentId = ?, ExamId = ?, Maths = ?, Science = ?, English = ?,
            Total = ?, Grade = ?
        WHERE ResultId = ?
    """, (
        request.form["student_id"],
        request.form["exam_id"],
        maths, science, english,
        total, grade,
        request.form["result_id"]
    ))

    conn.commit()
    return redirect(url_for("results"))


@app.route("/delete-result/<int:id>")
@login_required
def delete_result(id):
    cursor.execute("DELETE FROM Results WHERE ResultId = ?", (id,))
    conn.commit()
    return redirect(url_for("results"))




# ---------------- RUN APP ----------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
