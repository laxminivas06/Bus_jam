/**
 * CampusFleet - Sphoorthy Campus Lead Live Bus Tracking System
 * Frontend Application JavaScript (Multi-ESP Management, 7-Day Route History & Live GPS Replay)
 */

document.addEventListener("DOMContentLoaded", () => {
    // ==========================================
    // 1. STATE MANAGEMENT
    // ==========================================
    const state = {
        buses: [],
        selectedBusId: null,
        busMarkers: {},        // Map of { bus_id: L.marker }
        routePolyline: null,   // Live route L.polyline
        activeFilter: "all",   // "all" | "connected" | "offline"
        searchQuery: "",
        autoRefreshInterval: 5, // 5 seconds
        countdownRemaining: 5,
        timerId: null,
        mobileActiveTab: "buses", // "buses" | "map"

        // 7-Day History & Replay State
        viewMode: "live",      // "live" | "history"
        selectedDate: null,    // Format: "DD-MM-YYYY"
        availableDates: [],
        historyRecords: [],
        historyLayers: [],     // Leaflet layer objects for history display
        historyPolyline: null,

        replay: {
            index: 0,
            isPlaying: false,
            speedMultiplier: 1,
            timer: null,
            marker: null
        },

        // ESP Hardware Devices
        devices: []
    };

    // ==========================================
    // 2. DOM ELEMENTS CACHE
    // ==========================================
    const elements = {
        map: null,
        // Header
        headerActiveBusCount: document.getElementById("headerActiveBusCount"),
        syncStatusLabel: document.getElementById("syncStatusLabel"),
        openRegisterModalBtn: document.getElementById("openRegisterModalBtn"),
        openDevicesModalBtn: document.getElementById("openDevicesModalBtn"),
        devicesHeaderBadge: document.getElementById("devicesHeaderBadge"),

        // Bus Selector Panel
        busSelectorPanel: document.getElementById("busSelectorPanel"),
        liveMapPanel: document.getElementById("liveMapPanel"),
        busSearchInput: document.getElementById("busSearchInput"),
        clearSearchBtn: document.getElementById("clearSearchBtn"),
        statusTabBtns: document.querySelectorAll(".status-tab-btn"),
        busesListContainer: document.getElementById("busesListContainer"),
        countAllBuses: document.getElementById("countAllBuses"),
        countConnectedBuses: document.getElementById("countConnectedBuses"),
        countOfflineBuses: document.getElementById("countOfflineBuses"),
        footerTotalCount: document.getElementById("footerTotalCount"),
        mobileBusCount: document.getElementById("mobileBusCount"),

        // Mobile Tabs
        mobileTabBusesBtn: document.getElementById("mobileTabBusesBtn"),
        mobileTabMapBtn: document.getElementById("mobileTabMapBtn"),

        // Floating Telemetry HUD
        hudBusName: document.getElementById("hudBusName"),
        hudBusNumber: document.getElementById("hudBusNumber"),
        hudEspVal: document.getElementById("hudEspVal"),
        hudConnectionBadge: document.getElementById("hudConnectionBadge"),
        btnModeLive: document.getElementById("btnModeLive"),
        btnModeHistory: document.getElementById("btnModeHistory"),

        // View Sections in HUD
        liveTelemetrySection: document.getElementById("liveTelemetrySection"),
        historyTelemetrySection: document.getElementById("historyTelemetrySection"),

        // Live Telemetry Fields
        hudCoordsVal: document.getElementById("hudCoordsVal"),
        hudCopyCoordsBtn: document.getElementById("hudCopyCoordsBtn"),
        hudGoogleMapsLink: document.getElementById("hudGoogleMapsLink"),
        hudSpeedVal: document.getElementById("hudSpeedVal"),
        hudHeadingVal: document.getElementById("hudHeadingVal"),
        hudSatsVal: document.getElementById("hudSatsVal"),
        hudUpdatedVal: document.getElementById("hudUpdatedVal"),
        hudRouteVal: document.getElementById("hudRouteVal"),

        // 7-Day History UI Elements
        sevenDayNavPills: document.getElementById("sevenDayNavPills"),
        histDistVal: document.getElementById("histDistVal"),
        histMaxSpeedVal: document.getElementById("histMaxSpeedVal"),
        histStopsVal: document.getElementById("histStopsVal"),
        histPointsVal: document.getElementById("histPointsVal"),

        // Journey Replay Controls
        routeReplayControls: document.getElementById("routeReplayControls"),
        replayPlayPauseBtn: document.getElementById("replayPlayPauseBtn"),
        replayResetBtn: document.getElementById("replayResetBtn"),
        replayScrubber: document.getElementById("replayScrubber"),
        replayCurrentTime: document.getElementById("replayCurrentTime"),
        replayCurrentSpeed: document.getElementById("replayCurrentSpeed"),
        replayWaypointProgress: document.getElementById("replayWaypointProgress"),
        speedOptBtns: document.querySelectorAll(".speed-opt-btn"),

        // Map Controls
        centerSelectedBusBtn: document.getElementById("centerSelectedBusBtn"),
        fitAllBusesBtn: document.getElementById("fitAllBusesBtn"),

        // Modals
        registerBusModal: document.getElementById("registerBusModal"),
        closeRegisterModalBtn: document.getElementById("closeRegisterModalBtn"),
        simpleAddBusForm: document.getElementById("simpleAddBusForm"),

        devicesModal: document.getElementById("devicesModal"),
        closeDevicesModalBtn: document.getElementById("closeDevicesModalBtn"),
        devicesTableBody: document.getElementById("devicesTableBody"),
        unassignedAlertBanner: document.getElementById("unassignedAlertBanner"),
        addDeviceForm: document.getElementById("addDeviceForm"),
        devNameInput: document.getElementById("devNameInput"),
        devIdInput: document.getElementById("devIdInput"),
        devMacInput: document.getElementById("devMacInput"),
        devTypeInput: document.getElementById("devTypeInput"),
        devBusSelect: document.getElementById("devBusSelect"),
        devMetricTotal: document.getElementById("devMetricTotal"),
        devMetricOnline: document.getElementById("devMetricOnline"),
        devMetricGps: document.getElementById("devMetricGps"),
        devMetricUnassigned: document.getElementById("devMetricUnassigned"),

        // Toast Container
        toastContainer: document.getElementById("toastContainer")
    };

    // ==========================================
    // 3. MAP INITIALIZATION
    // ==========================================
    function initMap() {
        const defaultCenter = [17.385044, 78.486671]; // Hyderabad Coordinates

        elements.map = L.map("map", {
            center: defaultCenter,
            zoom: 13,
            zoomControl: false
        });

        L.control.zoom({ position: "bottomright" }).addTo(elements.map);

        // Standard clean OpenStreetMap light tiles
        L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
            maxZoom: 19,
            attribution: '&copy; OpenStreetMap contributors'
        }).addTo(elements.map);
    }

    // Live Bus Marker Generator with directional heading arrow
    function createBusMarkerIcon(bus, isSelected = false) {
        const isOnline = bus.is_online;
        const isMoving = bus.is_moving;

        let statusClass = "offline";
        if (isOnline) {
            statusClass = isMoving ? "online" : "stopped";
        }

        const selectedClass = isSelected ? "selected" : "";
        const heading = bus.current_location ? (bus.current_location.heading || 0) : 0;

        const html = `
            <div class="bus-marker-container">
                <div class="bus-marker-pin ${statusClass} ${selectedClass}" style="transform: rotate(${heading}deg);" title="${bus.bus_name} (${bus.bus_number})">
                    <i class="fa-solid fa-arrow-up"></i>
                </div>
            </div>
        `;

        return L.divIcon({
            html: html,
            className: "custom-bus-marker-wrapper",
            iconSize: [36, 36],
            iconAnchor: [18, 18],
            popupAnchor: [0, -18]
        });
    }

    // Historical Start & End Marker Generator
    function createHistoryPinIcon(type, label = "") {
        const isStart = (type === "start");
        const pinClass = isStart ? "start" : "end";
        const icon = isStart ? "fa-play" : "fa-flag-checkered";

        const html = `
            <div class="history-pin ${pinClass}" title="${label}">
                <i class="fa-solid ${icon}"></i>
            </div>
        `;

        return L.divIcon({
            html: html,
            className: "history-pin-wrapper",
            iconSize: [28, 28],
            iconAnchor: [14, 14],
            popupAnchor: [0, -14]
        });
    }

    // Replay Animated Bus Marker
    function createReplayMarkerIcon(heading = 0) {
        const html = `
            <div class="history-pin replay-live" style="transform: rotate(${heading}deg);" title="Journey Playback Position">
                <i class="fa-solid fa-bus"></i>
            </div>
        `;
        return L.divIcon({
            html: html,
            className: "replay-pin-wrapper",
            iconSize: [30, 30],
            iconAnchor: [15, 15],
            popupAnchor: [0, -15]
        });
    }

    // ==========================================
    // 4. DATA FETCHING (AUTOMATIC GPS SYNC)
    // ==========================================
    async function fetchBuses() {
        try {
            const res = await fetch("/api/buses?campus=Sphoorthy Campus Lead");
            if (!res.ok) throw new Error("Failed to load campus fleet");

            const data = await res.json();
            state.buses = data.buses || [];

            updateCounts();
            renderBusesList();
            updateMapMarkers();

            // If a bus is selected, update its HUD telemetry and ensure its route is shown
            if (state.selectedBusId) {
                const current = state.buses.find(b => b.bus_id === state.selectedBusId);
                if (current) {
                    updateTelemetryHUD(current);
                }
            } else if (state.buses.length > 0) {
                // Auto-select first active bus on initial load
                const firstOnline = state.buses.find(b => b.is_online) || state.buses[0];
                selectBus(firstOnline.bus_id, false);
            }
        } catch (err) {
            console.error("Error fetching Sphoorthy Campus buses:", err);
        }
    }

    function updateCounts() {
        const total = state.buses.length;
        const connected = state.buses.filter(b => b.is_online).length;
        const offline = total - connected;

        if (elements.headerActiveBusCount) elements.headerActiveBusCount.textContent = connected;
        if (elements.countAllBuses) elements.countAllBuses.textContent = total;
        if (elements.countConnectedBuses) elements.countConnectedBuses.textContent = connected;
        if (elements.countOfflineBuses) elements.countOfflineBuses.textContent = offline;
        if (elements.footerTotalCount) elements.footerTotalCount.textContent = total;
        if (elements.mobileBusCount) elements.mobileBusCount.textContent = total;
    }

    // ==========================================
    // 5. BUS SELECTION & LIST RENDERING
    // ==========================================
    function renderBusesList() {
        const query = state.searchQuery.toLowerCase();
        let filtered = state.buses;

        // Apply status filter
        if (state.activeFilter === "connected") {
            filtered = filtered.filter(b => b.is_online);
        } else if (state.activeFilter === "offline") {
            filtered = filtered.filter(b => !b.is_online);
        }

        // Apply search query
        if (query) {
            filtered = filtered.filter(b =>
                (b.bus_name || "").toLowerCase().includes(query) ||
                (b.bus_number || "").toLowerCase().includes(query) ||
                (b.bus_id || "").toLowerCase().includes(query) ||
                (b.device_id || "").toLowerCase().includes(query) ||
                (b.route_name || "").toLowerCase().includes(query)
            );
        }

        elements.busesListContainer.innerHTML = "";

        if (filtered.length === 0) {
            elements.busesListContainer.innerHTML = `
                <div style="text-align:center;padding:24px 12px;color:var(--text-muted);font-size:13px;">
                    <i class="fa-solid fa-bus" style="font-size:24px;margin-bottom:8px;color:var(--text-dim);"></i>
                    <p>No buses found matching criteria.</p>
                </div>
            `;
            return;
        }

        filtered.forEach(bus => {
            const isSelected = (bus.bus_id === state.selectedBusId);
            const isOnline = bus.is_online;
            const statusClass = bus.connection_status || (isOnline ? "connected" : "offline");
            const statusLabel = bus.connection_label || (isOnline ? "Connected" : "Offline");

            const sats = bus.current_location ? (bus.current_location.satellites || 8) : 0;
            const hasGps = isOnline && !bus.has_gps_issue && sats > 3;
            const gpsLabel = hasGps ? `GPS Active (${sats} Sats)` : (isOnline ? "Searching GPS Fix" : "Offline");
            const speed = bus.current_location ? `${Math.round(bus.current_location.speed)} km/h` : "Stopped";

            const card = document.createElement("div");
            card.className = `bus-item-card ${isSelected ? 'active' : ''}`;
            card.dataset.busId = bus.bus_id;

            card.innerHTML = `
                <div class="bus-card-head">
                    <div class="bus-name-block">
                        <span class="bus-name-title">${bus.bus_name || bus.bus_id}</span>
                        <div style="display:flex;align-items:center;gap:6px;margin-top:2px;">
                            <span class="bus-number-badge">${bus.bus_number}</span>
                            <span class="hud-esp-tag" style="font-size:9px;" title="Assigned Tracker"><i class="fa-solid fa-microchip"></i> ${bus.device_id || 'None'}</span>
                        </div>
                    </div>
                    <span class="card-status-badge ${statusClass}">${statusLabel}</span>
                </div>

                <div class="bus-card-middle">
                    <i class="fa-solid fa-route" style="color:var(--primary);font-size:11px;"></i>
                    <span>${bus.route_name || 'Assigned Campus Route'}</span>
                </div>

                <div class="bus-card-meta">
                    <span class="gps-avail-tag ${hasGps ? 'available' : 'unavailable'}">
                        <i class="fa-solid ${hasGps ? 'fa-satellite' : 'fa-satellite-dish'}"></i>
                        <span>${gpsLabel}</span>
                    </span>
                    <span class="bus-speed-tag"><i class="fa-solid fa-gauge-high"></i> ${speed}</span>
                </div>
            `;

            card.addEventListener("click", () => {
                selectBus(bus.bus_id, true);
            });

            elements.busesListContainer.appendChild(card);
        });
    }

    function selectBus(busId, userInitiated = true) {
        state.selectedBusId = busId;
        const bus = state.buses.find(b => b.bus_id === busId);
        if (!bus) return;

        // Highlight card in list
        document.querySelectorAll(".bus-item-card").forEach(c => {
            c.classList.toggle("active", c.dataset.busId === busId);
        });

        // Update Live Telemetry HUD
        updateTelemetryHUD(bus);

        // If currently in History Mode, reload date pills and route history for newly selected bus!
        if (state.viewMode === "history") {
            render7DayPills();
            loadHistoryForDate(bus.bus_id, state.selectedDate);
        } else {
            // Live view: Update Map Markers and Pan/Zoom
            updateMapMarkers();

            if (bus.current_location) {
                elements.map.flyTo([bus.current_location.latitude, bus.current_location.longitude], 15, {
                    duration: 1.0
                });
                if (state.busMarkers[busId]) {
                    state.busMarkers[busId].openPopup();
                }
            }
            loadAndDisplayRoutePath(bus);
        }

        // On mobile: switch to Map view automatically if clicked by user
        if (userInitiated && window.innerWidth <= 900) {
            switchMobileTab("map");
        }
    }

    function updateTelemetryHUD(bus) {
        elements.hudBusName.textContent = bus.bus_name || bus.bus_id;
        elements.hudBusNumber.textContent = bus.bus_number || bus.bus_id;
        elements.hudEspVal.textContent = bus.device_id || "Unassigned";

        const isOnline = bus.is_online;
        const statusClass = bus.connection_status || (isOnline ? "connected" : "offline");
        const statusLabel = bus.connection_label || (isOnline ? "Connected" : "Offline");

        elements.hudConnectionBadge.className = `card-status-badge ${statusClass}`;
        elements.hudConnectionBadge.textContent = statusLabel;

        if (bus.current_location) {
            const lat = Number(bus.current_location.latitude).toFixed(6);
            const lng = Number(bus.current_location.longitude).toFixed(6);
            elements.hudCoordsVal.textContent = `${lat}, ${lng}`;
            elements.hudSpeedVal.textContent = `${Math.round(bus.current_location.speed)} km/h`;
            elements.hudHeadingVal.textContent = `${Math.round(bus.current_location.heading)}° (${bus.current_location.cardinal_direction || 'N'})`;
            elements.hudSatsVal.textContent = `${bus.current_location.satellites || 8} Sats`;
            elements.hudUpdatedVal.textContent = formatTimeAgo(bus.current_location.updated_at);
            elements.hudGoogleMapsLink.href = `https://www.google.com/maps?q=${lat},${lng}`;
        } else {
            elements.hudCoordsVal.textContent = "Waiting for GPS fix...";
            elements.hudSpeedVal.textContent = "0 km/h";
            elements.hudHeadingVal.textContent = "0° (N)";
            elements.hudSatsVal.textContent = "0 Sats";
            elements.hudUpdatedVal.textContent = "Never";
            elements.hudGoogleMapsLink.href = "#";
        }

        elements.hudRouteVal.textContent = bus.route_name || "Campus Transit Route";
    }

    function updateMapMarkers() {
        if (state.viewMode === "history") return; // Keep map clean during history replay

        const currentIds = new Set();

        state.buses.forEach(bus => {
            if (!bus.current_location) return;

            const bId = bus.bus_id;
            const lat = bus.current_location.latitude;
            const lng = bus.current_location.longitude;
            const isSelected = (bId === state.selectedBusId);

            currentIds.add(bId);

            if (state.busMarkers[bId]) {
                const marker = state.busMarkers[bId];
                marker.setLatLng([lat, lng]);
                marker.setIcon(createBusMarkerIcon(bus, isSelected));
                marker.getPopup().setContent(`<strong>${bus.bus_name}</strong><br>${bus.bus_number}<br>Speed: ${Math.round(bus.current_location.speed)} km/h`);
            } else {
                const marker = L.marker([lat, lng], {
                    icon: createBusMarkerIcon(bus, isSelected)
                });
                marker.bindPopup(`<strong>${bus.bus_name}</strong><br>${bus.bus_number}<br>Speed: ${Math.round(bus.current_location.speed)} km/h`);
                marker.on("click", () => selectBus(bId, true));
                marker.addTo(elements.map);
                state.busMarkers[bId] = marker;
            }
        });

        // Prune removed markers
        Object.keys(state.busMarkers).forEach(bId => {
            if (!currentIds.has(bId)) {
                elements.map.removeLayer(state.busMarkers[bId]);
                delete state.busMarkers[bId];
            }
        });
    }

    async function loadAndDisplayRoutePath(bus) {
        if (state.viewMode === "history") return;

        try {
            const res = await fetch(`/api/buses/${bus.bus_id}/routes`);
            const data = await res.json();
            const routes = data.routes || [];

            let waypoints = null;
            if (routes.length > 0 && routes[0].waypoints) {
                waypoints = routes[0].waypoints;
            } else {
                const allRoutesRes = await fetch("/api/routes");
                const allRoutesData = await allRoutesRes.json();
                const matched = (allRoutesData.routes || []).find(r => r.id === bus.route_id);
                if (matched && matched.waypoints) {
                    waypoints = matched.waypoints;
                }
            }

            if (waypoints && waypoints.length > 0) {
                if (state.routePolyline) {
                    elements.map.removeLayer(state.routePolyline);
                }
                state.routePolyline = L.polyline(waypoints, {
                    color: '#2563eb',
                    weight: 4,
                    opacity: 0.85
                }).addTo(elements.map);
            }
        } catch (e) {
            console.error("Error loading route polyline:", e);
        }
    }

    // ==========================================
    // 6. SEVEN-DAY ROUTE HISTORY & REPLAY ENGINE
    // ==========================================
    function switchViewMode(mode) {
        state.viewMode = mode;
        const isLive = (mode === "live");

        elements.btnModeLive.classList.toggle("active", isLive);
        elements.btnModeHistory.classList.toggle("active", !isLive);

        elements.liveTelemetrySection.classList.toggle("hidden", !isLive);
        elements.historyTelemetrySection.classList.toggle("hidden", isLive);

        if (isLive) {
            // Stop and clear history layers
            stopReplay();
            clearHistoryLayers();
            updateMapMarkers();
            const bus = state.buses.find(b => b.bus_id === state.selectedBusId);
            if (bus) loadAndDisplayRoutePath(bus);
        } else {
            // Hide live markers while exploring history
            Object.values(state.busMarkers).forEach(m => elements.map.removeLayer(m));
            if (state.routePolyline) elements.map.removeLayer(state.routePolyline);

            // Populate rolling 7 days pills
            render7DayPills();

            if (state.selectedBusId) {
                loadHistoryForDate(state.selectedBusId, state.selectedDate);
            }
        }
    }

    function render7DayPills() {
        const daysOfWeek = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"];
        const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

        elements.sevenDayNavPills.innerHTML = "";
        const now = new Date();

        if (!state.selectedDate) {
            // Default to today
            state.selectedDate = formatDateKey(now);
        }

        // Generate past 7 days (day 0 to day 6)
        for (let i = 0; i < 7; i++) {
            const d = new Date(now);
            d.setDate(now.getDate() - i);

            const dateKey = formatDateKey(d);
            const dayName = (i === 0) ? "TODAY" : (i === 1 ? "YSTD" : daysOfWeek[d.getDay()]);
            const dayMonthStr = `${d.getDate()} ${months[d.getMonth()]}`;

            const pillBtn = document.createElement("button");
            pillBtn.className = `date-pill-btn ${dateKey === state.selectedDate ? 'active' : ''}`;
            pillBtn.dataset.date = dateKey;

            pillBtn.innerHTML = `
                <span class="pill-day">${dayName}</span>
                <span class="pill-date">${dayMonthStr}</span>
            `;

            pillBtn.addEventListener("click", () => {
                document.querySelectorAll(".date-pill-btn").forEach(b => b.classList.remove("active"));
                pillBtn.classList.add("active");
                state.selectedDate = dateKey;
                if (state.selectedBusId) {
                    loadHistoryForDate(state.selectedBusId, dateKey);
                }
            });

            elements.sevenDayNavPills.appendChild(pillBtn);
        }
    }

    async function loadHistoryForDate(busId, dateStr) {
        stopReplay();
        clearHistoryLayers();

        try {
            const res = await fetch(`/api/buses/${encodeURIComponent(busId)}/history?date=${encodeURIComponent(dateStr)}&limit=1000`);
            if (!res.ok) throw new Error("Failed to load date history");

            const data = await res.json();
            state.historyRecords = data.history || [];
            const summary = data.trip_summary || {};

            // Update Summary Card
            elements.histDistVal.textContent = `${summary.total_distance_km || 0.0} km`;
            elements.histMaxSpeedVal.textContent = `${Math.round(summary.max_speed || 0)} km/h`;
            elements.histStopsVal.textContent = summary.stops_count || 0;
            elements.histPointsVal.textContent = state.historyRecords.length;

            if (state.historyRecords.length === 0) {
                elements.replayWaypointProgress.textContent = "No GPS records on this day";
                elements.replayScrubber.max = 0;
                elements.replayScrubber.value = 0;
                elements.replayCurrentTime.textContent = "--:--";
                elements.replayCurrentSpeed.textContent = "0 km/h";
                return;
            }

            // Draw Chronological Polyline
            const latlngs = state.historyRecords.map(r => [r.latitude, r.longitude]);
            state.historyPolyline = L.polyline(latlngs, {
                color: '#2563eb',
                weight: 5,
                opacity: 0.85
            }).addTo(elements.map);
            state.historyLayers.push(state.historyPolyline);

            // Add Start Marker Pin (Green Pin)
            const firstPt = state.historyRecords[0];
            const startPin = L.marker([firstPt.latitude, firstPt.longitude], {
                icon: createHistoryPinIcon("start", `Route Start: ${firstPt.time || ''}`)
            }).bindPopup(`<strong>Journey Start</strong><br>Time: ${firstPt.time || firstPt.timestamp}<br>Speed: ${firstPt.speed} km/h`).addTo(elements.map);
            state.historyLayers.push(startPin);

            // Add Terminus / End Marker Pin (Red Pin)
            const lastPt = state.historyRecords[state.historyRecords.length - 1];
            const endPin = L.marker([lastPt.latitude, lastPt.longitude], {
                icon: createHistoryPinIcon("end", `Route End: ${lastPt.time || ''}`)
            }).bindPopup(`<strong>Journey Terminus</strong><br>Time: ${lastPt.time || lastPt.timestamp}<br>Speed: ${lastPt.speed} km/h`).addTo(elements.map);
            state.historyLayers.push(endPin);

            // Add intermediate small waypoint dots with hover tooltips
            state.historyRecords.forEach((pt, idx) => {
                if (idx > 0 && idx < state.historyRecords.length - 1 && idx % 3 === 0) {
                    const dot = L.circleMarker([pt.latitude, pt.longitude], {
                        radius: 3,
                        color: '#3b82f6',
                        fillColor: '#ffffff',
                        fillOpacity: 0.9,
                        weight: 2
                    }).bindPopup(`Waypoint #${idx + 1}<br>Time: ${pt.time}<br>Speed: ${pt.speed} km/h`).addTo(elements.map);
                    state.historyLayers.push(dot);
                }
            });

            // Fit map bounds to show complete journey
            elements.map.fitBounds(state.historyPolyline.getBounds(), { padding: [50, 50] });

            // Initialize Replay Scrubber
            elements.replayScrubber.max = state.historyRecords.length - 1;
            elements.replayScrubber.value = 0;
            state.replay.index = 0;
            updateReplayPosition(0);

        } catch (err) {
            console.error("Error loading route history:", err);
            showToast("Failed to load historical route records", "error");
        }
    }

    function clearHistoryLayers() {
        state.historyLayers.forEach(layer => elements.map.removeLayer(layer));
        state.historyLayers = [];
        if (state.replay.marker) {
            elements.map.removeLayer(state.replay.marker);
            state.replay.marker = null;
        }
    }

    function updateReplayPosition(index) {
        if (!state.historyRecords || state.historyRecords.length === 0) return;
        state.replay.index = Math.max(0, Math.min(index, state.historyRecords.length - 1));

        const pt = state.historyRecords[state.replay.index];
        elements.replayScrubber.value = state.replay.index;
        elements.replayCurrentTime.textContent = pt.time || "--:--";
        elements.replayCurrentSpeed.textContent = `${Math.round(pt.speed || 0)} km/h`;
        elements.replayWaypointProgress.textContent = `Point ${state.replay.index + 1} / ${state.historyRecords.length}`;

        const heading = pt.heading || 0;
        if (!state.replay.marker) {
            state.replay.marker = L.marker([pt.latitude, pt.longitude], {
                icon: createReplayMarkerIcon(heading),
                zIndexOffset: 1000
            }).addTo(elements.map);
        } else {
            state.replay.marker.setLatLng([pt.latitude, pt.longitude]);
            state.replay.marker.setIcon(createReplayMarkerIcon(heading));
        }
    }

    function toggleReplayPlayPause() {
        if (state.replay.isPlaying) {
            stopReplay();
        } else {
            startReplay();
        }
    }

    function startReplay() {
        if (!state.historyRecords || state.historyRecords.length === 0) return;

        // If at end, loop back to start
        if (state.replay.index >= state.historyRecords.length - 1) {
            state.replay.index = 0;
        }

        state.replay.isPlaying = true;
        elements.replayPlayPauseBtn.innerHTML = '<i class="fa-solid fa-pause"></i>';
        elements.replayPlayPauseBtn.classList.add("playing");

        const stepMs = Math.max(80, Math.floor(400 / state.replay.speedMultiplier));
        state.replay.timer = setInterval(() => {
            if (state.replay.index < state.historyRecords.length - 1) {
                updateReplayPosition(state.replay.index + 1);
            } else {
                stopReplay();
            }
        }, stepMs);
    }

    function stopReplay() {
        state.replay.isPlaying = false;
        if (state.replay.timer) {
            clearInterval(state.replay.timer);
            state.replay.timer = null;
        }
        if (elements.replayPlayPauseBtn) {
            elements.replayPlayPauseBtn.innerHTML = '<i class="fa-solid fa-play"></i>';
            elements.replayPlayPauseBtn.classList.remove("playing");
        }
    }

    function resetReplay() {
        stopReplay();
        updateReplayPosition(0);
    }

    // ==========================================
    // 7. ESP HARDWARE DEVICE MANAGEMENT
    // ==========================================
    async function fetchDevices() {
        try {
            const res = await fetch("/api/devices");
            if (!res.ok) throw new Error("Failed to load ESP devices");

            const data = await res.json();
            state.devices = data.devices || [];

            renderDevicesTable();
            populateDevBusDropdown();

            // Update Header Counter Badge (Online / Total)
            const onlineCount = data.metrics ? data.metrics.online_devices : 0;
            const totalCount = data.metrics ? data.metrics.total_devices : state.devices.length;
            elements.devicesHeaderBadge.textContent = `${onlineCount}/${totalCount}`;

            // Update Modal Quick Metric Cards
            if (elements.devMetricTotal) elements.devMetricTotal.textContent = totalCount;
            if (elements.devMetricOnline) elements.devMetricOnline.textContent = onlineCount;
            if (elements.devMetricUnassigned) elements.devMetricUnassigned.textContent = data.metrics ? data.metrics.unassigned_devices : 0;
            if (elements.devMetricGps) {
                const gpsActiveCount = state.devices.filter(d => d.gps_available).length;
                elements.devMetricGps.textContent = gpsActiveCount;
            }

            // Check if any devices are unassigned
            const unassignedCount = data.metrics ? data.metrics.unassigned_devices : 0;
            elements.unassignedAlertBanner.classList.toggle("hidden", unassignedCount === 0);

        } catch (err) {
            console.error("Error fetching ESP devices:", err);
        }
    }

    function getPlatformBadge(type) {
        const t = (type || "ESP8266").toUpperCase();
        if (t === "ESP8266") return `<span class="badge-platform esp8266">ESP8266</span>`;
        if (t === "ESP32") return `<span class="badge-platform esp32">ESP32</span>`;
        if (t.includes("CELLULAR") || t.includes("4G") || t.includes("A7670")) return `<span class="badge-platform cellular">4G LTE</span>`;
        if (t.includes("PICO")) return `<span class="badge-platform rpi">Pico W</span>`;
        if (t.includes("STM32")) return `<span class="badge-platform">STM32</span>`;
        return `<span class="badge-platform">${type}</span>`;
    }

    function renderDevicesTable() {
        elements.devicesTableBody.innerHTML = "";

        if (state.devices.length === 0) {
            elements.devicesTableBody.innerHTML = `
                <tr>
                    <td colspan="8" style="text-align:center;padding:24px;color:var(--text-muted);">
                        No hardware devices registered yet. Register a device below.
                    </td>
                </tr>
            `;
            return;
        }

        state.devices.forEach(dev => {
            const tr = document.createElement("tr");

            const statusClass = dev.status || "offline";
            const statusLabel = dev.status_label || "Offline";
            const lastSeenStr = dev.last_seen_relative || "Never";

            // Build Bus Assignment Dropdown Options
            let busOptionsHtml = `<option value="">-- Unassigned --</option>`;
            state.buses.forEach(b => {
                const selected = (b.bus_id === dev.assigned_bus_id) ? "selected" : "";
                busOptionsHtml += `<option value="${b.bus_id}" ${selected}>${b.bus_name} (${b.bus_number})</option>`;
            });

            const platformBadgeHtml = getPlatformBadge(dev.device_type);
            const gpsFixBadgeHtml = dev.gps_available
                ? `<span class="badge-gps active"><i class="fa-solid fa-satellite-dish"></i> Fix Active</span>`
                : `<span class="badge-gps searching"><i class="fa-solid fa-satellite"></i> Searching</span>`;
            const autoBadgeHtml = dev.auto_discovered ? `<span class="badge-autodisc">Auto</span>` : "";

            tr.innerHTML = `
                <td>
                    <span class="device-status-badge ${statusClass}">
                        <i class="fa-solid fa-circle" style="font-size:7px;"></i>
                        <span>${statusLabel}</span>
                    </span>
                </td>
                <td>
                    <div class="device-name-container">
                        <strong>${dev.device_name || dev.device_id}</strong>
                        <button class="btn-rename-device" data-device-id="${dev.device_id}" title="Rename Device">
                            <i class="fa-solid fa-pen"></i>
                        </button>
                    </div>
                    <div style="font-size:10px;color:var(--text-muted);font-family:monospace;">
                        ${dev.device_id} ${autoBadgeHtml}
                    </div>
                </td>
                <td>${platformBadgeHtml}</td>
                <td>
                    <span class="mono" style="font-size:11px;color:var(--text-muted);">${dev.mac_address || 'AA:BB:CC:--'}</span>
                </td>
                <td>${gpsFixBadgeHtml}</td>
                <td>
                    <select class="device-bus-select" data-device-id="${dev.device_id}">
                        ${busOptionsHtml}
                    </select>
                </td>
                <td><span style="font-size:11px;color:var(--text-muted);">${lastSeenStr}</span></td>
                <td>
                    <div style="display:flex;gap:4px;">
                        <button class="btn btn-outline btn-sm btn-assign-device" data-device-id="${dev.device_id}" title="Save Bus Assignment">
                            <i class="fa-solid fa-link"></i>
                        </button>
                        <button class="btn btn-outline btn-sm btn-delete-device" data-device-id="${dev.device_id}" title="Delete Tracker" style="color:#ef4444;">
                            <i class="fa-solid fa-trash-can"></i>
                        </button>
                    </div>
                </td>
            `;

            // Rename Button Listener
            const renameBtn = tr.querySelector(".btn-rename-device");
            if (renameBtn) {
                renameBtn.addEventListener("click", async () => {
                    await renameDevice(dev.device_id, dev.device_name);
                });
            }

            // Assign / Reassign Button Listener
            tr.querySelector(".btn-assign-device").addEventListener("click", async () => {
                const select = tr.querySelector(".device-bus-select");
                const targetBusId = select.value;
                await assignDeviceToBus(dev.device_id, targetBusId);
            });

            // Delete Button Listener
            tr.querySelector(".btn-delete-device").addEventListener("click", async () => {
                if (confirm(`Are you sure you want to delete Device '${dev.device_id}'?`)) {
                    await deleteDevice(dev.device_id);
                }
            });

            elements.devicesTableBody.appendChild(tr);
        });
    }

    async function renameDevice(deviceId, currentName) {
        const newName = prompt(`Enter new friendly name for device '${deviceId}':`, currentName || "");
        if (newName === null) return; // User cancelled
        const trimmed = newName.trim();
        if (!trimmed) {
            showToast("Device name cannot be empty", "warning");
            return;
        }

        try {
            const res = await fetch(`/api/devices/${encodeURIComponent(deviceId)}`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ device_name: trimmed })
            });
            const data = await res.json();
            if (res.ok && data.status === "success") {
                showToast(`Device renamed to '${trimmed}'`, "success");
                await fetchDevices();
            } else {
                showToast(data.message || "Failed to rename device", "error");
            }
        } catch (err) {
            showToast("Network error renaming device", "error");
        }
    }

    function populateDevBusDropdown() {
        elements.devBusSelect.innerHTML = `<option value="">-- Unassigned (Standby) --</option>`;
        state.buses.forEach(b => {
            elements.devBusSelect.innerHTML += `<option value="${b.bus_id}">${b.bus_name} (${b.bus_number})</option>`;
        });
    }

    async function assignDeviceToBus(deviceId, busId) {
        try {
            const res = await fetch(`/api/devices/${encodeURIComponent(deviceId)}/assign`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ bus_id: busId || null })
            });
            const data = await res.json();

            if (res.ok && data.status === "success") {
                showToast(`Device ${deviceId} assigned to ${busId || 'Unassigned'}`, "success");
                await fetchDevices();
                await fetchBuses();
            } else {
                showToast(data.message || "Failed to assign device", "error");
            }
        } catch (err) {
            showToast("Network error assigning device", "error");
        }
    }

    async function deleteDevice(deviceId) {
        try {
            const res = await fetch(`/api/devices/${encodeURIComponent(deviceId)}`, {
                method: "DELETE"
            });
            const data = await res.json();

            if (res.ok && data.status === "success") {
                showToast(`Device ${deviceId} deleted successfully`, "success");
                await fetchDevices();
            } else {
                showToast(data.message || "Failed to delete device", "error");
            }
        } catch (err) {
            showToast("Network error deleting device", "error");
        }
    }

    // ==========================================
    // 8. EVENT LISTENERS
    // ==========================================
    function setupEventListeners() {
        // Search Filter
        elements.busSearchInput.addEventListener("input", (e) => {
            state.searchQuery = e.target.value.trim();
            elements.clearSearchBtn.classList.toggle("hidden", state.searchQuery.length === 0);
            renderBusesList();
        });

        elements.clearSearchBtn.addEventListener("click", () => {
            elements.busSearchInput.value = "";
            state.searchQuery = "";
            elements.clearSearchBtn.classList.add("hidden");
            renderBusesList();
        });

        // Quick Status Tabs (All / Connected / Offline)
        elements.statusTabBtns.forEach(btn => {
            btn.addEventListener("click", (e) => {
                elements.statusTabBtns.forEach(b => b.classList.remove("active"));
                e.currentTarget.classList.add("active");
                state.activeFilter = e.currentTarget.dataset.filter;
                renderBusesList();
            });
        });

        // Mode Switching: Live vs 7-Day History
        elements.btnModeLive.addEventListener("click", () => switchViewMode("live"));
        elements.btnModeHistory.addEventListener("click", () => switchViewMode("history"));

        // Replay Controls
        elements.replayPlayPauseBtn.addEventListener("click", toggleReplayPlayPause);
        elements.replayResetBtn.addEventListener("click", resetReplay);

        elements.replayScrubber.addEventListener("input", (e) => {
            stopReplay();
            updateReplayPosition(parseInt(e.target.value, 10));
        });

        elements.speedOptBtns.forEach(btn => {
            btn.addEventListener("click", (e) => {
                elements.speedOptBtns.forEach(b => b.classList.remove("active"));
                e.currentTarget.classList.add("active");
                state.replay.speedMultiplier = parseInt(e.currentTarget.dataset.speed, 10);
                if (state.replay.isPlaying) {
                    stopReplay();
                    startReplay();
                }
            });
        });

        // 1-Click Copy Coordinates
        elements.hudCopyCoordsBtn.addEventListener("click", () => {
            const coords = elements.hudCoordsVal.textContent;
            if (coords && coords !== "Waiting for GPS fix...") {
                navigator.clipboard.writeText(coords).then(() => {
                    showToast("GPS coordinates copied to clipboard!", "success");
                }).catch(() => {
                    showToast("Failed to copy coordinates", "error");
                });
            }
        });

        // Map Control: Center Selected Bus
        elements.centerSelectedBusBtn.addEventListener("click", () => {
            if (state.selectedBusId) {
                const bus = state.buses.find(b => b.bus_id === state.selectedBusId);
                if (bus && bus.current_location) {
                    elements.map.flyTo([bus.current_location.latitude, bus.current_location.longitude], 16, { duration: 1.0 });
                }
            }
        });

        // Map Control: Fit All Buses
        elements.fitAllBusesBtn.addEventListener("click", () => {
            if (state.viewMode === "history" && state.historyPolyline) {
                elements.map.fitBounds(state.historyPolyline.getBounds(), { padding: [50, 50] });
            } else {
                const markers = Object.values(state.busMarkers);
                if (markers.length > 0) {
                    const group = L.featureGroup(markers);
                    elements.map.fitBounds(group.getBounds(), { padding: [50, 50] });
                }
            }
        });

        // Mobile Tabs Switching
        elements.mobileTabBusesBtn.addEventListener("click", () => switchMobileTab("buses"));
        elements.mobileTabMapBtn.addEventListener("click", () => switchMobileTab("map"));

        // Register Bus Modal
        elements.openRegisterModalBtn.addEventListener("click", () => {
            elements.registerBusModal.classList.remove("hidden");
        });

        elements.closeRegisterModalBtn.addEventListener("click", () => {
            elements.registerBusModal.classList.add("hidden");
        });

        // Simple Register Bus Form Submission
        elements.simpleAddBusForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            const busData = {
                bus_name: document.getElementById("newBusName").value.trim(),
                bus_id: document.getElementById("newBusId").value.trim().toUpperCase(),
                bus_number: document.getElementById("newBusNumber").value.trim(),
                device_id: document.getElementById("newDeviceId").value.trim(),
                campus: "Sphoorthy Campus Lead",
                route_id: document.getElementById("newRouteSelect").value,
                route_name: document.getElementById("newRouteSelect").selectedOptions[0].text,
                driver_name: document.getElementById("newDriverName").value.trim() || "Unassigned",
                driver_phone: document.getElementById("newDriverPhone").value.trim() || "N/A"
            };

            try {
                const res = await fetch("/api/buses", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(busData)
                });
                const data = await res.json();

                if (res.ok && data.status === "success") {
                    showToast(`Bus ${busData.bus_name} registered successfully!`, "success");
                    elements.simpleAddBusForm.reset();
                    elements.registerBusModal.classList.add("hidden");
                    await fetchBuses();
                    await fetchDevices();
                } else {
                    showToast(data.message || "Failed to register bus", "error");
                }
            } catch (err) {
                showToast("Network error registering bus", "error");
            }
        });

        // Devices Modal
        elements.openDevicesModalBtn.addEventListener("click", () => {
            fetchDevices();
            elements.devicesModal.classList.remove("hidden");
        });

        elements.closeDevicesModalBtn.addEventListener("click", () => {
            elements.devicesModal.classList.add("hidden");
        });

        // Register New Hardware Device Form Submission
        elements.addDeviceForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            const devData = {
                device_id: elements.devIdInput.value.trim().toUpperCase(),
                device_name: elements.devNameInput && elements.devNameInput.value.trim() ? elements.devNameInput.value.trim() : undefined,
                mac_address: elements.devMacInput.value.trim().toUpperCase(),
                device_type: elements.devTypeInput.value,
                assigned_bus_id: elements.devBusSelect.value || null
            };

            try {
                const res = await fetch("/api/devices", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(devData)
                });
                const data = await res.json();

                if (res.ok && data.status === "success") {
                    showToast(`Device ${devData.device_id} registered successfully!`, "success");
                    elements.addDeviceForm.reset();
                    await fetchDevices();
                    await fetchBuses();
                } else {
                    showToast(data.message || "Failed to register device", "error");
                }
            } catch (err) {
                showToast("Network error registering device", "error");
            }
        });
    }

    function switchMobileTab(tab) {
        state.mobileActiveTab = tab;
        elements.mobileTabBusesBtn.classList.toggle("active", tab === "buses");
        elements.mobileTabMapBtn.classList.toggle("active", tab === "map");

        if (tab === "buses") {
            elements.busSelectorPanel.classList.remove("mobile-hidden");
            elements.liveMapPanel.classList.add("mobile-hidden");
        } else {
            elements.busSelectorPanel.classList.add("mobile-hidden");
            elements.liveMapPanel.classList.remove("mobile-hidden");
            setTimeout(() => elements.map.invalidateSize(), 200);
        }
    }

    // ==========================================
    // 9. AUTO REFRESH LOOP
    // ==========================================
    function startAutoRefreshLoop() {
        fetchBuses();
        fetchDevices();

        state.timerId = setInterval(() => {
            state.countdownRemaining--;
            if (state.countdownRemaining <= 0) {
                state.countdownRemaining = state.autoRefreshInterval;
                if (state.viewMode === "live") {
                    fetchBuses();
                }
            }
        }, 1000);
    }

    // ==========================================
    // 10. UTILITIES
    // ==========================================
    function formatDateKey(dateObj) {
        const d = String(dateObj.getDate()).padStart(2, '0');
        const m = String(dateObj.getMonth() + 1).padStart(2, '0');
        const y = dateObj.getFullYear();
        return `${d}-${m}-${y}`;
    }

    function formatTimeAgo(isoString) {
        if (!isoString) return "Never";
        try {
            const date = new Date(isoString);
            const now = new Date();
            const seconds = Math.floor((now - date) / 1000);

            if (seconds < 5) return "Just now";
            if (seconds < 60) return `${seconds}s ago`;
            const minutes = Math.floor(seconds / 60);
            if (minutes < 60) return `${minutes}m ago`;
            const hours = Math.floor(minutes / 60);
            return `${hours}h ago`;
        } catch (e) {
            return "Recently";
        }
    }

    function showToast(message, type = "info") {
        const toast = document.createElement("div");
        toast.className = `toast ${type}`;
        const icon = type === "success" ? "fa-circle-check" : "fa-circle-info";
        toast.innerHTML = `<i class="fa-solid ${icon}"></i> <span>${message}</span>`;
        elements.toastContainer.appendChild(toast);

        setTimeout(() => {
            toast.style.opacity = "0";
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }

    // ==========================================
    // 11. INITIALIZE APPLICATION
    // ==========================================
    initMap();
    setupEventListeners();
    startAutoRefreshLoop();
});
