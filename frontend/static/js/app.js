/**
 * CampusFleet - College Bus Live Tracking System
 * Frontend Application JavaScript (Vanilla ES6 + Leaflet.js)
 */

document.addEventListener("DOMContentLoaded", () => {
    // State Management
    const state = {
        buses: [],
        routes: [],
        selectedBusId: null,
        busMarkers: {}, // Reusable Leaflet markers map: { bus_id: L.marker }
        historyPolyline: null,
        historyMarkers: [],
        activeFilters: {
            search: "",
            route: "all",
            status: "all"
        },
        metrics: {
            total: 0,
            online: 0,
            offline: 0
        },
        autoRefreshInterval: 10, // seconds
        countdownRemaining: 10,
        timerId: null,
        isAdmin: false
    };

    // DOM Elements
    const elements = {
        map: null, // Leaflet map instance
        sidebar: document.getElementById("sidebar"),
        openSidebarBtn: document.getElementById("openSidebarBtn"),
        closeSidebarBtn: document.getElementById("closeSidebarBtn"),
        
        statTotalCount: document.getElementById("statTotalCount"),
        statOnlineCount: document.getElementById("statOnlineCount"),
        statOfflineCount: document.getElementById("statOfflineCount"),
        mobileOnlineCount: document.getElementById("mobileOnlineCount"),
        
        filterStatTotal: document.getElementById("filterStatTotal"),
        filterStatOnline: document.getElementById("filterStatOnline"),
        filterStatOffline: document.getElementById("filterStatOffline"),
        
        busSearchInput: document.getElementById("busSearchInput"),
        clearSearchBtn: document.getElementById("clearSearchBtn"),
        routeFilterSelect: document.getElementById("routeFilterSelect"),
        statusFilterSelect: document.getElementById("statusFilterSelect"),
        
        busCardsList: document.getElementById("busCardsList"),
        filteredCountBadge: document.getElementById("filteredCountBadge"),
        
        busDetailDrawer: document.getElementById("busDetailDrawer"),
        closeDrawerBtn: document.getElementById("closeDrawerBtn"),
        detailBusId: document.getElementById("detailBusId"),
        detailBusNumber: document.getElementById("detailBusNumber"),
        detailStatusIndicator: document.getElementById("detailStatusIndicator"),
        detailStatusText: document.getElementById("detailStatusText"),
        detailRouteName: document.getElementById("detailRouteName"),
        detailSpeed: document.getElementById("detailSpeed"),
        detailHeading: document.getElementById("detailHeading"),
        detailCoordinates: document.getElementById("detailCoordinates"),
        detailDriverName: document.getElementById("detailDriverName"),
        detailDriverPhone: document.getElementById("detailDriverPhone"),
        detailLastUpdated: document.getElementById("detailLastUpdated"),
        drawerHistoryDateSelect: document.getElementById("drawerHistoryDateSelect"),
        centerMapBtn: document.getElementById("centerMapBtn"),
        toggleHistoryBtn: document.getElementById("toggleHistoryBtn"),
        
        nextRefreshCountdown: document.getElementById("nextRefreshCountdown"),
        manualRefreshIcon: document.getElementById("manualRefreshIcon"),
        mapFitBoundsBtn: document.getElementById("mapFitBoundsBtn"),
        
        openAdminBtn: document.getElementById("openAdminBtn"),
        adminModal: document.getElementById("adminModal"),
        closeAdminModalBtn: document.getElementById("closeAdminModalBtn"),
        adminLoginForm: document.getElementById("adminLoginForm"),
        adminLoginView: document.getElementById("adminLoginView"),
        adminDashboardView: document.getElementById("adminDashboardView"),
        adminUsernameInput: document.getElementById("adminUsernameInput"),
        adminPasswordInput: document.getElementById("adminPasswordInput"),
        adminLoginError: document.getElementById("adminLoginError"),
        adminLogoutBtn: document.getElementById("adminLogoutBtn"),
        
        tabHistoryAuditBtn: document.getElementById("tabHistoryAuditBtn"),
        tabAddBusBtn: document.getElementById("tabAddBusBtn"),
        adminHistorySection: document.getElementById("adminHistorySection"),
        adminAddBusSection: document.getElementById("adminAddBusSection"),
        adminHistoryBusSelect: document.getElementById("adminHistoryBusSelect"),
        adminHistoryDateInput: document.getElementById("adminHistoryDateInput"),
        adminViewLocationsBtn: document.getElementById("adminViewLocationsBtn"),
        adminHistoryResults: document.getElementById("adminHistoryResults"),
        adminHistoryCountBadge: document.getElementById("adminHistoryCountBadge"),
        adminHistoryTableBody: document.getElementById("adminHistoryTableBody"),
        adminShowOnMapBtn: document.getElementById("adminShowOnMapBtn"),

        addBusForm: document.getElementById("addBusForm"),
        adminFormMsg: document.getElementById("adminFormMsg")
    };

    // ==========================================
    // 1. MAP INITIALIZATION (Leaflet.js + OpenStreetMap)
    // ==========================================
    function initMap() {
        // Default center: [17.385044, 78.486671] (Hyderabad)
        const defaultCenter = [17.385044, 78.486671];
        
        elements.map = L.map("map", {
            center: defaultCenter,
            zoom: 12,
            zoomControl: false
        });

        // Add Zoom Control to bottom right
        L.control.zoom({ position: "bottomright" }).addTo(elements.map);

        // OpenStreetMap Tile Layer
        L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
            maxZoom: 19,
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        }).addTo(elements.map);
    }

    // Custom Bus Marker HTML Generator
    function createBusMarkerIcon(bus, isSelected = false) {
        const isOnline = bus.is_online;
        const statusClass = isOnline ? "online" : "offline";
        const selectedClass = isSelected ? "selected" : "";
        const heading = bus.current_location ? bus.current_location.heading || 0 : 0;

        const html = `
            <div class="bus-marker-container">
                <div class="bus-marker-pin ${statusClass} ${selectedClass}" style="transform: rotate(${heading}deg);">
                    <i class="fa-solid fa-bus"></i>
                </div>
            </div>
        `;

        return L.divIcon({
            html: html,
            className: "custom-bus-marker-wrapper",
            iconSize: [40, 40],
            iconAnchor: [20, 20],
            popupAnchor: [0, -20]
        });
    }

    // ==========================================
    // 2. API DATA FETCH & MARKER REUSE
    // ==========================================
    async function fetchBuses() {
        try {
            elements.manualRefreshIcon.classList.add("active");
            
            const queryParams = new URLSearchParams();
            if (state.activeFilters.search) queryParams.append("search", state.activeFilters.search);
            if (state.activeFilters.route !== "all") queryParams.append("route", state.activeFilters.route);
            if (state.activeFilters.status !== "all") queryParams.append("status", state.activeFilters.status);

            const response = await fetch(`/api/buses?${queryParams.toString()}`);
            if (!response.ok) throw new Error("Failed to fetch bus locations");

            const data = await response.json();
            
            state.buses = data.buses || [];
            state.metrics = data.metrics || { total_buses: 0, online_buses: 0, offline_buses: 0 };
            state.routes = data.routes || [];

            // Update UI components
            updateMetricsUI();
            updateRoutesDropdown();
            renderBusCardsList();
            updateMapMarkers();

            // If a bus is selected, update its detail drawer info
            if (state.selectedBusId) {
                const currentSelected = state.buses.find(b => b.bus_id === state.selectedBusId);
                if (currentSelected) {
                    populateDetailDrawer(currentSelected);
                }
            }

        } catch (error) {
            console.error("Error fetching bus locations:", error);
        } finally {
            setTimeout(() => {
                elements.manualRefreshIcon.classList.remove("active");
            }, 600);
        }
    }

    // Efficient Marker Reuse Logic
    function updateMapMarkers() {
        const currentBusIdsInView = new Set();

        state.buses.forEach(bus => {
            if (!bus.current_location) return;

            const busId = bus.bus_id;
            const lat = bus.current_location.latitude;
            const lng = bus.current_location.longitude;
            const isSelected = (busId === state.selectedBusId);
            
            currentBusIdsInView.add(busId);

            // Re-use existing marker if present
            if (state.busMarkers[busId]) {
                const marker = state.busMarkers[busId];
                marker.setLatLng([lat, lng]);
                marker.setIcon(createBusMarkerIcon(bus, isSelected));
                marker.getPopup().setContent(generatePopupHTML(bus));
            } else {
                // Create new marker if it doesn't exist
                const marker = L.marker([lat, lng], {
                    icon: createBusMarkerIcon(bus, isSelected)
                });

                marker.bindPopup(generatePopupHTML(bus));
                marker.on("click", () => {
                    selectBus(busId);
                });

                marker.addTo(elements.map);
                state.busMarkers[busId] = marker;
            }
        });

        // Remove markers that are no longer matching the current filter
        Object.keys(state.busMarkers).forEach(busId => {
            if (!currentBusIdsInView.has(busId)) {
                elements.map.removeLayer(state.busMarkers[busId]);
                delete state.busMarkers[busId];
            }
        });
    }

    function generatePopupHTML(bus) {
        const speed = bus.current_location ? `${Math.round(bus.current_location.speed)} km/h` : 'N/A';
        const isOnline = bus.is_online;
        const statusBadge = isOnline ? '<span class="popup-speed">ONLINE</span>' : '<span class="popup-speed" style="background:rgba(239,68,68,0.2);color:#ef4444;">OFFLINE</span>';

        return `
            <div class="popup-content">
                <div class="popup-header">
                    <span class="popup-title">${bus.bus_id}</span>
                    ${statusBadge}
                </div>
                <div class="popup-route">${bus.route_name}</div>
                <div class="popup-info-line">
                    <i class="fa-solid fa-gauge-high"></i> Speed: <strong>${speed}</strong>
                </div>
                <div class="popup-info-line">
                    <i class="fa-solid fa-user"></i> Driver: ${bus.driver_name}
                </div>
            </div>
        `;
    }

    // ==========================================
    // 3. UI RENDERING & COUNTERS
    // ==========================================
    function updateMetricsUI() {
        elements.statTotalCount.textContent = state.metrics.total_buses || 0;
        elements.statOnlineCount.textContent = state.metrics.online_buses || 0;
        elements.statOfflineCount.textContent = state.metrics.offline_buses || 0;
        elements.mobileOnlineCount.textContent = state.metrics.online_buses || 0;
        elements.filteredCountBadge.textContent = `${state.buses.length} buses`;
    }

    function updateRoutesDropdown() {
        const currentSelection = elements.routeFilterSelect.value;
        
        // Preserve selected route or 'all'
        elements.routeFilterSelect.innerHTML = '<option value="all">All Routes</option>';
        
        state.routes.forEach(route => {
            const option = document.createElement("option");
            option.value = route;
            option.textContent = route;
            if (route === currentSelection) option.selected = true;
            elements.routeFilterSelect.appendChild(option);
        });
    }

    function renderBusCardsList() {
        elements.busCardsList.innerHTML = "";

        if (state.buses.length === 0) {
            elements.busCardsList.innerHTML = `
                <div class="empty-state-card">
                    <div class="empty-icon"><i class="fa-solid fa-satellite-dish"></i></div>
                    <h4>No Active Buses</h4>
                    <p>No bus tracking data available yet.<br>Transmit GPS coordinates to start tracking.</p>
                </div>
            `;
            return;
        }

        state.buses.forEach(bus => {
            const isSelected = (bus.bus_id === state.selectedBusId);
            const isOnline = bus.is_online;
            const statusClass = isOnline ? "online" : "offline";
            const speed = bus.current_location ? `${Math.round(bus.current_location.speed)} km/h` : "Stopped";
            const timeAgo = formatTimeAgo(bus.current_location ? bus.current_location.updated_at : null);

            const card = document.createElement("div");
            card.className = `bus-card ${statusClass} ${isSelected ? "active" : ""}`;
            card.dataset.busId = bus.bus_id;

            card.innerHTML = `
                <div class="card-top">
                    <span class="card-bus-id">${bus.bus_id}</span>
                    <span class="card-status-badge ${statusClass}">${statusClass}</span>
                </div>
                <div class="card-route">${bus.route_name}</div>
                <div class="card-bottom">
                    <span><i class="fa-solid fa-user-tie"></i> ${bus.driver_name}</span>
                    <span class="card-speed"><i class="fa-solid fa-gauge-high"></i> ${speed}</span>
                </div>
            `;

            card.addEventListener("click", () => selectBus(bus.bus_id));
            elements.busCardsList.appendChild(card);
        });
    }

    // Select Bus Action
    function selectBus(busId) {
        state.selectedBusId = busId;
        const bus = state.buses.find(b => b.bus_id === busId);
        
        if (!bus) return;

        // Highlight bus card in sidebar
        document.querySelectorAll(".bus-card").forEach(card => {
            if (card.dataset.busId === busId) {
                card.classList.add("active");
                card.scrollIntoView({ behavior: "smooth", block: "nearest" });
            } else {
                card.classList.remove("active");
            }
        });

        // Refresh markers to show selected state
        updateMapMarkers();

        // Open Leaflet Popup and Center Map
        if (state.busMarkers[busId]) {
            const marker = state.busMarkers[busId];
            marker.openPopup();
            if (bus.current_location) {
                elements.map.flyTo([bus.current_location.latitude, bus.current_location.longitude], 15, {
                    duration: 1.2
                });
            }
        }

        // Show Detail Drawer in Sidebar
        populateDetailDrawer(bus);
        elements.busDetailDrawer.classList.remove("hidden");
    }

    async function populateDetailDrawer(bus) {
        elements.detailBusId.textContent = bus.bus_id;
        elements.detailBusNumber.textContent = bus.bus_number;
        
        const isOnline = bus.is_online;
        elements.detailStatusIndicator.className = `status-indicator-bar ${isOnline ? "online" : "offline"}`;
        elements.detailStatusText.textContent = isOnline ? "ONLINE - LIVE SYNC" : "OFFLINE";
        
        elements.detailRouteName.textContent = bus.route_name;
        
        if (bus.current_location) {
            elements.detailSpeed.textContent = `${Math.round(bus.current_location.speed)} km/h`;
            elements.detailHeading.textContent = `${Math.round(bus.current_location.heading)}°`;
            elements.detailCoordinates.textContent = `${bus.current_location.latitude.toFixed(6)}, ${bus.current_location.longitude.toFixed(6)}`;
            elements.detailLastUpdated.textContent = formatTimeAgo(bus.current_location.updated_at);
        } else {
            elements.detailSpeed.textContent = "N/A";
            elements.detailHeading.textContent = "N/A";
            elements.detailCoordinates.textContent = "No coordinates yet";
            elements.detailLastUpdated.textContent = "Never";
        }

        elements.detailDriverName.textContent = bus.driver_name;
        elements.detailDriverPhone.textContent = bus.driver_phone;

        // Fetch available history dates for this bus to populate drawer date select
        try {
            const res = await fetch(`/api/buses/${bus.bus_id}/history?limit=1`);
            const data = await res.json();
            if (data.available_dates && elements.drawerHistoryDateSelect) {
                const currentVal = elements.drawerHistoryDateSelect.value;
                elements.drawerHistoryDateSelect.innerHTML = '<option value="all">Latest / All Available</option>';
                data.available_dates.forEach(d => {
                    const opt = document.createElement("option");
                    opt.value = d;
                    opt.textContent = `Date: ${d}`;
                    elements.drawerHistoryDateSelect.appendChild(opt);
                });
                if (data.available_dates.includes(currentVal)) {
                    elements.drawerHistoryDateSelect.value = currentVal;
                }
            }
        } catch (e) {
            console.error("Error fetching dates:", e);
        }
    }

    // Toggle Bus History Polyline Path with Date Filtering
    async function toggleHistoryPath(forceDate = null) {
        if (!state.selectedBusId) return;

        // If polyline already visible and not forcing a specific date, remove it
        if (state.historyPolyline && !forceDate) {
            clearHistoryOnMap();
            elements.toggleHistoryBtn.classList.remove("btn-primary");
            elements.toggleHistoryBtn.classList.add("btn-secondary");
            elements.toggleHistoryBtn.innerHTML = '<i class="fa-solid fa-timeline"></i> View History Path';
            return;
        }

        clearHistoryOnMap();

        try {
            const chosenDate = forceDate || elements.drawerHistoryDateSelect.value;
            const queryParam = (chosenDate && chosenDate !== "all") ? `&date=${chosenDate}` : "";
            const response = await fetch(`/api/buses/${state.selectedBusId}/history?limit=500${queryParam}`);
            const data = await response.json();

            if (!data.history || data.history.length === 0) {
                alert(`No historical location pings available for ${state.selectedBusId} on ${chosenDate}`);
                return;
            }

            const latLngs = data.history.map(h => [h.latitude, h.longitude]);

            // Draw glowing polyline
            state.historyPolyline = L.polyline(latLngs, {
                color: '#00d2ff',
                weight: 4,
                opacity: 0.85,
                dashArray: '6, 6'
            }).addTo(elements.map);

            // Add waypoint circles along the route
            data.history.forEach((h, idx) => {
                const isFirst = (idx === 0);
                const isLast = (idx === data.history.length - 1);
                const markerColor = isLast ? '#10b981' : isFirst ? '#f59e0b' : '#00d2ff';

                const waypoint = L.circleMarker([h.latitude, h.longitude], {
                    radius: isFirst || isLast ? 6 : 4,
                    fillColor: markerColor,
                    color: '#fff',
                    weight: 1.5,
                    opacity: 1,
                    fillOpacity: 0.9
                });

                const popupHtml = `
                    <div class="popup-content">
                        <div class="popup-header">
                            <span class="popup-title">${h.bus_no || h.bus_id} Point #${idx + 1}</span>
                        </div>
                        <div class="popup-info-line"><i class="fa-solid fa-calendar"></i> Date: <strong>${h.date || 'N/A'}</strong></div>
                        <div class="popup-info-line"><i class="fa-solid fa-clock"></i> Time: <strong>${h.time || 'N/A'}</strong></div>
                        <div class="popup-info-line"><i class="fa-solid fa-location-dot"></i> Lat, Lng: <strong>${h.latitude.toFixed(6)}, ${h.longitude.toFixed(6)}</strong></div>
                        <div class="popup-info-line"><i class="fa-solid fa-gauge-high"></i> Speed: <strong>${Math.round(h.speed)} km/h</strong></div>
                    </div>
                `;
                waypoint.bindPopup(popupHtml);
                waypoint.addTo(elements.map);
                state.historyMarkers.push(waypoint);
            });

            elements.map.fitBounds(state.historyPolyline.getBounds(), { padding: [50, 50] });

            elements.toggleHistoryBtn.classList.remove("btn-secondary");
            elements.toggleHistoryBtn.classList.add("btn-primary");
            elements.toggleHistoryBtn.innerHTML = '<i class="fa-solid fa-xmark"></i> Hide History Path';

        } catch (error) {
            console.error("Error fetching bus history:", error);
        }
    }

    function clearHistoryOnMap() {
        if (state.historyPolyline) {
            elements.map.removeLayer(state.historyPolyline);
            state.historyPolyline = null;
        }
        state.historyMarkers.forEach(m => elements.map.removeLayer(m));
        state.historyMarkers = [];
    }

    function populateAdminBusSelect() {
        if (!elements.adminHistoryBusSelect) return;
        const currentVal = elements.adminHistoryBusSelect.value;
        elements.adminHistoryBusSelect.innerHTML = '<option value="">Select Bus Number...</option>';
        state.buses.forEach(b => {
            const opt = document.createElement("option");
            opt.value = b.bus_id;
            opt.textContent = `${b.bus_id} - ${b.bus_number} (${b.route_name})`;
            elements.adminHistoryBusSelect.appendChild(opt);
        });
        if (currentVal) elements.adminHistoryBusSelect.value = currentVal;
    }

    // ==========================================
    // 4. AUTO-REFRESH & TIMERS
    // ==========================================
    function startAutoRefreshLoop() {
        fetchBuses();

        state.timerId = setInterval(() => {
            state.countdownRemaining--;
            if (state.countdownRemaining <= 0) {
                state.countdownRemaining = state.autoRefreshInterval;
                fetchBuses();
            }
            elements.nextRefreshCountdown.textContent = `${state.countdownRemaining}s`;
        }, 1000);
    }

    // ==========================================
    // 5. EVENT LISTENERS
    // ==========================================
    function setupEventListeners() {
        // Mobile Sidebar Controls
        elements.openSidebarBtn.addEventListener("click", () => {
            elements.sidebar.classList.add("open");
        });

        elements.closeSidebarBtn.addEventListener("click", () => {
            elements.sidebar.classList.remove("open");
        });

        // Search Input
        elements.busSearchInput.addEventListener("input", (e) => {
            state.activeFilters.search = e.target.value.trim();
            elements.clearSearchBtn.classList.toggle("hidden", !state.activeFilters.search);
            fetchBuses();
        });

        elements.clearSearchBtn.addEventListener("click", () => {
            elements.busSearchInput.value = "";
            state.activeFilters.search = "";
            elements.clearSearchBtn.classList.add("hidden");
            fetchBuses();
        });

        // Dropdown Filters
        elements.routeFilterSelect.addEventListener("change", (e) => {
            state.activeFilters.route = e.target.value;
            fetchBuses();
        });

        elements.statusFilterSelect.addEventListener("change", (e) => {
            state.activeFilters.status = e.target.value;
            fetchBuses();
        });

        // Quick Stats Filters
        elements.filterStatTotal.addEventListener("click", () => {
            elements.statusFilterSelect.value = "all";
            state.activeFilters.status = "all";
            fetchBuses();
        });

        elements.filterStatOnline.addEventListener("click", () => {
            elements.statusFilterSelect.value = "online";
            state.activeFilters.status = "online";
            fetchBuses();
        });

        elements.filterStatOffline.addEventListener("click", () => {
            elements.statusFilterSelect.value = "offline";
            state.activeFilters.status = "offline";
            fetchBuses();
        });

        // Drawer buttons
        elements.closeDrawerBtn.addEventListener("click", () => {
            elements.busDetailDrawer.classList.add("hidden");
            state.selectedBusId = null;
            clearHistoryOnMap();
            elements.toggleHistoryBtn.classList.remove("btn-primary");
            elements.toggleHistoryBtn.classList.add("btn-secondary");
            elements.toggleHistoryBtn.innerHTML = '<i class="fa-solid fa-timeline"></i> View History Path';
            updateMapMarkers();
            renderBusCardsList();
        });

        elements.centerMapBtn.addEventListener("click", () => {
            if (state.selectedBusId && state.busMarkers[state.selectedBusId]) {
                const marker = state.busMarkers[state.selectedBusId];
                elements.map.flyTo(marker.getLatLng(), 16);
            }
        });

        elements.toggleHistoryBtn.addEventListener("click", () => toggleHistoryPath());
        
        if (elements.drawerHistoryDateSelect) {
            elements.drawerHistoryDateSelect.addEventListener("change", () => {
                if (state.historyPolyline) {
                    toggleHistoryPath(elements.drawerHistoryDateSelect.value);
                }
            });
        }

        // Fit All Markers Button
        elements.mapFitBoundsBtn.addEventListener("click", () => {
            const markerGroup = L.featureGroup(Object.values(state.busMarkers));
            if (markerGroup.getLayers().length > 0) {
                elements.map.fitBounds(markerGroup.getBounds(), { padding: [50, 50] });
            }
        });

        // Manual Refresh Click
        elements.manualRefreshIcon.parentElement.addEventListener("click", () => {
            state.countdownRemaining = state.autoRefreshInterval;
            elements.nextRefreshCountdown.textContent = `${state.countdownRemaining}s`;
            fetchBuses();
        });

        // Admin Modal Controls
        elements.openAdminBtn.addEventListener("click", () => {
            elements.adminModal.classList.remove("hidden");
            populateAdminBusSelect();
            if (elements.adminHistoryDateInput && !elements.adminHistoryDateInput.value) {
                elements.adminHistoryDateInput.value = new Date().toISOString().split('T')[0];
            }
        });

        elements.closeAdminModalBtn.addEventListener("click", () => {
            elements.adminModal.classList.add("hidden");
        });

        // Admin Tabs Switching
        if (elements.tabHistoryAuditBtn && elements.tabAddBusBtn) {
            elements.tabHistoryAuditBtn.addEventListener("click", () => {
                elements.tabHistoryAuditBtn.classList.add("active");
                elements.tabAddBusBtn.classList.remove("active");
                elements.adminHistorySection.classList.remove("hidden");
                elements.adminAddBusSection.classList.add("hidden");
                populateAdminBusSelect();
            });

            elements.tabAddBusBtn.addEventListener("click", () => {
                elements.tabAddBusBtn.classList.add("active");
                elements.tabHistoryAuditBtn.classList.remove("active");
                elements.adminAddBusSection.classList.remove("hidden");
                elements.adminHistorySection.classList.add("hidden");
            });
        }

        // Admin History "View Locations" Action
        if (elements.adminViewLocationsBtn) {
            elements.adminViewLocationsBtn.addEventListener("click", async () => {
                const busId = elements.adminHistoryBusSelect.value;
                const chosenDate = elements.adminHistoryDateInput.value;

                if (!busId) {
                    alert("Please select a Bus Number first");
                    return;
                }

                try {
                    const dateQuery = chosenDate ? `&date=${chosenDate}` : "";
                    const res = await fetch(`/api/buses/${busId}/history?limit=500${dateQuery}`);
                    const data = await res.json();

                    if (!data.history || data.history.length === 0) {
                        elements.adminHistoryTableBody.innerHTML = `<tr><td colspan="7" style="text-align:center;color:var(--text-muted);padding:16px;">No location records found for ${busId} on ${chosenDate || 'selected date'}.</td></tr>`;
                        elements.adminHistoryCountBadge.textContent = "0 Locations Found";
                        elements.adminHistoryResults.classList.remove("hidden");
                        return;
                    }

                    elements.adminHistoryCountBadge.textContent = `${data.history.length} Locations Recorded`;
                    elements.adminHistoryTableBody.innerHTML = "";

                    data.history.forEach((h, idx) => {
                        const tr = document.createElement("tr");
                        tr.innerHTML = `
                            <td>${idx + 1}</td>
                            <td><strong style="color:var(--accent);">${h.time || 'N/A'}</strong></td>
                            <td>${h.date || 'N/A'}</td>
                            <td>${h.latitude.toFixed(6)}</td>
                            <td>${h.longitude.toFixed(6)}</td>
                            <td>${Math.round(h.speed)} km/h</td>
                            <td>${Math.round(h.heading)}°</td>
                        `;
                        elements.adminHistoryTableBody.appendChild(tr);
                    });

                    elements.adminHistoryResults.classList.remove("hidden");

                } catch (e) {
                    console.error("Error loading history:", e);
                    alert("Failed to retrieve location history for bus");
                }
            });
        }

        // Admin "Show on Map" button
        if (elements.adminShowOnMapBtn) {
            elements.adminShowOnMapBtn.addEventListener("click", () => {
                const busId = elements.adminHistoryBusSelect.value;
                const chosenDate = elements.adminHistoryDateInput.value;
                if (!busId) return;

                // Close admin modal
                elements.adminModal.classList.add("hidden");

                // Select bus and trigger history on map
                selectBus(busId);
                setTimeout(() => {
                    toggleHistoryPath(chosenDate);
                }, 300);
            });
        }

        // Admin Login Form
        elements.adminLoginForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            const username = elements.adminUsernameInput.value.trim();
            const password = elements.adminPasswordInput.value.trim();

            try {
                const response = await fetch("/api/admin/login", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ username, password })
                });

                const data = await response.json();
                if (response.ok && data.status === "success") {
                    state.isAdmin = true;
                    elements.adminLoginForm.reset();
                    elements.adminLoginError.classList.add("hidden");
                    elements.adminLoginView.classList.add("hidden");
                    elements.adminDashboardView.classList.remove("hidden");
                    populateAdminBusSelect();
                } else {
                    elements.adminLoginError.textContent = data.message || "Invalid credentials";
                    elements.adminLoginError.classList.remove("hidden");
                }
            } catch (err) {
                elements.adminLoginError.textContent = "Network error while signing in";
                elements.adminLoginError.classList.remove("hidden");
            }
        });

        // Admin Logout
        elements.adminLogoutBtn.addEventListener("click", async () => {
            await fetch("/api/admin/logout", { method: "POST" });
            state.isAdmin = false;
            elements.adminDashboardView.classList.add("hidden");
            elements.adminLoginView.classList.remove("hidden");
        });

        // Add New Bus Form
        elements.addBusForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            const newBus = {
                bus_id: document.getElementById("newBusId").value.trim().toUpperCase(),
                bus_number: document.getElementById("newBusNumber").value.trim(),
                route_name: document.getElementById("newRouteName").value.trim(),
                driver_name: document.getElementById("newDriverName").value.trim(),
                driver_phone: document.getElementById("newDriverPhone").value.trim(),
                capacity: parseInt(document.getElementById("newCapacity").value, 10)
            };

            try {
                const response = await fetch("/api/admin/buses", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(newBus)
                });
                const data = await response.json();

                if (response.ok && data.status === "success") {
                    elements.addBusForm.reset();
                    elements.adminFormMsg.textContent = `Bus ${newBus.bus_id} registered successfully!`;
                    elements.adminFormMsg.classList.remove("hidden");
                    setTimeout(() => elements.adminFormMsg.classList.add("hidden"), 3000);
                    fetchBuses();
                } else {
                    alert(data.message || "Error adding bus");
                }
            } catch (err) {
                alert("Failed to create new bus");
            }
        });
    }

    // Utility: Format ISO Timestamp to Relative Time Ago
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

    // App Initialization
    initMap();
    setupEventListeners();
    startAutoRefreshLoop();
});
