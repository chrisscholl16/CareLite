from flask import Flask, render_template, request, url_for, redirect, flash
from config import Config
from flask_migrate import Migrate
from models import db, User, PasswordResetId, PatientRecord, Appointment
from sqlalchemy import select
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, login_required, login_user, logout_user, current_user
from flask_mail import Mail, Message
from functools import wraps
from datetime import datetime, timedelta


app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

migrate = Migrate(app, db)
bcrypt = Bcrypt(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message = "You need to be authenticated to access this page"
login_manager.login_message_category = "error"

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

mail = Mail(app)

def role_required(required_role):
    def decorator(f):
        @wraps(f)
        @login_required
        def decorated_function(*args, **kwargs):
            # Check if the logged-in user has the allowed role
            if current_user.role != required_role:
                flash("You do not have permission to view this page.", "danger")
                return redirect(url_for('login'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def admin_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):

        if not current_user.is_admin():
            flash(
                "You do not have permission to access this page.",
                "danger"
            )
            return redirect(url_for("login"))

        return f(*args, **kwargs)

    return decorated_function

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():

    if current_user.is_authenticated:
        return redirect(url_for("home"))

    if request.method == "POST":

        username = request.form.get("username")
        email = request.form.get("email")
        role = request.form.get("role")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")

        # Patient-specific information
        patient_name = request.form.get("patient_name")
        date_of_birth = request.form.get("date_of_birth")

        if len(password) < 5:
            flash("Password must be at least 5 characters", "error")
            return redirect(url_for("register"))

        if password != confirm_password:
            flash("Passwords do not match", "error")
            return redirect(url_for("register"))

        # Make sure email isn't already being used
        if db.session.scalar(
            select(User).where(User.email == email)
        ):
            flash("Email already in use", "error")
            return redirect(url_for("register"))

        # Make sure username isn't already being used
        if db.session.scalar(
            select(User).where(User.username == username)
        ):
            flash("Username already in use", "error")
            return redirect(url_for("register"))

        # Make sure patient information was provided
        if role == "patient":

            if not patient_name or not date_of_birth:
                flash(
                    "Patient name and date of birth are required.",
                    "error"
                )
                return redirect(url_for("register"))

            from datetime import datetime

            try:
                date_of_birth = datetime.strptime(
                    date_of_birth,
                    "%Y-%m-%d"
                ).date()

            except ValueError:
                flash("Invalid date of birth.", "error")
                return redirect(url_for("register"))

        hashed_password = bcrypt.generate_password_hash(
            password
        ).decode("utf-8")

        # Create the User
        user = User(
            username=username,
            email=email,
            role=role,
            password=hashed_password
        )

        db.session.add(user)

        # Get the user's ID before committing
        db.session.flush()

        # Create PatientRecord if this is a patient
        if role == "patient":

            patient_record = PatientRecord(
                patient_id=user.id,
                patient_name=patient_name,
                date_of_birth=date_of_birth
            )

            db.session.add(patient_record)

        db.session.commit()

        flash("Account created successfully", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():

    if current_user.is_authenticated:
        return redirect(url_for("home"))

    if request.method == 'POST':
        username = request.form.get("username")
        password = request.form.get("password")

        user = db.session.scalar(
            select(User).where(User.username == username)
        )
        if user:
            #check if password is correct
            if bcrypt.check_password_hash(user.password, password):
                login_user(user)

                if user.is_admin():
                    return redirect(url_for('admin'))

                elif user.is_nurse():
                    return redirect(url_for('nurse'))

                elif user.is_patient():
                    return redirect(url_for('patient'))

                # next = request.args.get('next')
                # return redirect(next or url_for('home'))

            flash("Invalid password entered", "error")
            return redirect(url_for("login"))

        flash("Invalid username entered", "error")
        return redirect(url_for("login"))

    return render_template("login.html")


@app.route('/logout', methods=['GET'])
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():

    if current_user.is_authenticated:
        return redirect(url_for("home"))

    if request.method == 'POST':
        email = request.form.get("email")

        user = db.session.scalar(
            select(User).where(User.email == email)
        )

        if not user:
            flash("No user with that email found", "error")
            return redirect(url_for("forgot_password"))
        
        # delete other potentially existing codes
        user.password_reset_ids.clear()

        new_password_reset_id = PasswordResetId(user=user)
        db.session.add(new_password_reset_id)
        db.session.commit()

        password_reset_link = url_for("reset_password", reset_id=new_password_reset_id.reset_id , _external=True)
        
        msg = Message(
            subject = "Reset your password",
            recipients = [email],
            body = f"Reset your password using the link below\n\n{password_reset_link}"
        )
        try:
            mail.send(msg)

            context = {
                "reset_sent": True,
                "email": email
            }
            return render_template("forgot_password.html", **context) 
        except Exception as e:
            print(f"Error: {e}")


    return render_template("forgot_password.html", reset_sent=False)


@app.route("/reset-password/<reset_id>", methods=["GET", "POST"])
def reset_password(reset_id):

    if current_user.is_authenticated:
        return redirect(url_for("home"))

    reset_id_object = db.session.scalar(
        select(PasswordResetId).where(PasswordResetId.reset_id == reset_id)
    )

    if not reset_id_object:
        flash("Invalid reset link", "error")
        return redirect(url_for("forgot_password"))

    # delete reset id if it has expired
    if reset_id_object.is_expired():
        db.session.delete(reset_id)
        db.session.commit()

        flash("Expired reset link", "error")
        return redirect(url_for("forgot_password"))
    
    if request.method == "POST":

        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")

        if len(password) < 5:
            flash("Password must be at east 5 characters long", "error")
            return redirect(url_for("reset_password", reset_id=reset_id))

        if password != confirm_password:
            flash("Passwords do not match", "error")
            return redirect(url_for("reset_password", reset_id=reset_id))
        
        user = reset_id_object.user
        user.password = bcrypt.generate_password_hash(password).decode('utf-8')
        db.session.commit()

        db.session.delete(reset_id_object)
        db.session.commit()

        flash("Password changed successfully. Login", "success")
        return redirect(url_for("login"))

    return render_template("reset_password.html")


@app.route('/patient', methods=['GET', 'POST'])
@role_required('patient')
def patient():

    patient_record = current_user.patient_record

    # Get upcoming appointments for this patient
    appointments = db.session.scalars(
    select(Appointment)
    .where(
        Appointment.patient_id == current_user.id,
        Appointment.status == "Scheduled",
        Appointment.appointment_date >= datetime.now().date()
    )
    .order_by(
        Appointment.appointment_date,
        Appointment.appointment_time
    )
).all()

    now = datetime.now()
    reminder_limit = now + timedelta(hours=24)

    reminders = []

    for appointment in appointments:

        appointment_datetime = datetime.combine(
            appointment.appointment_date,
            appointment.appointment_time
        )

        # Add appointment to reminders if it is
        # happening within the next 24 hours
        if now <= appointment_datetime <= reminder_limit:
            reminders.append(appointment)

    return render_template(
        'patient.html',
        patient_record=patient_record,
        appointments=appointments,
        reminders=reminders
    )


@app.route('/nurse', methods=['GET', 'POST'])
@role_required('nurse')
def nurse():

    patients = db.session.scalars(
        select(User).where(User.role == "patient")
    ).all()

    if request.method == 'POST':

        patient_id = request.form.get("patient_id")
        blood_pressure = request.form.get("blood_pressure")
        temperature = request.form.get("temperature")
        notes = request.form.get("notes")

        if not patient_id:
            flash("Please select a patient.", "error")
            return redirect(url_for("nurse"))

        patient = db.session.get(
            User,
            int(patient_id)
        )

        if not patient or not patient.is_patient():
            flash("Invalid patient selected.", "error")
            return redirect(url_for("nurse"))

        if temperature:
            try:
                temperature = float(temperature)
            except ValueError:
                flash(
                    "Temperature must be a valid number.",
                    "error"
                )
                return redirect(url_for("nurse"))
        else:
            temperature = None

        patient_record = patient.patient_record

        if patient_record:

            patient_record.blood_pressure = blood_pressure
            patient_record.temperature = temperature
            patient_record.notes = notes

            # Record which nurse updated the information
            patient_record.nurse_id = current_user.id

            flash(
                "Patient record updated successfully!",
                "success"
            )

        else:

            flash(
                "This patient does not have a patient record.",
                "error"
            )
            return redirect(url_for("nurse"))

        db.session.commit()

        return redirect(url_for("nurse"))

    appointments = db.session.scalars(
    select(Appointment)
    .where(
        Appointment.status == "Scheduled",
        Appointment.appointment_date >= datetime.now().date()
    )
    .order_by(
        Appointment.appointment_date,
        Appointment.appointment_time
    )
    ).all()

    return render_template(
        "nurse.html",
        patients=patients,
        appointments=appointments
    )

@app.route("/admin")
@admin_required
def admin():

    users = db.session.scalars(
        select(User)
    ).all()

    patient_records = db.session.scalars(
        select(PatientRecord)
    ).all()

    appointments = db.session.scalars(
    select(Appointment)
    .where(
        Appointment.appointment_date >= datetime.now().date(),
        Appointment.status == "Scheduled"
    )
    .order_by(
        Appointment.appointment_date,
        Appointment.appointment_time
    )
    ).all()

    return render_template(
        "admin.html",
        users=users,
        patient_records=patient_records,
        appointments=appointments
    )

@app.route("/appointments", methods=["GET", "POST"])
@role_required("patient")
def appointments():

    if request.method == "POST":

        appointment_date = request.form.get("appointment_date")
        appointment_time = request.form.get("appointment_time")
        reason = request.form.get("reason")

        if not appointment_date or not appointment_time or not reason:
            flash(
                "Please complete all appointment fields.",
                "error"
            )
            return redirect(url_for("appointments"))

        from datetime import datetime

        # Convert date
        try:
            appointment_date = datetime.strptime(
                appointment_date,
                "%Y-%m-%d"
            ).date()

        except ValueError:
            flash(
                "Invalid appointment date.",
                "error"
            )
            return redirect(url_for("appointments"))

        # Convert time
        try:
            appointment_time = datetime.strptime(
                appointment_time,
                "%H:%M"
            ).time()

        except ValueError:
            flash(
                "Invalid appointment time.",
                "error"
            )
            return redirect(url_for("appointments"))

        # Don't allow appointments in the past
        appointment_datetime = datetime.combine(
            appointment_date,
            appointment_time
        )

        if appointment_datetime < datetime.now():
            flash(
                "You cannot schedule an appointment in the past.",
                "error"
            )
            return redirect(url_for("appointments"))

        # Check if this time is already booked
        existing_appointment = db.session.scalar(
            select(Appointment).where(
                Appointment.appointment_date == appointment_date,
                Appointment.appointment_time == appointment_time,
                Appointment.status == "Scheduled"
            )
        )

        if existing_appointment:
            flash(
                "That appointment time is already booked.",
                "error"
            )
            return redirect(url_for("appointments"))

        # Create appointment
        appointment = Appointment(
            patient_id=current_user.id,
            appointment_date=appointment_date,
            appointment_time=appointment_time,
            reason=reason,
            status="Scheduled"
        )

        db.session.add(appointment)
        db.session.commit()

        flash(
            "Appointment scheduled successfully!",
            "success"
        )

        return redirect(url_for("appointments"))

    # Get this patient's appointments
    patient_appointments = db.session.scalars(
        select(Appointment)
        .where(Appointment.patient_id == current_user.id)
        .order_by(
            Appointment.appointment_date,
            Appointment.appointment_time
        )
    ).all()

    return render_template(
        "appointments.html",
        appointments=patient_appointments
    )



if __name__ == "__main__":
    app.run(port=8000, debug=True)