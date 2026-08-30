const TERRAIN_ICON = { wald: "🌲", stadt: "🏠", mix: "🏡", unbekannt: "⋯" };

const SM_CODES = new Set(["LOM", "MOM", "SPM", "NOM", "SOM", "TOM", "SSM"]);
const TYPE_LABEL = {
  sm: "SM",
  nat: "Nat. OL",
  swisscup: "SwissCup",
  reg: "Reg. OL",
  mehrtaegig: "Mehrtägig",
  staffel: "Staffel",
  team: "Team-OL",
  adm: "Adm",
  sonstige: "Sonstige",
};

function categorize(code) {
  if (!code) return "sonstige";
  if (code === "Adm") return "adm";
  if (SM_CODES.has(code)) return "sm";
  if (code.startsWith("**")) return "nat";
  if (/^SC\d/.test(code)) return "swisscup";
  if (code.startsWith("*")) return "reg";
  if (/M$/.test(code)) return "mehrtaegig";
  if (/S$/.test(code)) return "staffel";
  if (/T$/.test(code)) return "team";
  return "sonstige";
}

function isJomEvent(ev) {
  return jomUids.has(ev.uid);
}

const HOME = { lat: 47.3546, lon: 8.4332 }; // Birmensdorf ZH

function haversineKm(lat1, lon1, lat2, lon2) {
  const R = 6371;
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLon = ((lon2 - lon1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos((lat1 * Math.PI) / 180) * Math.cos((lat2 * Math.PI) / 180) * Math.sin(dLon / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

function getNearbyRadius() {
  const val = parseFloat(nearbyRadiusInput.value);
  return val > 0 ? val : 50;
}

function isNearbyEvent(ev) {
  return ev.lat != null && ev.lon != null && haversineKm(HOME.lat, HOME.lon, ev.lat, ev.lon) <= getNearbyRadius();
}

let events = [];
let jomActive = false;
let nearbyActive = false;
let showPast = false;
let jomUids = new Set();

function todayIso() {
  const d = new Date();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${mm}-${dd}`;
}

async function loadJomConfig(year) {
  try {
    const res = await fetch(`/jom-${year}.json`, { cache: "no-store" });
    if (!res.ok) {
      jomUids = new Set();
      return;
    }
    const data = await res.json();
    jomUids = new Set((data.events || []).map((e) => e.uid));
  } catch {
    jomUids = new Set();
  }
}

const yearSelect = document.getElementById("year");
const reloadBtn = document.getElementById("reload");
const statusEl = document.getElementById("status");
const bodyEl = document.getElementById("events-body");
const searchEl = document.getElementById("search");
const mapFrame = document.getElementById("map-frame");
const mapTitle = document.getElementById("map-title");
const mapHint = document.getElementById("map-hint");
const terrainFilters = Array.from(document.querySelectorAll(".terrain-filter"));
const typeFilters = Array.from(document.querySelectorAll(".type-filter"));
const jomBtn = document.getElementById("jom-btn");
const nearbyBtn = document.getElementById("nearby-btn");
const nearbyRadiusInput = document.getElementById("nearby-radius");
const pastBtn = document.getElementById("past-btn");

function initYearSelect() {
  const current = new Date().getFullYear();
  for (let y = current - 1; y <= current + 2; y++) {
    const opt = document.createElement("option");
    opt.value = y;
    opt.textContent = y;
    if (y === current) opt.selected = true;
    yearSelect.appendChild(opt);
  }
}

function setStatus(text, isError) {
  statusEl.textContent = text;
  statusEl.classList.toggle("error", !!isError);
}

async function loadFixtures() {
  const year = yearSelect.value;
  reloadBtn.disabled = true;
  setStatus(`Lade Termine ${year} von o-l.ch ...`);
  try {
    const [res] = await Promise.all([
      fetch(`/api/fixtures?year=${encodeURIComponent(year)}`),
      loadJomConfig(year),
    ]);
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
    events = data.events;
    setStatus(`${data.count} Termine geladen (${new Date().toLocaleTimeString("de-CH")}).`);
    render();
  } catch (err) {
    setStatus(`Fehler: ${err.message}`, true);
  } finally {
    reloadBtn.disabled = false;
  }
}

function activeTerrains() {
  return new Set(terrainFilters.filter((cb) => cb.checked).map((cb) => cb.value));
}

function activeTypes() {
  return new Set(typeFilters.filter((cb) => cb.checked).map((cb) => cb.value));
}

function toggleJom() {
  if (!jomActive && jomUids.size === 0) {
    setStatus(`Keine JOM-Konfiguration für ${yearSelect.value} gefunden (jom-${yearSelect.value}.json fehlt).`, true);
    return;
  }
  jomActive = !jomActive;
  jomBtn.classList.toggle("active", jomActive);
  jomBtn.textContent = jomActive ? "JOM-Filter aktiv ✕" : "Nur JOM-Läufe";
  render();
}

function toggleNearby() {
  nearbyActive = !nearbyActive;
  nearbyBtn.classList.toggle("active", nearbyActive);
  nearbyBtn.textContent = nearbyActive ? "Nähe-Filter aktiv ✕" : "OL in der Nähe";
  render();
}

function togglePast() {
  showPast = !showPast;
  pastBtn.classList.toggle("active", showPast);
  pastBtn.textContent = showPast ? "Vergangene Termine ausblenden" : "Mit vergangenen Terminen";
  render();
}

function formatDate(iso) {
  const [y, m, d] = iso.split("-");
  return `${d}.${m}.${y}`;
}

function matchesSearch(ev, query) {
  if (!query) return true;
  const haystack = `${ev.name} ${ev.organizer} ${ev.location} ${ev.region}`.toLowerCase();
  return haystack.includes(query);
}

function render() {
  const terrains = activeTerrains();
  const types = activeTypes();
  const query = searchEl.value.trim().toLowerCase();
  const today = todayIso();
  const filtered = events.filter(
    (ev) =>
      terrains.has(ev.terrain) &&
      types.has(categorize(ev.code)) &&
      matchesSearch(ev, query) &&
      (!jomActive || isJomEvent(ev)) &&
      (!nearbyActive || isNearbyEvent(ev)) &&
      (showPast || ev.date >= today)
  );

  bodyEl.innerHTML = "";

  if (filtered.length === 0) {
    const tr = document.createElement("tr");
    const td = document.createElement("td");
    td.colSpan = 10;
    td.className = "empty";
    td.textContent = events.length === 0
      ? 'Noch keine Daten geladen. "Daten laden" klicken.'
      : "Keine Termine passen zu den aktuellen Filtern.";
    tr.appendChild(td);
    bodyEl.appendChild(tr);
    return;
  }

  for (const ev of filtered) {
    bodyEl.appendChild(buildRow(ev));
  }
}

function buildRow(ev) {
  const tr = document.createElement("tr");
  tr.dataset.uid = ev.uid;

  const weekdayDate = document.createElement("td");
  weekdayDate.textContent = `${ev.weekday} ${formatDate(ev.date)}`;
  tr.appendChild(weekdayDate);

  const region = document.createElement("td");
  region.textContent = ev.region;
  tr.appendChild(region);

  const name = document.createElement("td");
  name.className = "name-cell";
  const nameLink = document.createElement("a");
  nameLink.href = ev.detail_url;
  nameLink.target = "_blank";
  nameLink.rel = "noopener";
  nameLink.textContent = ev.name;
  name.appendChild(nameLink);
  tr.appendChild(name);

  const organizer = document.createElement("td");
  organizer.className = "organizer-cell";
  organizer.textContent = ev.organizer;
  tr.appendChild(organizer);

  const location = document.createElement("td");
  location.className = "location-cell";
  location.textContent = ev.location;
  tr.appendChild(location);

  const dist = document.createElement("td");
  dist.textContent = ev.distance;
  tr.appendChild(dist);

  const terrain = document.createElement("td");
  terrain.textContent = TERRAIN_ICON[ev.terrain] || "";
  terrain.title = ev.terrain;
  tr.appendChild(terrain);

  const type = document.createElement("td");
  const typeKey = categorize(ev.code);
  type.textContent = TYPE_LABEL[typeKey] === "Sonstige" ? "" : TYPE_LABEL[typeKey];
  type.title = ev.code;
  tr.appendChild(type);

  const mapCell = document.createElement("td");
  if (ev.lat != null && ev.lon != null) {
    const mapBtn = document.createElement("button");
    mapBtn.className = "small";
    mapBtn.textContent = "Karte";
    mapBtn.addEventListener("click", () => showOnMap(ev, tr));
    mapCell.appendChild(mapBtn);
  } else if (ev.location) {
    const mapBtn = document.createElement("button");
    mapBtn.className = "small";
    mapBtn.textContent = "Karte (Ort)";
    mapBtn.addEventListener("click", () => showOnMapByName(ev, tr));
    mapCell.appendChild(mapBtn);
  }
  tr.appendChild(mapCell);

  const icsCell = document.createElement("td");
  const icsBtn = document.createElement("button");
  icsBtn.className = "small";
  icsBtn.textContent = "ICS";
  icsBtn.addEventListener("click", () => downloadIcs(ev));
  icsCell.appendChild(icsBtn);
  tr.appendChild(icsCell);

  return tr;
}

function showOnMap(ev, row) {
  document.querySelectorAll("#events-body tr.highlight").forEach((r) => r.classList.remove("highlight"));
  row.classList.add("highlight");
  const label = encodeURIComponent(`${ev.name} (${ev.location})`);
  mapFrame.src = `https://www.google.com/maps?q=${ev.lat},${ev.lon}(${label})&z=14&output=embed`;
  mapTitle.textContent = `Karte: ${ev.name}`;
  mapHint.textContent = `${ev.location}, ${ev.region} — Koordinaten aus o-l.ch, Position kann leicht abweichen.`;
}

function showOnMapByName(ev, row) {
  document.querySelectorAll("#events-body tr.highlight").forEach((r) => r.classList.remove("highlight"));
  row.classList.add("highlight");
  mapFrame.src = `https://www.google.com/maps?q=${encodeURIComponent(ev.location)}&z=13&output=embed`;
  mapTitle.textContent = `Karte: ${ev.name}`;
  mapHint.textContent = `Suche nach "${ev.location}" — o-l.ch liefert für diesen Termin keine genauen Koordinaten.`;
}

function icsEscape(text) {
  return String(text || "")
    .replace(/\\/g, "\\\\")
    .replace(/,/g, "\\,")
    .replace(/;/g, "\\;")
    .replace(/\n/g, "\\n");
}

function isoDateToIcsDateTime(iso, time) {
  return `${iso.replace(/-/g, "")}T${time}00`;
}

function buildIcs(ev) {
  const now = new Date().toISOString().replace(/[-:]/g, "").split(".")[0] + "Z";
  const start = isoDateToIcsDateTime(ev.date, "0900");
  const end = isoDateToIcsDateTime(ev.date, "1400");
  const description = `Veranstalter: ${ev.organizer}${ev.distance ? " | Distanz: " + ev.distance : ""} | Details: ${ev.detail_url} | Zeit 9-14 Uhr ist ein Platzhalter, o-l.ch liefert keine genaue Startzeit.`;
  return [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//ol-termine-viewer//DE",
    "CALSCALE:GREGORIAN",
    "BEGIN:VEVENT",
    `UID:ol-${ev.uid}@o-l.ch`,
    `DTSTAMP:${now}`,
    `DTSTART;TZID=Europe/Zurich:${start}`,
    `DTEND;TZID=Europe/Zurich:${end}`,
    `SUMMARY:${icsEscape(ev.name)}`,
    `LOCATION:${icsEscape(ev.location + ", " + ev.region)}`,
    `DESCRIPTION:${icsEscape(description)}`,
    `URL:${ev.detail_url}`,
    "END:VEVENT",
    "END:VCALENDAR",
    "",
  ].join("\r\n");
}

function downloadIcs(ev) {
  const blob = new Blob([buildIcs(ev)], { type: "text/calendar;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  const slug = ev.name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
  a.download = `ol-${ev.date}-${slug || ev.uid}.ics`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

initYearSelect();
reloadBtn.addEventListener("click", loadFixtures);
searchEl.addEventListener("input", render);
terrainFilters.forEach((cb) => cb.addEventListener("change", render));
typeFilters.forEach((cb) => cb.addEventListener("change", render));
jomBtn.addEventListener("click", toggleJom);
nearbyBtn.addEventListener("click", toggleNearby);
pastBtn.addEventListener("click", togglePast);
nearbyRadiusInput.addEventListener("input", () => {
  if (nearbyActive) render();
});
