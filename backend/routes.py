from flask import Blueprint, jsonify, request, url_for
from sqlalchemy import select
from sqlalchemy.exc import DataError, IntegrityError, OperationalError
from werkzeug.exceptions import BadRequest, Conflict, NotFound

from . import db
from .models import Guest, Reservation, Room, RoomType
from .validation import ACTIVE_RESERVATION_STATUSES, validated_fields


api = Blueprint("api", __name__)
RESOURCES = {"guests": Guest, "rooms": Room, "reservations": Reservation}


def model_for(resource):
    model = RESOURCES.get(resource)
    if model is None:
        raise NotFound("Recurso inexistente.")
    return model


def serialize(record):
    # Flask serializa Decimal como texto, preservando la precisión monetaria.
    return {
        column.key: value.isoformat() if hasattr(value, "isoformat") else value
        for column in record.__table__.columns
        for value in (getattr(record, column.key),)
    }


def validate_room(values):
    if "room_type_id" in values and db.session.get(RoomType, values["room_type_id"]) is None:
        raise BadRequest("El tipo de habitación indicado no existe.")


def validate_reservation(values, current=None):
    def field(name):
        if name in values:
            return values[name]
        return getattr(current, name, None)

    check_in, check_out = field("check_in_date"), field("check_out_date")
    if check_out <= check_in:
        raise BadRequest("La salida debe ser posterior a la entrada.")
    actual_in = field("actual_check_in_date")
    actual_out = field("actual_check_out_date")
    if actual_out is not None and (actual_in is None or actual_out < actual_in):
        raise BadRequest("La salida real requiere una entrada real igual o anterior.")

    if db.session.get(Guest, field("guest_id")) is None:
        raise BadRequest("El huésped indicado no existe.")
    room_id = field("room_id")
    # Todas las altas y ediciones de reservas comparten el bloqueo de la
    # habitación destino. READ COMMITTED permite ver la reserva recién confirmada
    # por otra transacción una vez obtenido el bloqueo.
    room = db.session.get(Room, room_id, with_for_update=True)
    if room is None:
        raise BadRequest("La habitación indicada no existe.")
    if field("status") not in ACTIVE_RESERVATION_STATUSES:
        return
    if room.status != "available":
        raise Conflict("La habitación no está disponible.")
    overlap = select(Reservation.reservation_id).where(
        Reservation.room_id == room_id,
        Reservation.status.in_(ACTIVE_RESERVATION_STATUSES),
        Reservation.check_in_date < check_out,
        Reservation.check_out_date > check_in,
    )
    if current is not None:
        overlap = overlap.where(Reservation.reservation_id != current.reservation_id)
    if db.session.scalar(overlap.limit(1)) is not None:
        raise Conflict("La habitación ya tiene una reserva activa en esas fechas.")


def validate(model, values, current=None):
    if model is Room:
        validate_room(values)
    elif model is Reservation:
        validate_reservation(values, current)


@api.errorhandler(IntegrityError)
@api.errorhandler(DataError)
@api.errorhandler(OperationalError)
def database_error(error):
    db.session.rollback()
    code = error.orig.args[0] if error.orig.args else None
    referenced_record = (409, "El registro tiene datos asociados y no se puede eliminar.")
    messages = {
        1062: (409, "Ya existe un registro con ese valor único."),
        1217: referenced_record,
        1451: referenced_record,
        1452: (400, "El registro referenciado no existe."),
        3819: (400, "Los datos incumplen una restricción."),
        1205: (409, "La operación encontró un conflicto concurrente. Inténtalo de nuevo."),
        1213: (409, "La operación encontró un conflicto concurrente. Inténtalo de nuevo."),
    }
    if code not in messages:
        from flask import current_app

        current_app.logger.error("Error de base de datos %s (%s)", type(error).__name__, code)
    status, message = messages.get(code, (500, "No se pudo completar la operación en la base de datos."))
    return jsonify(error=message), status


@api.route("/<resource>", methods=["GET", "POST"])
def collection(resource):
    model = model_for(resource)
    primary_key = model.__mapper__.primary_key[0]
    if request.method in ("GET", "HEAD"):
        records = db.session.scalars(select(model).order_by(primary_key))
        return jsonify([serialize(record) for record in records])

    values = validated_fields(model, request.get_json(), replacing=True)
    validate(model, values)
    record = model(**values)
    db.session.add(record)
    db.session.flush()
    data = serialize(record)
    db.session.commit()
    return jsonify(data), 201, {
        "Location": url_for("api.item", resource=resource, record_id=data[primary_key.key])
    }


@api.route("/<resource>/<int:record_id>", methods=["GET", "PUT", "PATCH", "DELETE"])
def item(resource, record_id):
    model = model_for(resource)
    reading = request.method in ("GET", "HEAD")
    if record_id >= 2**31:
        raise NotFound("Registro inexistente.")
    record = db.session.get(model, record_id, with_for_update=not reading)
    if record is None:
        raise NotFound("Registro inexistente.")
    if reading:
        return jsonify(serialize(record))
    if request.method == "DELETE":
        db.session.delete(record)
        db.session.commit()
        return "", 204

    values = validated_fields(model, request.get_json(), replacing=request.method == "PUT")
    validate(model, values, record)
    for name, value in values.items():
        setattr(record, name, value)
    db.session.flush()
    data = serialize(record)
    db.session.commit()
    return jsonify(data)
