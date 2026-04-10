from flask import Flask, render_template, request, redirect, send_file, session
import random
import mysql.connector
import qrcode
import os

app = Flask(__name__)
app.secret_key = "healthcard_secret_key"

# MySQL connection
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="Dharsh!7",
    database="smart_health_card"
)
cursor = db.cursor()

# 🏠 FRONT PAGE (3 portals)
@app.route('/')
def home():

    # Get most recently added patient
    cursor.execute("SELECT patient_id FROM patients ORDER BY id DESC LIMIT 1")
    latest_patient = cursor.fetchone()

    if latest_patient:
        latest_qr = latest_patient[0] + ".png"
    else:
        latest_qr = "PAT001.png"  # default if no patient

    return render_template("home.html", latest_qr=latest_qr)

# 🛠 ADMIN DASHBOARD
@app.route('/admin')
def admin_dashboard():
    return render_template("admin_dashboard.html")

# 👤 PATIENT DETAILS
@app.route('/adminpatient', methods=['GET', 'POST'])
def adminpatient():
    if request.method == 'POST':
        name = request.form['name']
        dob = request.form['dob']
        mobile = request.form['mobile']
        height = request.form['height']
        weight = request.form['weight']
        reason = request.form['reason']
        doctor = request.form['doctor']

        # Generate Patient ID
        cursor.execute("SELECT COUNT(*) FROM patients")
        count = cursor.fetchone()[0] + 1
        patient_id = f"PAT{count:03}"

        # Insert into DB
        sql = """INSERT INTO patients
                 (patient_id, name, dob, mobile, height, weight, reason, doctor)
                 VALUES (%s,%s,%s,%s,%s,%s,%s,%s)"""
        cursor.execute(sql, (patient_id, name, dob, mobile, height, weight, reason, doctor))
        db.commit()

        # Generate QR
        url = f"https://courageous-dorene-unsickened.ngrok-free.dev/emergency/{patient_id}"
        qr = qrcode.make(url)
        qr.save(f"static/qr_codes/{patient_id}.png")

        return redirect('/adminpatient')

    # Fetch available doctors for dropdown
    cursor.execute("SELECT doctor_id, name FROM doctors WHERE status='Available'")
    doctor_list = cursor.fetchall()

    # Fetch patients
    cursor.execute("SELECT * FROM patients")
    data = cursor.fetchall()

    return render_template(
        "patient_details.html",
        patients=data,
        doctors=doctor_list
    )

@app.route('/download/<patient_id>')
def download_card(patient_id):
    path = f"static/qr_codes/{patient_id}.png"
    return send_file(path, as_attachment=True)

# 🩺 DOCTOR AVAILABILITY
@app.route('/admindoctor', methods=['GET', 'POST'])
def admindoctor():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        specialization = request.form['specialization']
        status = request.form['status']

        # Generate Doctor ID
        cursor.execute("SELECT COUNT(*) FROM doctors")
        count = cursor.fetchone()[0] + 1
        doctor_id = f"DOC{count:03}"

        sql = """INSERT INTO doctors
                 (doctor_id, name, email, specialization, status)
                 VALUES (%s,%s,%s,%s,%s)"""
        cursor.execute(sql, (doctor_id, name, email, specialization, status))
        db.commit()

        return redirect('/admindoctor')

    cursor.execute("SELECT * FROM doctors")
    data = cursor.fetchall()
    return render_template("doctor_availability.html", doctors=data)

@app.route('/delete_doctor/<int:id>')
def delete_doctor(id):
    sql = "DELETE FROM doctors WHERE id=%s"
    cursor.execute(sql, (id,))
    db.commit()
    return redirect('/admindoctor')

#Doctor Login
@app.route('/doctorlogin', methods=['GET', 'POST'])
def doctor_login():
    if request.method == 'POST':
        email = request.form['email']

        cursor.execute("SELECT doctor_id, name FROM doctors WHERE email=%s", (email,))
        doctor = cursor.fetchone()

        if doctor:
            return redirect(f"/doctor/{doctor[0]}")
        else:
            return "Invalid Doctor"

    return render_template("doctor_login.html")

    # Doctor Dashboard
@app.route('/doctor/<doctor_id>', methods=['GET', 'POST'])
def doctor_dashboard(doctor_id):
    patient = None
    success = request.args.get('success')

    if request.method == 'POST':
        patient_id = request.form['patient_id']
        cursor.execute("SELECT * FROM patients WHERE patient_id=%s", (patient_id,))
        patient = cursor.fetchone()

    return render_template("doctor_dashboard.html",
                           patient=patient,
                           doctor_id=doctor_id,
                           success=success)
# Prescription Adding
from flask import jsonify

@app.route('/add_prescription/<doctor_id>', methods=['POST'])
def add_prescription(doctor_id):
    patient_id = request.form['patient_id']
    diagnosis = request.form['diagnosis']
    prescription = request.form['prescription']
    severity = request.form['severity']

    cursor.execute("""
        INSERT INTO prescriptions (patient_id, doctor_id, diagnosis, prescription, severity, date)
        VALUES (%s, %s, %s, %s, %s, CURDATE())
    """, (patient_id, doctor_id, diagnosis, prescription, severity))
    
    db.commit()

    return jsonify({"message": "Prescription Added Successfully!"})

# 🚑 EMERGENCY ACCESS — PATIENT SPECIFIC (QR SCAN)
@app.route('/emergency/<patient_id>')
def emergency_access(patient_id):

    # 🔎 Check patient exists
    cursor.execute("SELECT mobile FROM patients WHERE patient_id=%s", (patient_id,))
    result = cursor.fetchone()

    if not result:
        return "Patient not found ❌"

    mobile = result[0]

    session['patient_id'] = patient_id

    # 📱 Generate OTP
    otp = random.randint(1000, 9999)
    session['otp'] = str(otp)

    print("OTP sent to", mobile, ":", otp)

    # ➜ Go to OTP page
    return render_template("verify_otp.html")

@app.route('/verify_otp', methods=['POST'])
def verify_otp():

    entered_otp = request.form['entered_otp']

    if entered_otp == session.get('otp'):

        patient_id = session.get('patient_id')

        # Get patient details
        cursor.execute("SELECT * FROM patients WHERE patient_id=%s", (patient_id,))
        patient = cursor.fetchone()

        # Get prescriptions
        cursor.execute("SELECT * FROM prescriptions WHERE patient_id=%s", (patient_id,))
        prescriptions = cursor.fetchall()

        # 🔴🟡🟢 Find highest severity
        severity = "Mild"   # default

        for p in prescriptions:
            if p[6] == "Serious":
                severity = "Serious"
                break
            elif p[6] == "Moderate":
                severity = "Moderate"

        from datetime import date
        # Calculate age from DOB
        dob = patient[3]  # YYYY-MM-DD
        birth_year = int(str(dob).split("-")[0])
        age = date.today().year - birth_year

        return render_template(
            "patient_records.html",
            patient=patient,
            prescriptions=prescriptions,
            severity=severity,
            age=age
        )

    else:
        return "Invalid OTP"


# 🚑 SKIP OTP (Emergency Access)
@app.route('/skip_otp')
def skip_otp():

    patient_id = session.get('patient_id')

    if not patient_id:
        return redirect('/')

    # Get patient details
    cursor.execute("SELECT * FROM patients WHERE patient_id=%s", (patient_id,))
    patient = cursor.fetchone()

    # Get prescriptions
    cursor.execute("SELECT * FROM prescriptions WHERE patient_id=%s", (patient_id,))
    prescriptions = cursor.fetchall()

    # 🔴🟡🟢 Find highest severity
    severity = "Mild"

    for p in prescriptions:
        if p[6] == "Serious":
            severity = "Serious"
            break
        elif p[6] == "Moderate":
            severity = "Moderate"

    from datetime import date
    dob = patient[3]
    birth_year = int(str(dob).split("-")[0])
    age = date.today().year - birth_year

    return render_template(
        "patient_records.html",
        patient=patient,
        prescriptions=prescriptions,
        severity=severity,
        age=age
    )

@app.route('/resend_otp')
def resend_otp():

    patient_id = session.get('patient_id')

    if not patient_id:
        return redirect('/')

    cursor.execute("SELECT mobile FROM patients WHERE patient_id=%s", (patient_id,))
    result = cursor.fetchone()

    mobile = result[0]

    otp = random.randint(1000, 9999)
    session['otp'] = str(otp)

    print("NEW OTP sent to", mobile, ":", otp)

    return render_template("verify_otp.html")

    

if __name__ == '__main__':
   
    app.run(debug=True, host="0.0.0.0")