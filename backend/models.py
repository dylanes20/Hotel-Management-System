"""Mapeo del esquema MySQL existente."""

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Index, PrimaryKeyConstraint, UniqueConstraint

from . import db


class Guest(db.Model):
    __tablename__ = "guest"
    __table_args__ = (
        PrimaryKeyConstraint("guest_id", name="pk_guest"),
        UniqueConstraint("identification_number", name="uq_guest_identification_number"),
        UniqueConstraint("email", name="uq_guest_email"),
        {"mysql_engine": "InnoDB"},
    )

    guest_id = db.Column(db.Integer, nullable=False, autoincrement=True)
    full_name = db.Column(db.String(100), nullable=False)
    identification_number = db.Column(db.String(30), nullable=False)
    phone = db.Column(db.String(20), nullable=True)
    email = db.Column(db.String(100), nullable=True)


class RoomType(db.Model):
    __tablename__ = "room_type"
    __table_args__ = (
        PrimaryKeyConstraint("room_type_id", name="pk_room_type"),
        UniqueConstraint("name", name="uq_room_type_name"),
        CheckConstraint(
            'capacity > 0',
            name="ck_room_type_capacity_positive",
        ),
        CheckConstraint(
            'base_nightly_rate >= 0',
            name="ck_room_type_rate_not_negative",
        ),
        {"mysql_engine": "InnoDB"},
    )

    room_type_id = db.Column(db.Integer, nullable=False, autoincrement=True)
    name = db.Column(db.String(50), nullable=False)
    capacity = db.Column(db.Integer, nullable=False)
    base_nightly_rate = db.Column(db.Numeric(10, 2), nullable=False)


class Room(db.Model):
    __tablename__ = "room"
    __table_args__ = (
        PrimaryKeyConstraint("room_id", name="pk_room"),
        UniqueConstraint("room_number", name="uq_room_room_number"),
        CheckConstraint(
            "status IN ('available','maintenance','out_of_service')",
            name="ck_room_status_valid",
        ),
        ForeignKeyConstraint(
            ["room_type_id"], ["room_type.room_type_id"],
            name="fk_room_room_type", ondelete="RESTRICT", onupdate="CASCADE",
        ),
        {"mysql_engine": "InnoDB"},
    )

    room_id = db.Column(db.Integer, nullable=False, autoincrement=True)
    room_type_id = db.Column(db.Integer, nullable=False)
    room_number = db.Column(db.String(10), nullable=False)
    floor = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), nullable=False, server_default='available')


class Reservation(db.Model):
    __tablename__ = "reservation"
    __table_args__ = (
        PrimaryKeyConstraint("reservation_id", name="pk_reservation"),
        CheckConstraint(
            'check_out_date > check_in_date',
            name="ck_reservation_dates_ordered",
        ),
        CheckConstraint(
            'actual_check_out_date IS NULL OR (actual_check_in_date IS NOT NULL AND actual_check_out_date >= actual_check_in_date)',
            name="ck_reservation_actual_dates_ordered",
        ),
        CheckConstraint(
            'nightly_rate >= 0',
            name="ck_reservation_rate_not_negative",
        ),
        CheckConstraint(
            "status IN ('booked','checked_in','checked_out','cancelled')",
            name="ck_reservation_status_valid",
        ),
        ForeignKeyConstraint(
            ["guest_id"], ["guest.guest_id"],
            name="fk_reservation_guest", ondelete="RESTRICT", onupdate="CASCADE",
        ),
        ForeignKeyConstraint(
            ["room_id"], ["room.room_id"],
            name="fk_reservation_room", ondelete="RESTRICT", onupdate="CASCADE",
        ),
        Index('idx_reservation_room_id_dates', 'room_id', 'check_in_date', 'check_out_date'),
        Index('idx_reservation_guest_id', 'guest_id'),
        Index('idx_reservation_status', 'status'),
        Index('idx_reservation_check_in_date', 'check_in_date'),
        {"mysql_engine": "InnoDB"},
    )

    reservation_id = db.Column(db.Integer, nullable=False, autoincrement=True)
    guest_id = db.Column(db.Integer, nullable=False)
    room_id = db.Column(db.Integer, nullable=False)
    check_in_date = db.Column(db.Date, nullable=False)
    check_out_date = db.Column(db.Date, nullable=False)
    nightly_rate = db.Column(db.Numeric(10, 2), nullable=False)
    status = db.Column(db.String(20), nullable=False, server_default='booked')
    actual_check_in_date = db.Column(db.Date, nullable=True)
    actual_check_out_date = db.Column(db.Date, nullable=True)


class Payment(db.Model):
    __tablename__ = "payment"
    __table_args__ = (
        PrimaryKeyConstraint("payment_id", name="pk_payment"),
        CheckConstraint(
            'amount > 0',
            name="ck_payment_amount_positive",
        ),
        CheckConstraint(
            "payment_method IN ('cash','credit_card','debit_card','bank_transfer')",
            name="ck_payment_method_valid",
        ),
        CheckConstraint(
            "status IN ('pending','completed','refunded')",
            name="ck_payment_status_valid",
        ),
        ForeignKeyConstraint(
            ["reservation_id"], ["reservation.reservation_id"],
            name="fk_payment_reservation", ondelete="RESTRICT", onupdate="CASCADE",
        ),
        Index('idx_payment_reservation_id', 'reservation_id'),
        {"mysql_engine": "InnoDB"},
    )

    payment_id = db.Column(db.Integer, nullable=False, autoincrement=True)
    reservation_id = db.Column(db.Integer, nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    payment_date = db.Column(db.Date, nullable=False)
    payment_method = db.Column(db.String(30), nullable=False)
    status = db.Column(db.String(20), nullable=False, server_default='completed')


class Service(db.Model):
    __tablename__ = "service"
    __table_args__ = (
        PrimaryKeyConstraint("service_id", name="pk_service"),
        UniqueConstraint("name", name="uq_service_name"),
        CheckConstraint(
            'standard_price >= 0',
            name="ck_service_price_not_negative",
        ),
        CheckConstraint(
            "availability_status IN ('available','unavailable')",
            name="ck_service_availability_valid",
        ),
        {"mysql_engine": "InnoDB"},
    )

    service_id = db.Column(db.Integer, nullable=False, autoincrement=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255), nullable=True)
    standard_price = db.Column(db.Numeric(10, 2), nullable=False)
    availability_status = db.Column(db.String(20), nullable=False, server_default='available')


class ServiceCharge(db.Model):
    __tablename__ = "service_charge"
    __table_args__ = (
        PrimaryKeyConstraint("service_charge_id", name="pk_service_charge"),
        CheckConstraint(
            'quantity > 0',
            name="ck_service_charge_quantity_positive",
        ),
        CheckConstraint(
            'unit_price >= 0',
            name="ck_service_charge_price_not_negative",
        ),
        ForeignKeyConstraint(
            ["reservation_id"], ["reservation.reservation_id"],
            name="fk_service_charge_reservation", ondelete="RESTRICT", onupdate="CASCADE",
        ),
        ForeignKeyConstraint(
            ["service_id"], ["service.service_id"],
            name="fk_service_charge_service", ondelete="RESTRICT", onupdate="CASCADE",
        ),
        Index('idx_service_charge_reservation_id', 'reservation_id'),
        {"mysql_engine": "InnoDB"},
    )

    service_charge_id = db.Column(db.Integer, nullable=False, autoincrement=True)
    reservation_id = db.Column(db.Integer, nullable=False)
    service_id = db.Column(db.Integer, nullable=False)
    service_date = db.Column(db.Date, nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)
