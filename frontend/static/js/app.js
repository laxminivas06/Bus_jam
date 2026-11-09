/**
 * CampusFleet - Sphoorthy Campus Lead Live Bus Tracking System
 * Frontend Application JavaScript (Simplified, Lightweight, Real-Time)
 */

document.addEventListener("DOMContentLoaded", () => {
    // ==========================================
    // 1. STATE MANAGEMENT
    // ==========================================
    const state = {
        buses: [],
        selectedBusId: null,
        busMarkers: {},        // Map of { bus_id: L.marker }
        routePolyline: null,   // Active route L.polyline
        activeFilter: "all",   // "all" | "connected" | "offline"
        searchQuery: "",
        autoRefreshInterval: 5, // 5 seconds
        countdownRemaining: 5,
        timerId: null,
        mobileActiveTab: "buses" // "buses" | "map"
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
        hudConnectionBadge: document.getElementById("hudConnectionBadge"),
        hudCoordsVal: document.getElementById("hudCoordsVal"),
        hudCopyCoordsBtn: document.getElementById("hudCopyCoordsBtn"),
        hudGoogleMapsLink: document.getElementById("hudGoogleMapsLink"),
        hudSpeedVal: document.getElementById("hudSpeedVal"),
        hudHeadingVal: document.getElementById("hudHeadingVal"),
        hudSatsVal: document.getElementById("hudSatsVal"),
        hudUpdatedVal: document.getElementById("hudUpdatedVal"),
        hudRouteVal: document.getElementById("hudRouteVal"),

        // Map Controls
        centerSelectedBusBtn: document.getElementById("centerSelectedBusBtn"),
        fitAllBusesBtn: document.getElementById("fitAllBusesBtn"),

        // Modal
        registerBusModal: document.getElementById("registerBusModal"),
        closeRegisterModalBtn: document.getElementById("closeRegisterModalBtn"),
        simpleAddBusForm: document.getElementById("simpleAddBusForm"),

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

    // Directional Marker Pin Generator
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
                        <span class="bus-number-badge">${bus.bus_number}</span>
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

        // Update Map Markers and Pan/Zoom
        updateMapMarkers();

        if (bus.current_location) {
            elements.map.flyTo([bus.current_location.latitude, bus.current_location.longitude], 15, {
                duration: 1.0
            });
            if (state.busMarkers[busId]) {
                state.busMarkers[busId].openPopup();
            }
        }

        // Draw Route Polyline
        loadAndDisplayRoutePath(bus);

        // On mobile: switch to Map view automatically if clicked by user
        if (userInitiated && window.innerWidth <= 900) {
            switchMobileTab("map");
        }
    }

    function updateTelemetryHUD(bus) {
        elements.hudBusName.textContent = bus.bus_name || bus.bus_id;
        elements.hudBusNumber.textContent = bus.bus_number || bus.bus_id;

        const isOnline = bus.is_online;
        const statusClass = bus.connection_status || (isOnline ? "connected" : "offline");
        const statusLabel = bus.connection_label || (isOnline ? "Connected" : "Offline");

        elements.hudConnectionBadge.className = `card-status-badge ${statusClass}`;
        elements.hudConnectionBadge.textContent = statusLabel;

        if (bus.current_location) {
            const lat = bus.current_location.latitude.toFixed(6);
            const lng = bus.current_location.longitude.toFixed(6);
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
        try {
            // First check if bus has detected/assigned routes
            const res = await fetch(`/api/buses/${bus.bus_id}/routes`);
            const data = await res.json();
            const routes = data.routes || [];

            let waypoints = null;
            if (routes.length > 0 && routes[0].waypoints) {
                waypoints = routes[0].waypoints;
            } else {
                // Fallback to route endpoints
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
    // 6. EVENT LISTENERS
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
            const markers = Object.values(state.busMarkers);
            if (markers.length > 0) {
                const group = L.featureGroup(markers);
                elements.map.fitBounds(group.getBounds(), { padding: [50, 50] });
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
                    fetchBuses();
                } else {
                    showToast(data.message || "Failed to register bus", "error");
                }
            } catch (err) {
                showToast("Network error registering bus", "error");
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
    // 7. AUTO REFRESH LOOP
    // ==========================================
    function startAutoRefreshLoop() {
        fetchBuses();

        state.timerId = setInterval(() => {
            state.countdownRemaining--;
            if (state.countdownRemaining <= 0) {
                state.countdownRemaining = state.autoRefreshInterval;
                fetchBuses();
            }
        }, 1000);
    }

    // ==========================================
    // 8. UTILITIES
    // ==========================================
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
    // 9. INITIALIZE APPLICATION
    // ==========================================
    initMap();
    setupEventListeners();
    startAutoRefreshLoop();
});
