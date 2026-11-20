"use strict";

const byId = (id) => document.getElementById(id);
const locale = "en-US";
const institutions = new Map();
let papers = [];
let map;
let markerLayer;
let selected = "";
let query = "";

async function readJson(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Could not read ${url}`);
  return response.json();
}

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function safeLink(label, target, className) {
  const node = element("a", className, label);
  try {
    const url = new URL(target);
    if (["https:", "http:"].includes(url.protocol)) node.href = url.href;
  } catch { /* A missing or invalid source remains readable text. */ }
  return node;
}

function displayDate(value, precision) {
  const parts = String(value || "").slice(0, 10).split("-");
  if (!parts[0]) return "Date unavailable";
  if (parts.length === 1 || precision === "year") return parts[0];
  const day = parts.length > 2 && precision !== "month";
  const date = new Date(Date.UTC(Number(parts[0]), Number(parts[1]) - 1, day ? Number(parts[2]) : 1));
  if (!Number.isFinite(date.getTime())) return String(value);
  return date.toLocaleDateString("en-GB", {day: day ? "numeric" : undefined, month: "short", year: "numeric", timeZone: "UTC"});
}

function addPaperRow(paper) {
  const article = element("article", "paper-row");
  const date = element("time", "", displayDate(paper.date, paper.datePrecision));
  date.dateTime = paper.date;
  const body = element("div");
  const title = element("h3", "paper-title");
  title.append(safeLink(paper.title, paper.url));
  const names = paper.institutions.map(id => institutions.get(id)?.name).filter(Boolean);
  const metadata = [paper.type, paper.venue, ...names].filter(Boolean).join(" · ");
  body.append(title, element("p", "paper-meta", metadata), element("p", "paper-usage", paper.usage));
  const evidence = element("details", "evidence");
  const summary = element("summary", "", "Evidence");
  summary.setAttribute("aria-label", `Show usage evidence for ${paper.title}`);
  const detail = element("div", "evidence-detail");
  const source = safeLink("Read source ↗", paper.evidence.url, "text-link");
  source.setAttribute("aria-label", `Read ${paper.evidence.locator} for ${paper.title}`);
  if (paper.evidence.quote) detail.append(element("q", "", paper.evidence.quote));
  detail.append(element("p", "", paper.evidence.locator), source);
  evidence.append(summary, detail);
  article.append(date, body, evidence);
  return article;
}

function searchText(paper) {
  const names = paper.institutions.map(id => {
    const inst = institutions.get(id);
    return inst ? [inst.name, inst.city, inst.country].join(" ") : "";
  });
  const authors = Array.isArray(paper.authors) ? paper.authors.join(" ") : paper.authors;
  return [paper.title, authors, paper.venue, paper.date, paper.usage, ...names].join(" ").toLocaleLowerCase(locale);
}

function refresh() {
  const matched = papers.filter(p => p.search.includes(query));
  const visible = matched.filter(p => !selected || p.institutions.includes(selected));
  const list = byId("papers");
  if (visible.length) {
    list.replaceChildren(...visible.map(addPaperRow));
  } else {
    list.replaceChildren(element("p", "empty", "No matching papers. Try another search or institution."));
  }
  list.setAttribute("aria-busy", "false");
  byId("visible-count").textContent = visible.length;
  const filterActive = Boolean(query || selected);
  byId("clear-filters").hidden = !filterActive;
  byId("selection-note").textContent = filterActive
    ? `${visible.length} of ${papers.length} papers${selected ? " · " + institutions.get(selected).name : ""}`
    : "";
  const matchingInstitutions = new Set(matched.flatMap(p => p.institutions));
  renderMarkers([...institutions.values()].filter(inst => matchingInstitutions.has(inst.id)));
}

function chooseInstitution(id) {
  selected = id;
  byId("affiliation").value = id;
  refresh();
}

const worldBounds = [[-56, -173], [78, 180]];
function fitWorld() {
  if (!map) return;
  const padding = map.getSize().x > 650 ? [15, 10] : [6, 8];
  map.fitBounds(worldBounds, {padding, animate: false});
}

function initMap(world) {
  if (!window.L) {
    byId("map").append(element("p", "map-fallback", "The map could not load. Use the institution filter below to explore the same papers."));
    return;
  }
  map = L.map("map", {
    crs: L.CRS.EPSG4326, minZoom: -1, maxZoom: 8, zoomSnap: 0.05, zoomDelta: 1,
    zoomControl: false, attributionControl: false, scrollWheelZoom: false,
    maxBounds: [[-89, -220], [89, 220]], maxBoundsViscosity: .75
  });
  fitWorld();
  const grid = {color: "#aabbb1", weight: .6, opacity: .63, interactive: false};
  for (let lon = -180; lon <= 180; lon += 30) L.polyline([[-89, lon], [89, lon]], grid).addTo(map);
  for (let lat = -75; lat <= 75; lat += 15) L.polyline([[lat, -180], [lat, 180]], grid).addTo(map);
  if (world) {
    L.geoJSON(world, {style: {weight: .7, color: "#b7c0b4", fillColor: "#f7f7ed", fillOpacity: 1}, interactive: false}).addTo(map);
  }
  const oceans = [
    [28, -138, "Pacific Ocean"], [29, -41, "Atlantic Ocean"],
    [-24, 77, "Indian Ocean"], [-27, -132, "South Pacific"]
  ];
  for (const [lat, lon, text] of oceans) {
    const icon = L.divIcon({className: "", html: element("span", "water-label", text), iconSize: [0, 0]});
    L.marker([lat, lon], {icon, interactive: false, keyboard: false, zIndexOffset: -5000}).addTo(map);
  }
  markerLayer = L.layerGroup().addTo(map);
  byId("map-controls").hidden = false;
  byId("zoom-in").addEventListener("click", () => map.zoomIn());
  byId("zoom-out").addEventListener("click", () => map.zoomOut());
  byId("fit-world").addEventListener("click", fitWorld);
  map.on("zoomend", () => {
    byId("zoom-in").disabled = map.getZoom() >= map.getMaxZoom();
    byId("zoom-out").disabled = map.getZoom() <= map.getMinZoom();
    refreshMarkersForQuery();
  });
  if ("ResizeObserver" in window) {
    let width = byId("map").clientWidth;
    new ResizeObserver(() => {
      const newWidth = byId("map").clientWidth;
      if (width === newWidth) return;
      width = newWidth;
      map.invalidateSize();
      fitWorld();
    }).observe(byId("map"));
  }
}

function refreshMarkersForQuery() {
  const ids = new Set(papers.filter(p => p.search.includes(query)).flatMap(p => p.institutions));
  renderMarkers([...institutions.values()].filter(inst => ids.has(inst.id)));
}

function groupLocations(locations) {
  const groups = [];
  for (const inst of locations) {
    if (!Number.isFinite(inst.lat) || !Number.isFinite(inst.lon)) continue;
    const point = map.project([inst.lat, inst.lon]);
    const group = groups.find(g => g.center.distanceTo(point) < 24);
    if (!group) {
      groups.push({center: point, members: [inst]});
      continue;
    }
    const count = group.members.length;
    group.center = group.center.multiplyBy(count).add(point).divideBy(count + 1);
    group.members.push(inst);
  }
  return groups;
}

function showGroup(group, position) {
  const members = group.members;
  const popup = element("div", "popup-body");
  if (members.length === 1) {
    const inst = members[0];
    chooseInstitution(inst.id);
    popup.append(element("strong", "popup-title", inst.name));
    popup.append(element("span", "", [inst.city, inst.country].filter(Boolean).join(", ")));
    const number = papers.filter(p => p.search.includes(query) && p.institutions.includes(inst.id)).length;
    const link = element("a", "", `View ${number} ${number === 1 ? "paper" : "papers"} ↓`);
    link.href = "#publications";
    popup.append(link);
  } else {
    popup.append(element("strong", "popup-title", `${members.length} institutions`));
    for (const inst of members) {
      const button = element("button", "", inst.name);
      button.type = "button";
      button.addEventListener("click", () => showGroup({members: [inst]}, [inst.lat, inst.lon]));
      popup.append(button);
    }
    if (map.getZoom() < map.getMaxZoom()) {
      const zoom = element("button", "", "Zoom to group +");
      zoom.type = "button";
      zoom.addEventListener("click", () => {
        map.closePopup();
        const bounds = L.latLngBounds(members.map(inst => [inst.lat, inst.lon]));
        map.fitBounds(bounds, {padding: [35, 35], maxZoom: map.getZoom() + 3});
      });
      popup.append(zoom);
    }
  }
  L.popup({offset: [0, -8], maxWidth: 270}).setLatLng(position).setContent(popup).openOn(map);
}

function renderMarkers(locations) {
  if (!markerLayer) return;
  markerLayer.clearLayers();
  for (const group of groupLocations(locations)) {
    const count = group.members.length;
    const active = group.members.some(inst => inst.id === selected);
    const size = count > 1 ? 25 : 24;
    const name = count > 1 ? `${count} institutions` : group.members[0].name;
    const icon = L.divIcon({
      className: ["map-point", count > 1 ? "is-cluster" : "", active ? "is-selected" : ""].join(" "),
      html: count > 1 ? element("b", "", count) : "", iconSize: [size, size], iconAnchor: [size / 2, size / 2]
    });
    const position = map.unproject(group.center);
    const marker = L.marker(position, {icon, title: name, alt: name, keyboard: true, riseOnHover: true})
      .bindTooltip(element("span", "", name), {direction: "top", offset: [0, -7]})
      .on("click", () => showGroup(group, position)).addTo(markerLayer);
    marker.getElement()?.setAttribute("aria-label", name);
  }
}

function updateFooter(reviewedThrough, status) {
  const dates = [];
  if (reviewedThrough) dates.push(`Data reviewed ${displayDate(reviewedThrough)}`);
  if (status?.lastSuccessfulSearch) dates.push(`Last search ${displayDate(status.lastSuccessfulSearch)}`);
  if (status?.lastAttempt && ["partial", "failed", "failure"].includes(status.outcome)) {
    dates.push(`Search ${displayDate(status.lastAttempt)} · ${status.outcome === "partial" ? "partial source coverage" : "sources unavailable"}`);
  }
  byId("freshness").textContent = dates.join(" · ");
}

async function start() {
  const [data, world, status] = await Promise.all([
    readJson("data/papers.json"), readJson("assets/world.json").catch(() => null),
    readJson("data/status.json").catch(() => null)
  ]);
  const usedIds = new Set(data.papers.flatMap(p => p.institutions));
  for (const inst of data.institutions) {
    if (usedIds.has(inst.id)) institutions.set(inst.id, inst);
  }
  papers = data.papers.map(p => ({...p, search: searchText(p)})).sort((a, b) =>
    b.date.localeCompare(a.date) || a.title.localeCompare(b.title, locale));
  for (const inst of [...institutions.values()].sort((a, b) => a.name.localeCompare(b.name, locale))) {
    byId("affiliation").add(new Option(inst.name, inst.id));
  }
  byId("paper-count").textContent = papers.length;
  byId("institution-count").textContent = institutions.size;
  byId("country-count").textContent = new Set([...institutions.values()].map(inst => inst.country).filter(Boolean)).size;
  byId("search").addEventListener("input", event => {
    query = event.target.value.trim().toLocaleLowerCase(locale);
    map?.closePopup();
    refresh();
  });
  byId("affiliation").addEventListener("change", event => {
    map?.closePopup();
    chooseInstitution(event.target.value);
    const inst = institutions.get(selected);
    if (inst && map && Number.isFinite(inst.lat) && Number.isFinite(inst.lon)) {
      map.setView([inst.lat, inst.lon], Math.max(map.getZoom(), 4));
    } else if (map) fitWorld();
  });
  byId("clear-filters").addEventListener("click", () => {
    query = byId("search").value = "";
    map?.closePopup();
    chooseInstitution("");
    if (map) fitWorld();
  });
  refresh();
  updateFooter(data.reviewedThrough, status);
  initMap(world);
  refreshMarkersForQuery();
}

start().catch(() => {
  byId("papers").setAttribute("aria-busy", "false");
  byId("selection-note").textContent = "The index could not load. Please refresh or view the source data.";
  byId("papers").append(safeLink("View source data ↗", "https://github.com/zilinzhuang/andes-usage/tree/main/data", "text-link"));
});
