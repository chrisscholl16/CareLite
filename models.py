from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta, timezone
import uuid
from flask_login import UserMixin
from sqlalchemy import event

db = SQLAlchemy()


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)

    username = db.Column(
        db.String(100),
        unique=True,
        nullable=False
    )

    email = db.Column(
        db.String(50),
        unique=True,
        nullable=False
    )

    password = db.Column(
        db.String(100),
        nullable=False
    )

    role = db.Column(
        db.String(50),
        nullable=True,
        server_default="patient"
    )

    def is_nurse(self):
        return self.role == "nurse"

    def is_patient(self):
        return self.role == "patient"

    def is_admin(self):
        return self.role == "admin"

    password_reset_ids = db.relationship(
        "PasswordResetId",
        backref="user",
        cascade="all, delete-orphan"
    )

    # Patient's own patient record
    patient_record = db.relationship(
        "PatientRecord",
        foreign_keys="PatientRecord.patient_id",
        back_populates="patient",
        uselist=False,
        cascade="all, delete-orphan"
    )

    # Records entered by this nurse
    nurse_records = db.relationship(
        "PatientRecord",
        foreign_keys="PatientRecord.nurse_id",
        back_populates="nurse"
    )

    appointments = db.relationship(
        "Appointment",
        foreign_keys="Appointment.patient_id",
        back_populates="patient",
        cascade="all, delete-orphan"
    )


@event.listens_for(User.role, 'set', retval=True)
def lowercase_role(target, value, oldvalue, initiator):
    if isinstance(value, str):
        return value.lower()
    return value


class PasswordResetId(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False
    )

    reset_id = db.Column(
        db.String(36),
        nullable=False,
        default=lambda: str(uuid.uuid4())
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    def is_expired(self):
        expires_at = self.created_at + timedelta(minutes=10)
        return datetime.utcnow() > expires_at


class PatientRecord(db.Model):
    id = db.Column(
        db.Integer,
        primary_key=True
    )

    # The patient this record belongs to
    patient_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False,
        unique=True
    )

    # The nurse who entered/updated the record
    nurse_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=True
    )

    patient_name = db.Column(
        db.String(100),
        nullable=False
    )

    date_of_birth = db.Column(
        db.Date,
        nullable=False
    )

    blood_pressure = db.Column(
        db.String(20),
        nullable=True
    )

    temperature = db.Column(
        db.Float,
        nullable=True
    )

    notes = db.Column(
        db.Text,
        nullable=True
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    patient = db.relationship(
        "User",
        foreign_keys=[patient_id],
        back_populates="patient_record"
    )

    nurse = db.relationship(
        "User",
        foreign_keys=[nurse_id],
        back_populates="nurse_records"
    )

class Appointment(db.Model):
    id = db.Column(
        db.Integer,
        primary_key=True
    )

    patient_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False
    )

    appointment_date = db.Column(
        db.Date,
        nullable=False
    )

    appointment_time = db.Column(
        db.Time,
        nullable=False
    )

    reason = db.Column(
        db.String(255),
        nullable=False
    )

    status = db.Column(
        db.String(50),
        nullable=False,
        default="Scheduled"
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    patient = db.relationship(
        "User",
        foreign_keys=[patient_id],
        back_populates="appointments"
    )