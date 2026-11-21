import re
from datetime import date
from decimal import Decimal, InvalidOperation

from sqlalchemy import Date, Integer, Numeric, String
from werkzeug.exceptions import BadRequest


ROOM_STATUSES = ("available", "maintenance", "out_of_service")
ACTIVE_RESERVATION_STATUSES = ("booked", "checked_in")
RESERVATION_STATUSES = (*ACTIVE_RESERVATION_STATUSES, "checked_out", "cancelled")


def validated_fields(model, payload, *, replacing=False):
    if not isinstance(payload, dict) or not payload:
        raise BadRequest("Se requiere un objeto JSON con campos.")
    writable = {column.key: column for column in model.__table__.columns if not column.primary_key}
    unknown = payload.keys() - writable.keys()
    if unknown:
        raise BadRequest("Campos desconocidos o de solo lectura: " + ", ".join(sorted(unknown)))

    values = {}
    for name, column in writable.items():
        if name in payload:
            values[name] = parsed_value(column, payload[name])
        elif replacing:
            if column.server_default is not None:
                values[name] = column.server_default.arg
            elif column.nullable:
                values[name] = None
            else:
                raise BadRequest(f"Falta el campo {name}.")
    return values


def parsed_value(column, value):
    name = column.key
    if value is None and column.nullable:
        return None

    if isinstance(column.type, String):
        if isinstance(value, str) and value.strip() and len(value.strip()) <= column.type.length:
            value = value.strip()
            if name != "status":
                return value
            allowed = ROOM_STATUSES if column.table.name == "room" else RESERVATION_STATUSES
            if value in allowed:
                return value
            raise BadRequest(f"{name} debe ser uno de: {', '.join(allowed)}.")
        raise BadRequest(f"{name} debe ser texto de 1 a {column.type.length} caracteres.")

    if isinstance(column.type, Integer):
        lower_bound = 1 if name.endswith("_id") else -(2**31)
        if type(value) is int and lower_bound <= value < 2**31:
            return value
        raise BadRequest(f"{name} debe ser un entero válido.")

    if isinstance(column.type, Date):
        if isinstance(value, str) and re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
            try:
                parsed = date.fromisoformat(value)
                if parsed.year >= 1000:
                    return parsed
            except ValueError:
                pass
        raise BadRequest(f"{name} debe ser una fecha válida en formato AAAA-MM-DD.")

    if isinstance(column.type, Numeric):
        if type(value) in (str, int, float):
            try:
                amount = Decimal(str(value))
                if amount.is_finite() and 0 <= amount <= Decimal("99999999.99"):
                    rounded = amount.quantize(Decimal("0.01"))
                    if rounded == amount:
                        return rounded
            except InvalidOperation:
                pass
        raise BadRequest(f"{name} debe ser un importe no negativo con hasta dos decimales.")

    raise TypeError(f"Tipo de columna no compatible: {column.type}")
