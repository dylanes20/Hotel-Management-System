"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const {test} = require("node:test");
const vm = require("node:vm");

test("las fichas usan el estado de disponibilidad y el nombre del tipo enviados por la API", () => {
  function element() {
    return {
      children: [],
      append(...children) { this.children.push(...children); },
      addEventListener() {},
    };
  }

  const controls = new Map();
  const document = {
    body: {dataset: {api: "/api/reservations", room: "/room.webp", junior: "/junior.webp"}},
    createElement: element,
    querySelectorAll: () => [],
    getElementById(id) {
      if (!controls.has(id)) controls.set(id, element());
      return controls.get(id);
    },
  };
  document.getElementById("reservation-form").elements = {namedItem: element};
  const context = vm.createContext({document});
  const source = fs.readFileSync(new URL("../static/hotel.js", `file://${__filename}`), "utf8");
  // No hay navegador ni red. Se ejecutan las funciones de renderizado reales.
  vm.runInContext(source.replace(/void loadSection\(\);\s*$/, ""), context);
  vm.runInContext('section = "rooms";', context);

  for (const [status, label] of Object.entries({
    operational: "Operativa", available: "Disponible", reserved: "Reservada",
    maintenance: "En mantenimiento", out_of_service: "Fuera de servicio",
  })) {
    context.room = {
      room_id: 1, room_number: "101", floor: 1, room_type_id: 25,
      room_type_name: "Suite Junior", capacity: 2, base_nightly_rate: "110.00",
      status: "available", display_status: status,
    };
    const card = vm.runInContext("recordCard(room, recordContent(room))", context);
    const [photo, body] = card.children;
    const [header, details] = body.children;
    assert.equal(photo.src, "/junior.webp");
    assert.equal(header.children[1].textContent, label);
    assert.equal(details.children[1].children[1].textContent, "Suite Junior");
    assert.equal(details.children[2].children[1].textContent, 2);
    assert.match(details.children[3].children[1].textContent, /110/);
  }
});
