"use strict";

const byId = (id) => document.getElementById(id);
const apiRoot = document.body.dataset.api.replace(/\/reservations$/, "");
const rows = byId("rows");
const roomDates = byId("room-dates");
const roomsCheckIn = byId("rooms-check-in");
const roomsCheckOut = byId("rooms-check-out");
const search = byId("search");
const dialog = byId("reservation-dialog");
const form = byId("reservation-form");
const saveButton = byId("save-reservation");
const deleteButton = byId("confirm-delete");
const cancelButton = byId("confirm-cancel");
const roomField = form.elements.namedItem("room_id");
const arrival = form.elements.namedItem("check_in_date");
const departure = form.elements.namedItem("check_out_date");
const stayStatus = form.elements.namedItem("status");
const guestSearch = byId("guest-search");
const closeButton = byId("dialog-close");
const addButton = byId("new-reservation");
const guestForm = byId("guest-form");
const guestButton = byId("add-guest");
const saveGuest = byId("save-guest");
const guestBack = byId("guest-back");

const statuses = {
  booked: ["Confirmada", "good"], checked_in: ["En estancia", "good"],
  checked_out: ["Finalizada", ""], cancelled: ["Cancelada", "stop"],
  available: ["Disponible", "good"], reserved: ["Reservada", "reserved"],
  operational: ["Operativa", ""], maintenance: ["En mantenimiento", "warn"],
  out_of_service: ["Fuera de servicio", "stop"],
};

const sections = {
  reservations: {
    name: "Reservas", description: "Consulta y gestiona las estancias del hotel.",
  },
  guests: {
    name: "Huéspedes", description: "Consulta la identificación y los datos de contacto.",
  },
  rooms: {
    name: "Habitaciones", description: "Consulta el estado y la ubicación de las habitaciones. Imágenes ilustrativas.",
  },
};

let section = "reservations";
let records = [];
let guests = new Map();
let rooms = new Map();
let listRequest;
let dialogRequest;
let editingId;
let originalStay;
let guestEditId;
let availabilityRequest;
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

const nightlyCurrency = new Intl.NumberFormat("es-CO", {style: "currency", currency: "USD"});

function roomPhoto(type) {
  const {single, double, junior, family, suite, room} = document.body.dataset;
  switch (type.toLocaleLowerCase("es")) {
    case "individual": return single;
    case "doble": return double;
    case "suite junior": return junior;
    case "familiar": return family;
    default: return type.toLocaleLowerCase("es").includes("suite") ? suite : room;
  }
}

function recordContent(record) {
  if (section === "guests") {
    return {
      title: record.full_name,
      fields: [["Documento", record.identification_number], ["Teléfono", record.phone], ["Correo electrónico", record.email]],
    };
  }
  if (section === "rooms") {
    return {
      title: `Habitación ${record.room_number}`,
      fields: [
        ["Piso", record.floor], ["Tipo", record.room_type_name],
        ["Capacidad", record.capacity], ["Tarifa por noche", nightlyCurrency.format(record.base_nightly_rate)],
      ],
      status: record.display_status,
      image: roomPhoto(record.room_type_name),
    };
  }
  return {
    title: guestName(record.guest_id),
    fields: [
      ["Reserva", `#${record.reservation_id}`], ["Habitación", roomName(record.room_id)],
      ["Entrada", record.check_in_date], ["Salida", record.check_out_date],
    ],
  };
}

function descriptionList(fields) {
  return fields.map(([label, value]) => {
    const group = node("div");
    group.append(node("dt", label), node("dd", value ?? "—"));
    return group;
  });
}

function recordCard(record, {title, fields, image, status = record.status}) {
  const card = node("article", undefined, "record");
  const content = node("div", undefined, "record-content");
  const heading = node("header", undefined, "record-header");
  heading.append(node("h3", title));
  if (status) heading.append(badge(status));
  const details = node("dl");
  details.append(...descriptionList(fields));
  if (image) {
    const photo = node("img");
    photo.src = image;
    photo.alt = "";
    photo.loading = "lazy";
    card.append(photo);
  }
  content.append(heading, details);
  if (section !== "rooms") content.append(actions(record));
  card.append(content);
  return card;
}

function actions(record) {
  const controls = node("div", undefined, "row-actions");
  const isGuest = section === "guests";
  const options = [["Ver", "view"], ["Editar", "edit"]];
  if (!isGuest) {
    if (["booked", "checked_in"].includes(record.status)) options.push(["Cancelar", "cancel"]);
    options.push(["Eliminar", "delete"]);
  }
  for (const [label, mode] of options) {
    const button = node("button", label);
    button.type = "button";
    const context = isGuest ? `a ${record.full_name}` : `reserva #${record.reservation_id}`;
    button.setAttribute("aria-label", `${label} ${context}`);
    button.addEventListener("click", () => {
      if (isGuest) void openGuest(mode, record.guest_id);
      else void openReservation(mode, record);
    });
    controls.append(button);
  }
  return controls;
}

function renderList() {
  const term = search.value.trim().toLocaleLowerCase("es");
  const filtered = records.map((record) => [record, recordContent(record)]).filter(([record, content]) =>
    [content.title, ...content.fields.map(([, value]) => value), statusLabel(content.status ?? record.status)].some((value) =>
      String(value ?? "").toLocaleLowerCase("es").includes(term)
    )
  );
  rows.replaceChildren(...filtered.map(([record, content]) => recordCard(record, content)));
  byId("count").textContent = `${filtered.length} de ${records.length} registros`;
  message("list-message", filtered.length ? "" : (term ? "No hay coincidencias." : "No hay registros para mostrar."));
}

function roomOverviewResource() {
  const start = roomsCheckIn.value;
  const end = roomsCheckOut.value;
  if (!start || !end) {
    message("room-date-message", "Selecciona ambas fechas para consultar disponibilidad.");
    return "rooms/overview";
  }
  if (!roomsCheckIn.validity.valid || !roomsCheckOut.validity.valid || end <= start) {
    message("room-date-message", "Selecciona fechas válidas. La salida debe ser posterior a la entrada.", true);
    return "rooms/overview";
  }
  message("room-date-message", "Disponibilidad para el intervalo seleccionado.");
  return `rooms/overview?${new URLSearchParams({check_in_date: start, check_out_date: end})}`;
}

async function loadSection() {
  listRequest?.abort();
  const controller = new AbortController();
  listRequest = controller;
  const selected = section;
  const {name, description} = sections[selected];
  byId("section-name").textContent = name;
  byId("section-description").textContent = description;
  roomDates.hidden = selected !== "rooms";
  addButton.hidden = selected !== "reservations";
  addButton.disabled = true;
  search.disabled = true;
  rows.replaceChildren();
  byId("count").textContent = "";
  message("list-message", "Cargando registros…");

  try {
    const needed = selected === "reservations"
      ? [selected, "guests", "rooms"]
      : [selected === "rooms" ? roomOverviewResource() : selected];
    const [data, guestData, roomData] = await Promise.all(needed.map((resource) =>
      request(resource, {signal: controller.signal})
    ));
    if (controller.signal.aborted) return;
    records = data;
    if (selected === "reservations") {
      guests = new Map(guestData.map((guest) => [guest.guest_id, guest]));
      rooms = new Map(roomData.map((room) => [room.room_id, room]));
      addButton.disabled = !rooms.size;
    }
    search.disabled = false;
    renderList();
    if (selected === "reservations" && addButton.disabled) {
      message("notice", "Para crear una reserva debe existir al menos una habitación.", true);
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

function fillGuestOptions(selectedId = form.elements.namedItem("guest_id").value) {
  const term = guestSearch.value.trim().toLocaleLowerCase("es");
  const filtered = [...guests].filter(([id, guest]) =>
    id === Number(selectedId) || [guest.full_name, guest.identification_number, guest.email]
      .some((value) => value?.toLocaleLowerCase("es").includes(term))
  );
  selectOptions("guest_id", filtered, (guest) => guest.full_name, selectedId);
  if (!filtered.length) form.elements.namedItem("guest_id").options[0].textContent = "No se encontraron huéspedes";
}

async function refreshAvailability(preferred = roomField.value) {
  availabilityRequest?.abort();
  const controller = new AbortController();
  availabilityRequest = controller;
  const retry = byId("retry-availability");
  retry.hidden = true;
  selectOptions("room_id", [], roomName);
  roomField.disabled = saveButton.disabled = true;

  const historical = originalStay && (originalStay.status === "checked_out" || stayStatus.value === "cancelled");
  const closing = originalStay && originalStay.status !== "cancelled" && stayStatus.value === "checked_out"
    && arrival.value === originalStay.check_in_date && departure.value === originalStay.check_out_date;
  if (historical || closing) {
    const id = originalStay.room_id;
    selectOptions("room_id", [[id, id]], roomName, id);
    roomField.disabled = false;
    saveButton.disabled = busy;
    message("availability-message", "Se conserva la habitación de la reserva.");
    return;
  }
  if (!arrival.value || !departure.value || !arrival.validity.valid || !departure.validity.valid) {
    message("availability-message", "Selecciona las fechas para consultar habitaciones libres.");
    return;
  }
  if (departure.value <= arrival.value) {
    message("availability-message", "La salida debe ser posterior a la entrada.", true);
    return;
  }

  const params = new URLSearchParams({check_in_date: arrival.value, check_out_date: departure.value});
  if (editingId !== undefined) params.set("exclude_reservation_id", editingId);
  message("availability-message", "Consultando habitaciones…");
  try {
    const available = await request(`rooms/availability?${params}`, {signal: controller.signal});
    if (controller.signal.aborted) return;
    selectOptions("room_id", available.map((room) => [room.room_id, room]), (room) => room.room_number, preferred);
    roomField.disabled = !available.length;
    saveButton.disabled = busy || roomField.disabled;
    message("availability-message", available.length
      ? `Habitaciones disponibles: ${available.length}.`
      : "No hay habitaciones libres para esas fechas. Prueba otras fechas.");
  } catch (error) {
    if (controller.signal.aborted) return;
    message("availability-message", errorMessage(error), true);
    retry.hidden = false;
  }
}

function fillForm(record = {}) {
  form.reset();
  originalStay = record.reservation_id ? record : undefined;
  guestSearch.value = "";
  fillGuestOptions(record.guest_id ?? "");
  for (const input of form.elements) {
    if (record[input.name] != null && input !== roomField) input.value = record[input.name];
  }
  const completed = record.status === "checked_out";
  arrival.readOnly = departure.readOnly = completed;
  for (const option of stayStatus.options) {
    option.disabled = completed ? option.value !== "checked_out" :
      option.value === "cancelled" && record.status !== "cancelled";
    option.hidden = option.disabled;
  }
  form.hidden = saveButton.hidden = false;
  void refreshAvailability(record.room_id ?? "");
  arrival.focus();
}

function showDetails(record) {
  const details = byId("reservation-details");
  const fields = [
    ["Huésped", guestName(record.guest_id)], ["Habitación", roomName(record.room_id)],
    ["Entrada", record.check_in_date], ["Salida", record.check_out_date],
    ["Tarifa por noche", record.nightly_rate], ["Estado", statusLabel(record.status)],
    ["Entrada real", record.actual_check_in_date], ["Salida real", record.actual_check_out_date],
  ];
  details.replaceChildren(...descriptionList(fields));
  details.hidden = false;
}

async function openReservation(mode, record) {
  if (dialog.open || busy) return;
  editingId = record?.reservation_id;
  guestEditId = undefined;
  const controller = new AbortController();
  dialogRequest = controller;
  message("dialog-error", "");
  message("guest-notice", "");
  guestForm.hidden = true;
  guestButton.setAttribute("aria-expanded", "false");
  form.hidden = saveButton.hidden = deleteButton.hidden = cancelButton.hidden = true;
  byId("reservation-details").hidden = true;
  byId("delete-description").hidden = true;
  closeButton.textContent = mode === "view" ? "Cerrar" : "Cancelar";
  const titles = {create: "Nueva reserva", view: "Reserva", edit: "Editar reserva", delete: "Eliminar reserva", cancel: "Cancelar reserva"};
  byId("dialog-title").textContent = record ? `${titles[mode]} #${editingId}` : titles[mode];
  dialog.showModal();
  closeButton.focus();

  if (mode === "create") {
    fillForm();
  } else if (mode === "delete" || mode === "cancel") {
    const description = byId("delete-description");
    description.textContent = mode === "cancel"
      ? "¿Cancelar esta reserva? Las noches volverán a estar disponibles y se conservará el historial."
      : `¿Eliminar la reserva de ${guestName(record.guest_id)} para la habitación ${roomName(record.room_id)}? Esta acción es definitiva.`;
    description.hidden = false;
    deleteButton.hidden = mode !== "delete";
    cancelButton.hidden = mode !== "cancel";
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
  for (const element of [deleteButton, cancelButton, closeButton, saveGuest, guestBack]) element.disabled = value;
  saveButton.disabled = value || roomField.disabled;
}

async function mutate(operation, success, {deleting = false, savingStay = false} = {}) {
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
    if (savingStay && error.status === 409) await refreshAvailability();
  } finally {
    setBusy(false);
  }
}

async function openGuest(mode, id) {
  if (dialog.open || busy) return;
  guestEditId = id;
  const controller = new AbortController();
  dialogRequest = controller;
  form.hidden = saveButton.hidden = deleteButton.hidden = cancelButton.hidden = guestForm.hidden = true;
  byId("reservation-details").hidden = true;
  byId("delete-description").hidden = true;
  message("dialog-error", "");
  message("guest-notice", "");
  byId("dialog-title").textContent = mode === "edit" ? "Editar huésped" : "Datos del huésped";
  closeButton.textContent = "Cerrar";
  dialog.showModal();
  closeButton.focus();
  try {
    const guest = await request(`guests/${id}`, {signal: controller.signal});
    if (controller.signal.aborted) return;
    if (mode === "edit") {
      byId("guest-form-title").hidden = true;
      guestBack.hidden = true;
      saveGuest.textContent = "Guardar cambios";
      guestForm.reset();
      for (const input of guestForm.elements) {
        if (input.name) input.value = guest[input.name] ?? "";
      }
      guestForm.hidden = false;
      guestForm.elements.namedItem("full_name").focus();
    } else {
      const details = byId("reservation-details");
      details.replaceChildren(...descriptionList([
        ["Nombre completo", guest.full_name], ["Documento", guest.identification_number],
        ["Teléfono", guest.phone], ["Correo electrónico", guest.email],
      ]));
      details.hidden = false;
    }
  } catch (error) {
    if (!controller.signal.aborted) message("dialog-error", errorMessage(error));
  }
}

function showGuestForm(open) {
  guestForm.hidden = !open;
  form.hidden = saveButton.hidden = open;
  guestButton.setAttribute("aria-expanded", String(open));
  message("dialog-error", "");
  message("guest-notice", "");
  if (open) {
    byId("guest-form-title").hidden = false;
    guestBack.hidden = false;
    saveGuest.textContent = "Registrar huésped";
    guestForm.reset();
    guestForm.elements.namedItem("full_name").focus();
  } else {
    form.elements.namedItem("guest_id").focus();
  }
}

guestButton.addEventListener("click", () => showGuestForm(true));
guestBack.addEventListener("click", () => showGuestForm(false));
guestForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (busy) return;
  const data = Object.fromEntries(new FormData(guestForm));
  for (const name of Object.keys(data)) data[name] = data[name].trim();
  if (!data.full_name || !data.identification_number) {
    message("dialog-error", "Escribe el nombre y el documento del huésped.");
    return;
  }
  data.phone ||= null;
  data.email ||= null;
  if (guestEditId !== undefined) {
    await mutate(() => request(`guests/${guestEditId}`, {method: "PATCH", data}), "Huésped actualizado.");
    return;
  }
  message("dialog-error", "");
  setBusy(true);
  try {
    const guest = await request("guests", {method: "POST", data});
    guests.set(guest.guest_id, guest);
    guestSearch.value = "";
    fillGuestOptions(guest.guest_id);
    showGuestForm(false);
    message("guest-notice", "Huésped registrado y seleccionado para esta reserva.");
  } catch (error) {
    message("dialog-error", errorMessage(error));
  } finally {
    setBusy(false);
  }
});

form.addEventListener("submit", (event) => {
  event.preventDefault();
  if (busy || roomField.disabled) return;
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
  void mutate(() => request(resource, {method, data}), editingId ? "Reserva actualizada." : "Reserva creada.", {savingStay: true});
});

deleteButton.addEventListener("click", () => {
  void mutate(() => request(`reservations/${editingId}`, {method: "DELETE"}), "Reserva eliminada.", {deleting: true});
});
cancelButton.addEventListener("click", () => {
  void mutate(() => request(`reservations/${editingId}`, {method: "PATCH", data: {status: "cancelled"}}), "Reserva cancelada. Se conservó el historial.");
});
for (const field of [arrival, departure, stayStatus]) {
  field.addEventListener("change", () => void refreshAvailability());
}
guestSearch.addEventListener("input", () => fillGuestOptions());
byId("retry-availability").addEventListener("click", () => void refreshAvailability());
closeButton.addEventListener("click", () => dialog.close());
dialog.addEventListener("cancel", (event) => { if (busy) event.preventDefault(); });
dialog.addEventListener("close", () => { if (!dialog.open) {
  dialogRequest?.abort();
  availabilityRequest?.abort();
} });
addButton.addEventListener("click", () => openReservation("create"));
search.addEventListener("input", renderList);
for (const date of [roomsCheckIn, roomsCheckOut]) {
  date.addEventListener("change", () => { if (section === "rooms") void loadSection(); });
}
byId("reload").addEventListener("click", () => { message("notice", ""); void loadSection(); });
for (const button of document.querySelectorAll("[data-section]")) {
  button.addEventListener("click", () => {
    document.querySelector("[aria-current]").removeAttribute("aria-current");
    button.setAttribute("aria-current", "page");
    section = button.dataset.section;
    search.value = "";
    message("notice", "");
    void loadSection();
    byId("operacion").scrollIntoView();
  });
}
void loadSection();
