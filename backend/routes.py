from flask import Blueprint, jsonify, request, url_for
from sqlalchemy import case, select
from sqlalchemy.exc import DataError, IntegrityError, OperationalError
from werkzeug.exceptions import BadRequest, Conflict, NotFound

from . import db
from .models import Guest, Reservation, Room, RoomType
from .validation import BLOCKING_RESERVATION_STATUSES, parsed_value, validate_stay_dates, validated_fields


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


def overlapping_stays(room_id, check_in, check_out, exclude_id=None):
    query = select(Reservation.reservation_id).where(
        Reservation.room_id == room_id,
        Reservation.status.in_(BLOCKING_RESERVATION_STATUSES),
        Reservation.check_in_date < check_out,
        Reservation.check_out_date > check_in,
    )
    if exclude_id is not None:
        query = query.where(Reservation.reservation_id != exclude_id)
    return query


def requested_stay():
    columns = Reservation.__table__.columns
    check_in = parsed_value(columns.check_in_date, request.args.get("check_in_date"))
    check_out = parsed_value(columns.check_out_date, request.args.get("check_out_date"))
    validate_stay_dates(check_in, check_out)
    return check_in, check_out


@api.get("/rooms/overview")
def room_overview():
    overlapping = None
    if "check_in_date" in request.args or "check_out_date" in request.args:
        check_in, check_out = requested_stay()
        overlapping = overlapping_stays(Room.room_id, check_in, check_out).exists()
    if overlapping is None:
        status = case((Room.status == "available", "operational"), else_=Room.status)
    else:
        status = case(
            (Room.status != "available", Room.status),
            (overlapping, "reserved"),
            else_="available",
        )
    query = select(Room, RoomType.name, RoomType.capacity, RoomType.base_nightly_rate, status).join(
        RoomType, Room.room_type_id == RoomType.room_type_id,
    ).order_by(Room.room_number)
    return jsonify([
        {
            **serialize(room), "room_type_name": type_name, "capacity": capacity,
            "base_nightly_rate": rate, "display_status": display_status,
        }
        for room, type_name, capacity, rate, display_status in db.session.execute(query)
    ])


@api.get("/rooms/availability")
def room_availability():
    columns = Reservation.__table__.columns
    check_in, check_out = requested_stay()
    exclude_id = request.args.get("exclude_reservation_id")
    if exclude_id is not None:
        if not exclude_id.isascii() or not exclude_id.isdecimal() or len(exclude_id) > 10:
            raise BadRequest("El identificador de reserva no es válido.")
        exclude_id = parsed_value(columns.reservation_id, int(exclude_id))
        if db.session.get(Reservation, exclude_id) is None:
            raise NotFound("La reserva indicada no existe.")

    overlap = overlapping_stays(Room.room_id, check_in, check_out, exclude_id)
    query = select(Room).where(
        Room.status == "available",
        ~overlap.exists(),
    ).order_by(Room.room_number)
    return jsonify([serialize(room) for room in db.session.scalars(query)])


def validate_reservation(values, current=None):
    def field(name):
        if name in values:
            return values[name]
        return getattr(current, name, None)

    check_in, check_out = field("check_in_date"), field("check_out_date")
    validate_stay_dates(check_in, check_out)
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
    status = field("status")
    same_stay = current is not None and (
        room_id, check_in, check_out
    ) == (current.room_id, current.check_in_date, current.check_out_date)
    if current is not None and current.status == "checked_out" and (
        not same_stay or status != "checked_out"
    ):
        raise Conflict("Las fechas, la habitación y el estado de una reserva finalizada se conservan.")
    if status == "cancelled":
        return
    if status == "checked_out" and same_stay and current.status != "cancelled":
        # Cerrar una estancia existente también debe ser posible si el cuarto
        # pasó a mantenimiento después de hospedar al cliente.
        return
    if room.status != "available":
        raise Conflict("La habitación está en mantenimiento o fuera de servicio.")
    overlap = overlapping_stays(room_id, check_in, check_out, current.reservation_id if current else None)
    if db.session.scalar(overlap.limit(1)) is not None:
        raise Conflict("La habitación ya tiene una reserva para esas fechas.")


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
    duplicate = "Ya existe un registro con ese valor único."
    if code == 1062:
        detail = str(error.orig)
        if "uq_guest_identification_number" in detail:
            duplicate = "Ya existe un huésped con ese número de identificación."
        elif "uq_guest_email" in detail:
            duplicate = "Ya existe un huésped con ese correo electrónico."
    connection_error = (503, "No se pudo conectar con la base de datos. Inténtalo de nuevo.")
    messages = {
        1062: (409, duplicate),
        2002: connection_error,
        2003: connection_error,
        2006: connection_error,
        2013: connection_error,
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
