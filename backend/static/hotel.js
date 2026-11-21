"use strict";

const byId = (id) => document.getElementById(id);
const apiRoot = document.body.dataset.api.replace(/\/reservations$/, "");
const rows = byId("rows");
const search = byId("search");
const dialog = byId("reservation-dialog");
const form = byId("reservation-form");
const saveButton = byId("save-reservation");
const deleteButton = byId("confirm-delete");
const closeButton = byId("dialog-close");
const addButton = byId("new-reservation");

const statuses = {
  booked: ["Confirmada", "good"], checked_in: ["En estancia", "good"],
  checked_out: ["Finalizada", ""], cancelled: ["Cancelada", "stop"],
  available: ["Disponible", "good"], maintenance: ["Mantenimiento", "warn"],
  out_of_service: ["Fuera de servicio", "stop"],
};

const sections = {
  reservations: {
    name: "Reservas", list: "Listado de reservas", description: "Consulta y gestiona las estancias del hotel.",
    columns: ["Reserva", "Huésped", "Habitación", "Entrada", "Salida", "Estado", "Acciones"],
  },
  guests: {
    name: "Huéspedes", list: "Directorio de huéspedes", description: "Consulta la identificación y los datos de contacto.",
    columns: ["Huésped", "Documento", "Teléfono", "Correo electrónico"],
  },
  rooms: {
    name: "Habitaciones", list: "Inventario de habitaciones", description: "Consulta el estado y la ubicación de las habitaciones.",
    columns: ["Habitación", "Piso", "Tipo", "Estado"],
  },
};

let section = "reservations";
let records = [];
let guests = new Map();
let rooms = new Map();
let listRequest;
let dialogRequest;
let editingId;
let busy = false;

async function request(resource, {method = "GET", data, signal} = {}) {
  const response = await fetch(`${apiRoot}/${resource}`, {
    method, signal, cache: "no-store",
    headers: data === undefined ? {Accept: "application/json"} : {
      Accept: "application/json", "Content-Type": "application/json",
    },
    body: data === undefined ? undefined : JSON.stringify(data),
  });
  if (response.status === 204) return null;
  const result = await response.json().catch(() => null);
  if (!response.ok) {
    const error = new Error(result?.error || `La API devolvió HTTP ${response.status}.`);
    error.status = response.status;
    throw error;
  }
  if (result === null) throw new Error("La API no devolvió datos JSON válidos.");
  return result;
}

function errorMessage(error) {
  return error instanceof TypeError ? "No fue posible conectar con la API. Comprueba que Flask esté en ejecución." : error.message;
}

function message(id, text, error = false) {
  const element = byId(id);
  element.textContent = text;
  element.hidden = !text;
  element.classList.toggle("error", error);
}

function node(tag, text, className) {
  const element = document.createElement(tag);
  if (text !== undefined) element.textContent = text;
  if (className) element.className = className;
  return element;
}

function statusLabel(value) {
  return statuses[value]?.[0] ?? value;
}

function badge(value) {
  return node("span", statusLabel(value), `badge ${statuses[value]?.[1] ?? ""}`);
}

function guestName(id) {
  return guests.get(id)?.full_name ?? `Huésped #${id}`;
}

function roomName(id) {
  return rooms.get(id)?.room_number ?? `Habitación #${id}`;
}

function listValues(record) {
  if (section === "guests") return [record.full_name, record.identification_number, record.phone, record.email];
  if (section === "rooms") return [record.room_number, record.floor, record.room_type_id, badge(record.status)];
  return [
    `#${record.reservation_id}`, guestName(record.guest_id), roomName(record.room_id),
    record.check_in_date, record.check_out_date, badge(record.status),
  ];
}

function actions(record) {
  const controls = node("div", undefined, "row-actions");
  for (const [label, mode] of [["Ver", "view"], ["Editar", "edit"], ["Eliminar", "delete"]]) {
    const button = node("button", label);
    button.type = "button";
    button.setAttribute("aria-label", `${label} reserva #${record.reservation_id}`);
    button.addEventListener("click", () => openReservation(mode, record));
    controls.append(button);
  }
  return controls;
}

function renderList() {
  const term = search.value.trim().toLocaleLowerCase("es");
  const filtered = records.map((record) => [record, listValues(record)]).filter(([, values]) =>
    values.some((value) => String(value instanceof Node ? value.textContent : value ?? "").toLocaleLowerCase("es").includes(term))
  );
  rows.replaceChildren();
  for (const [record, values] of filtered) {
    const row = node("tr");
    if (section === "reservations") values.push(actions(record));
    for (const value of values) {
      const cell = node("td");
      cell.append(value ?? "—");
      row.append(cell);
    }
    rows.append(row);
  }
  byId("count").textContent = `${filtered.length} de ${records.length} registros`;
  message("list-message", filtered.length ? "" : (term ? "No hay coincidencias." : "No hay registros para mostrar."));
}

async function loadSection() {
  listRequest?.abort();
  const controller = new AbortController();
  listRequest = controller;
  const selected = section;
  const {name, list, description, columns} = sections[selected];
  byId("section-name").textContent = name;
  byId("section-description").textContent = description;
  byId("list-title").textContent = list;
  addButton.hidden = selected !== "reservations";
  addButton.disabled = true;
  search.disabled = true;
  const heading = node("tr");
  for (const title of columns) {
    const cell = node("th", title);
    cell.scope = "col";
    heading.append(cell);
  }
  byId("columns").replaceChildren(heading);
  rows.replaceChildren();
  byId("count").textContent = "";
  message("list-message", "Cargando registros…");

  try {
    const needed = selected === "reservations" ? [selected, "guests", "rooms"] : [selected];
    const [data, guestData, roomData] = await Promise.all(needed.map((resource) =>
      request(resource, {signal: controller.signal})
    ));
    if (controller.signal.aborted) return;
    records = data;
    if (selected === "reservations") {
      guests = new Map(guestData.map((guest) => [guest.guest_id, guest]));
      rooms = new Map(roomData.map((room) => [room.room_id, room]));
      addButton.disabled = !guests.size || !rooms.size;
    }
    search.disabled = false;
    renderList();
    if (selected === "reservations" && addButton.disabled) {
      message("notice", "Para crear una reserva debe existir al menos un huésped y una habitación.", true);
    }
  } catch (error) {
    if (!controller.signal.aborted) message("list-message", errorMessage(error), true);
  }
}

function selectOptions(name, entries, label, selectedId) {
  const select = form.elements.namedItem(name);
  const empty = node("option", "Selecciona una opción");
  empty.value = "";
  select.replaceChildren(empty);
  for (const [id, record] of entries) {
    const option = node("option", label(record));
    option.value = id;
    select.append(option);
  }
  select.value = selectedId ?? "";
}

function fillForm(record = {}) {
  form.reset();
  selectOptions("guest_id", guests, (guest) => guest.full_name, record.guest_id);
  selectOptions("room_id", rooms, (room) => `${room.room_number} · ${statusLabel(room.status)}`, record.room_id);
  for (const input of form.elements) {
    if (record[input.name] != null) input.value = record[input.name];
  }
  form.hidden = false;
  saveButton.hidden = false;
  form.elements.namedItem("guest_id").focus();
}

function showDetails(record) {
  const details = byId("reservation-details");
  const fields = [
    ["Huésped", guestName(record.guest_id)], ["Habitación", roomName(record.room_id)],
    ["Entrada", record.check_in_date], ["Salida", record.check_out_date],
    ["Tarifa por noche", record.nightly_rate], ["Estado", statusLabel(record.status)],
    ["Entrada real", record.actual_check_in_date], ["Salida real", record.actual_check_out_date],
  ];
  details.replaceChildren(...fields.flatMap(([label, value]) => [node("dt", label), node("dd", value ?? "—")]));
  details.hidden = false;
}

async function openReservation(mode, record) {
  if (dialog.open) return;
  editingId = record?.reservation_id;
  const controller = new AbortController();
  dialogRequest = controller;
  message("dialog-error", "");
  form.hidden = saveButton.hidden = deleteButton.hidden = true;
  byId("reservation-details").hidden = true;
  byId("delete-description").hidden = true;
  closeButton.textContent = mode === "view" ? "Cerrar" : "Cancelar";
  const titles = {create: "Nueva reserva", view: "Reserva", edit: "Editar reserva", delete: "Eliminar reserva"};
  byId("dialog-title").textContent = record ? `${titles[mode]} #${editingId}` : titles[mode];
  dialog.showModal();
  closeButton.focus();

  if (mode === "create") {
    fillForm();
  } else if (mode === "delete") {
    const description = byId("delete-description");
    description.textContent = `¿Eliminar la reserva de ${guestName(record.guest_id)} para la habitación ${roomName(record.room_id)}? Esta acción es definitiva.`;
    description.hidden = deleteButton.hidden = false;
  } else {
    try {
      const latest = await request(`reservations/${editingId}`, {signal: controller.signal});
      if (controller.signal.aborted) return;
      if (mode === "edit") fillForm(latest);
      else showDetails(latest);
    } catch (error) {
      if (!controller.signal.aborted) message("dialog-error", errorMessage(error));
    }
  }
}

function setBusy(value) {
  busy = value;
  for (const element of [saveButton, deleteButton, closeButton]) element.disabled = value;
}

async function mutate(operation, success, deleting = false) {
  if (busy) return;
  message("dialog-error", "");
  setBusy(true);
  try {
    await operation();
    dialog.close();
    message("notice", success);
    await loadSection();
  } catch (error) {
    const linkedRecords = deleting && error.status === 409 && error.message.includes("datos asociados");
    message("dialog-error", linkedRecords
      ? "No se puede eliminar la reserva porque tiene pagos o cargos asociados."
      : errorMessage(error));
  } finally {
    setBusy(false);
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const data = Object.fromEntries(new FormData(form));
  if (data.check_out_date <= data.check_in_date) {
    message("dialog-error", "La salida debe ser posterior a la entrada.");
    form.elements.namedItem("check_out_date").focus();
    return;
  }
  if (data.actual_check_out_date && (!data.actual_check_in_date || data.actual_check_out_date < data.actual_check_in_date)) {
    message("dialog-error", "La salida real requiere una entrada real igual o anterior.");
    form.elements.namedItem("actual_check_out_date").focus();
    return;
  }
  data.guest_id = Number(data.guest_id);
  data.room_id = Number(data.room_id);
  data.actual_check_in_date ||= null;
  data.actual_check_out_date ||= null;
  const resource = editingId ? `reservations/${editingId}` : "reservations";
  const method = editingId ? "PATCH" : "POST";
  void mutate(() => request(resource, {method, data}), editingId ? "Reserva actualizada." : "Reserva creada.");
});

deleteButton.addEventListener("click", () => {
  void mutate(() => request(`reservations/${editingId}`, {method: "DELETE"}), "Reserva eliminada.", true);
});
closeButton.addEventListener("click", () => dialog.close());
dialog.addEventListener("cancel", (event) => { if (busy) event.preventDefault(); });
dialog.addEventListener("close", () => dialogRequest?.abort());
addButton.addEventListener("click", () => openReservation("create"));
search.addEventListener("input", renderList);
byId("reload").addEventListener("click", () => { message("notice", ""); void loadSection(); });
for (const button of document.querySelectorAll("[data-section]")) {
  button.addEventListener("click", () => {
    document.querySelector("[aria-current]").removeAttribute("aria-current");
    button.setAttribute("aria-current", "page");
    section = button.dataset.section;
    search.value = "";
    message("notice", "");
    void loadSection();
  });
}
void loadSection();
