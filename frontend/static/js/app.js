/**
 * SmartBus Live Fleet Tracking System - Client Application JavaScript
 * Full-Stack 10-Section Navigation, Live GPS, 300 MB Storage Optimization & 7-Day History
 */

document.addEventListener("DOMContentLoaded", () => {
    // ==========================================
    // 1. APPLICATION STATE
    // ==========================================
    const state = {
        currentView: "dashboard",
        buses: [],
        selectedBusId: null,
        busMarkers: {},
        routePolyline: null,
        stopsMarkersGroup: null,
        collegeCircle: null,
        activeFilter: "all",
        fleetFilter: "all",
        searchQuery: "",
        fleetSearchQuery: "",

        autoRefreshInterval: 5,
        timerId: null,

        // 7-Day History & Replay State
        viewMode: "live",
        selectedDate: null,
        availableDates: [],
        historyRecords: [],
        historyLayers: [],
        historyPolyline: null,
        replay: {
            index: 0,
            isPlaying: false,
            speedMultiplier: 1,
            timer: null,
            marker: null
        },

        // Devices, Routes, Trips, Storage, Auth
        devices: [],
        routes: [],
        collegeConfig: null,
        storageMetrics: null,
        currentUser: null,
        trips: [],
        selectedTripBusId: null
    };

    // ==========================================
    // 2. DOM ELEMENTS CACHE
    // ==========================================
    const elements = {
        map: null,

        // Header
        headerCollegeName: document.getElementById("headerCollegeName"),
        headerActiveBusCount: document.getElementById("headerActiveBusCount"),
        headerTotalBusCount: document.getElementById("headerTotalBusCount"),
        headerStoragePill: document.getElementById("headerStoragePill"),
        headerStorageText: document.getElementById("headerStorageText"),
        headerStorageDot: document.getElementById("headerStorageDot"),
        syncStatusLabel: document.getElementById("syncStatusLabel"),
        userSessionBadge: document.getElementById("userSessionBadge"),
        sessionUsername: document.getElementById("sessionUsername"),
        sessionRoleTag: document.getElementById("sessionRoleTag"),
        headerAuthBtn: document.getElementById("headerAuthBtn"),
        authBtnLabel: document.getElementById("authBtnLabel"),
        brandLogoHome: document.getElementById("brandLogoHome"),

        // Navigation
        navButtons: document.querySelectorAll(".nav-link-btn"),
        navBusesCount: document.getElementById("navBusesCount"),
        views: document.querySelectorAll(".app-view"),

        // View 1: Dashboard
        dashTotalBuses: document.getElementById("dashTotalBuses"),
        dashActiveBuses: document.getElementById("dashActiveBuses"),
        dashSendingGps: document.getElementById("dashSendingGps"),
        dashRunningBuses: document.getElementById("dashRunningBuses"),
        dashReachedCollege: document.getElementById("dashReachedCollege"),
        dashOfflineDevices: document.getElementById("dashOfflineDevices"),
        dashTotalRoutes: document.getElementById("dashTotalRoutes"),
        dashCompletedTrips: document.getElementById("dashCompletedTrips"),
        dashFleetDistance: document.getElementById("dashFleetDistance"),
        dashStorageWarningBadge: document.getElementById("dashStorageWarningBadge"),
        dashStorageStatusText: document.getElementById("dashStorageStatusText"),
        dashStorageProgressFill: document.getElementById("dashStorageProgressFill"),
        dashStorageUsed: document.getElementById("dashStorageUsed"),
        dashStorageAvailable: document.getElementById("dashStorageAvailable"),
        dashStoragePercent: document.getElementById("dashStoragePercent"),
        dashFleetTableBody: document.getElementById("dashFleetTableBody"),
        btnDashboardToMap: document.getElementById("btnDashboardToMap"),
        btnViewAllBuses: document.getElementById("btnViewAllBuses"),

        // View 2: Live Tracking
        busSelectorPanel: document.getElementById("busSelectorPanel"),
        liveMapPanel: document.getElementById("liveMapPanel"),
        busSearchInput: document.getElementById("busSearchInput"),
        clearSearchBtn: document.getElementById("clearSearchBtn"),
        statusTabBtns: document.querySelectorAll(".status-tab-btn[data-filter]"),
        busesListContainer: document.getElementById("busesListContainer"),
        countAllBuses: document.getElementById("countAllBuses"),
        countRunningBuses: document.getElementById("countRunningBuses"),
        countReachedCollegeBuses: document.getElementById("countReachedCollegeBuses"),
        countOfflineBuses: document.getElementById("countOfflineBuses"),
        footerTotalCount: document.getElementById("footerTotalCount"),
        mobileBusCount: document.getElementById("mobileBusCount"),
        mobileTabBusesBtn: document.getElementById("mobileTabBusesBtn"),
        mobileTabMapBtn: document.getElementById("mobileTabMapBtn"),

        // HUD Elements
        telemetryHudCard: document.getElementById("telemetryHudCard"),
        hudBusName: document.getElementById("hudBusName"),
        hudBusNumber: document.getElementById("hudBusNumber"),
        hudEspVal: document.getElementById("hudEspVal"),
        hudConnectionBadge: document.getElementById("hudConnectionBadge"),
        btnModeLive: document.getElementById("btnModeLive"),
        btnModeHistory: document.getElementById("btnModeHistory"),
        liveTelemetrySection: document.getElementById("liveTelemetrySection"),
        historyTelemetrySection: document.getElementById("historyTelemetrySection"),
        hudCoordsVal: document.getElementById("hudCoordsVal"),
        hudCopyCoordsBtn: document.getElementById("hudCopyCoordsBtn"),
        hudGoogleMapsLink: document.getElementById("hudGoogleMapsLink"),
        hudSpeedVal: document.getElementById("hudSpeedVal"),
        hudHeadingVal: document.getElementById("hudHeadingVal"),
        hudSatsVal: document.getElementById("hudSatsVal"),
        hudUpdatedVal: document.getElementById("hudUpdatedVal"),
        hudRouteVal: document.getElementById("hudRouteVal"),
        hudTripDistVal: document.getElementById("hudTripDistVal"),
        hudTripStatusSub: document.getElementById("hudTripStatusSub"),
        hudDailyDistVal: document.getElementById("hudDailyDistVal"),
        hudRemainingDistVal: document.getElementById("hudRemainingDistVal"),
        hud7DayDistVal: document.getElementById("hud7DayDistVal"),

        // Replay Controls
        sevenDayNavPills: document.getElementById("sevenDayNavPills"),
        histDistVal: document.getElementById("histDistVal"),
        histMaxSpeedVal: document.getElementById("histMaxSpeedVal"),
        histStopsVal: document.getElementById("histStopsVal"),
        histPointsVal: document.getElementById("histPointsVal"),
        replayPlayPauseBtn: document.getElementById("replayPlayPauseBtn"),
        replayResetBtn: document.getElementById("replayResetBtn"),
        replayScrubber: document.getElementById("replayScrubber"),
        replayCurrentTime: document.getElementById("replayCurrentTime"),
        replayCurrentSpeed: document.getElementById("replayCurrentSpeed"),
        replayWaypointProgress: document.getElementById("replayWaypointProgress"),
        speedOptBtns: document.querySelectorAll(".speed-opt-btn"),
        centerSelectedBusBtn: document.getElementById("centerSelectedBusBtn"),
        fitAllBusesBtn: document.getElementById("fitAllBusesBtn"),

        // View 3: Buses
        fleetSearchInput: document.getElementById("fleetSearchInput"),
        fleetCountAll: document.getElementById("fleetCountAll"),
        fleetCountRunning: document.getElementById("fleetCountRunning"),
        fleetCountCollege: document.getElementById("fleetCountCollege"),
        fleetCountOffline: document.getElementById("fleetCountOffline"),
        fleetTableBody: document.getElementById("fleetTableBody"),
        btnFleetRegisterBus: document.getElementById("btnFleetRegisterBus"),

        // View 4: Register Bus
        dedicatedRegisterBusForm: document.getElementById("dedicatedRegisterBusForm"),
        regBusName: document.getElementById("regBusName"),
        regBusId: document.getElementById("regBusId"),
        regBusNumber: document.getElementById("regBusNumber"),
        regDeviceId: document.getElementById("regDeviceId"),
        regDriverName: document.getElementById("regDriverName"),
        regDriverPhone: document.getElementById("regDriverPhone"),
        regRouteSelect: document.getElementById("regRouteSelect"),
        regCollegeDest: document.getElementById("regCollegeDest"),

        // View 5: Routes
        btnToggleCreateRoute: document.getElementById("btnToggleCreateRoute"),
        routeCreateCard: document.getElementById("routeCreateCard"),
        routeForm: document.getElementById("routeForm"),
        routeNameInput: document.getElementById("routeNameInput"),
        routeCodeInput: document.getElementById("routeCodeInput"),
        routeOriginInput: document.getElementById("routeOriginInput"),
        btnGeocodeOrigin: document.getElementById("btnGeocodeOrigin"),
        originSuggestionsBox: document.getElementById("originSuggestionsBox"),
        originConfirmedPill: document.getElementById("originConfirmedPill"),
        originCoordsText: document.getElementById("originCoordsText"),
        routeStopSearchInput: document.getElementById("routeStopSearchInput"),
        btnAddStopSearch: document.getElementById("btnAddStopSearch"),
        stopSuggestionsBox: document.getElementById("stopSuggestionsBox"),
        selectedStopsList: document.getElementById("selectedStopsList"),
        btnCancelRouteForm: document.getElementById("btnCancelRouteForm"),
        routesCardsGrid: document.getElementById("routesCardsGrid"),

        // View 6: Trip History
        tripHistoryBusSelect: document.getElementById("tripHistoryBusSelect"),
        tripHistoryDateSelect: document.getElementById("tripHistoryDateSelect"),
        tripViewDist: document.getElementById("tripViewDist"),
        tripViewStatus: document.getElementById("tripViewStatus"),
        dailyViewDist: document.getElementById("dailyViewDist"),
        sevenDayViewDist: document.getElementById("sevenDayViewDist"),
        tripCountBadge: document.getElementById("tripCountBadge"),
        tripsTableBody: document.getElementById("tripsTableBody"),

        // View 7: College Settings
        collegeConfigForm: document.getElementById("collegeConfigForm"),
        collegeNameInput: document.getElementById("collegeNameInput"),
        collegeRadiusInput: document.getElementById("collegeRadiusInput"),
        collegeLatInput: document.getElementById("collegeLatInput"),
        collegeLngInput: document.getElementById("collegeLngInput"),
        lblCollegeRadius: document.getElementById("lblCollegeRadius"),
        lblCollegeCoords: document.getElementById("lblCollegeCoords"),

        // View 8: Devices
        devTotalCount: document.getElementById("devTotalCount"),
        devOnlineCount: document.getElementById("devOnlineCount"),
        devGpsCount: document.getElementById("devGpsCount"),
        devUnassignedCount: document.getElementById("devUnassignedCount"),
        devUnassignedBanner: document.getElementById("devUnassignedBanner"),
        devicesTableViewBody: document.getElementById("devicesTableViewBody"),

        // View 9: Storage
        btnTriggerStorageCleanup: document.getElementById("btnTriggerStorageCleanup"),
        storageHeroUsageText: document.getElementById("storageHeroUsageText"),
        storageHeroBadge: document.getElementById("storageHeroBadge"),
        storageHeroProgressFill: document.getElementById("storageHeroProgressFill"),
        storageCatDb: document.getElementById("storageCatDb"),
        storageCatTracking: document.getElementById("storageCatTracking"),
        storageCatTrips: document.getElementById("storageCatTrips"),
        storageCatBackups: document.getElementById("storageCatBackups"),
        storageCatSecurity: document.getElementById("storageCatSecurity"),
        storageFilesTableBody: document.getElementById("storageFilesTableBody"),

        // View 10: Security
        secCurrentUsername: document.getElementById("secCurrentUsername"),
        secCurrentRole: document.getElementById("secCurrentRole"),
        changePasswordForm: document.getElementById("changePasswordForm"),
        oldPassInput: document.getElementById("oldPassInput"),
        newPassInput: document.getElementById("newPassInput"),
        secUsersTableBody: document.getElementById("secUsersTableBody"),
        createNewUserForm: document.getElementById("createNewUserForm"),
        newUserNameInput: document.getElementById("newUserNameInput"),
        newUserRoleSelect: document.getElementById("newUserRoleSelect"),
        newUserPasswordInput: document.getElementById("newUserPasswordInput"),
        secAuditLogsTableBody: document.getElementById("secAuditLogsTableBody"),

        // Auth Modal
        authLoginModal: document.getElementById("authLoginModal"),
        authLoginForm: document.getElementById("authLoginForm"),
        loginUsername: document.getElementById("loginUsername"),
        loginPassword: document.getElementById("loginPassword"),
        closeAuthModalBtn: document.getElementById("closeAuthModalBtn"),

        // Toast Container
        toastContainer: document.getElementById("toastContainer")
    };

    // Temporary storage for intermediate stops during route creation
    let currentNewRouteStops = [];
    let confirmedOriginCoords = null;

    // ==========================================
    // 3. MAP INITIALIZATION (Leaflet)
    // ==========================================
    function initMap() {
        const defaultCenter = [17.3450, 78.5300];
        const defaultZoom = 12;

        elements.map = L.map("map", {
            zoomControl: false,
            attributionControl: false
        }).setView(defaultCenter, defaultZoom);

        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
            maxZoom: 19
        }).addTo(elements.map);

        L.control.zoom({ position: "topright" }).addTo(elements.map);
        elements.stopsMarkersGroup = L.layerGroup().addTo(elements.map);

        elements.map.on("click", (e) => {
            if (state.currentView === "college-settings") {
                const lat = roundCoord(e.latlng.lat);
                const lng = roundCoord(e.latlng.lng);
                elements.collegeLatInput.value = lat;
                elements.collegeLngInput.value = lng;
                updateCollegeCircle(lat, lng, parseInt(elements.collegeRadiusInput.value || 120));
                showToast(`College coordinates selected: ${lat}, ${lng}`, "info");
            }
        });
    }

    function updateCollegeCircle(lat, lng, radiusMeters) {
        if (!elements.map) return;
        if (elements.collegeCircle) {
            elements.map.removeLayer(elements.collegeCircle);
        }

        elements.collegeCircle = L.circle([lat, lng], {
            radius: radiusMeters,
            color: "#2563eb",
            fillColor: "#3b82f6",
            fillOpacity: 0.18,
            weight: 2,
            dashArray: "4, 4"
        }).addTo(elements.map);

        const collegeIcon = L.divIcon({
            className: "college-terminal-marker",
            html: `<div style="background:#1e40af; color:#fff; width:34px; height:34px; border-radius:50%; display:flex; align-items:center; justify-content:center; box-shadow:0 3px 8px rgba(0,0,0,0.3); border:2px solid #fff;"><i class="fa-solid fa-graduation-cap"></i></div>`,
            iconSize: [34, 34],
            iconAnchor: [17, 17]
        });

        L.marker([lat, lng], { icon: collegeIcon })
            .bindTooltip(`<strong>${state.collegeConfig ? state.collegeConfig.college_name : "College Terminal"}</strong><br>Arrival Geofence: ${radiusMeters}m`, { direction: "top" })
            .addTo(elements.map);
    }

    // ==========================================
    // 4. VIEW SWITCHING LOGIC (10 Sections)
    // ==========================================
    function switchView(viewName) {
        state.currentView = viewName;

        elements.navButtons.forEach(btn => {
            if (btn.dataset.view === viewName) {
                btn.classList.add("active");
            } else {
                btn.classList.remove("active");
            }
        });

        elements.views.forEach(view => {
            if (view.id === getViewId(viewName)) {
                view.classList.add("active");
            } else {
                view.classList.remove("active");
            }
        });

        // Specific view activations
        if (viewName === "live-tracking") {
            setTimeout(() => {
                if (elements.map) {
                    elements.map.invalidateSize();
                    if (state.selectedBusId) {
                        centerBus(state.selectedBusId);
                    } else if (state.buses.length > 0) {
                        selectBus(state.buses[0].bus_id, false);
                    }
                }
            }, 100);
        } else if (viewName === "dashboard") {
            fetchDashboard();
        } else if (viewName === "buses") {
            renderFleetTable();
        } else if (viewName === "routes") {
            fetchRoutes();
        } else if (viewName === "trip-history") {
            loadTripHistoryView();
        } else if (viewName === "college-settings") {
            loadCollegeSettingsView();
        } else if (viewName === "devices") {
            fetchDevices();
        } else if (viewName === "storage") {
            fetchStorageMetrics();
        } else if (viewName === "security") {
            fetchSecurityData();
        }
    }

    function getViewId(viewName) {
        switch (viewName) {
            case "dashboard": return "viewDashboard";
            case "live-tracking": return "viewLiveTracking";
            case "buses": return "viewBuses";
            case "register-bus": return "viewRegisterBus";
            case "routes": return "viewRouteManagement";
            case "trip-history": return "viewTripHistory";
            case "college-settings": return "viewCollegeSettings";
            case "devices": return "viewDevices";
            case "storage": return "viewStorage";
            case "security": return "viewSecurity";
            default: return "viewDashboard";
        }
    }

    // ==========================================
    // 5. DATA FETCHING (AUTOMATIC GPS SYNC)
    // ==========================================
    async function fetchBuses() {
        try {
            const resp = await fetch("/api/buses");
            if (!resp.ok) throw new Error("Failed to fetch buses");
            const data = await resp.json();

            state.buses = data.buses || [];
            updateHeaderMetrics(data.metrics || {});
            renderBusesList();
            updateMapMarkers();

            if (state.currentView === "dashboard") {
                renderDashboardMetrics(data.metrics || {});
                renderDashFleetTable();
            } else if (state.currentView === "buses") {
                renderFleetTable();
            }

            // If a bus is selected, update HUD telemetry and distance metrics
            if (state.selectedBusId) {
                const bus = state.buses.find(b => b.bus_id === state.selectedBusId);
                if (bus) updateTelemetryHud(bus);
            } else if (state.buses.length > 0 && !state.selectedBusId) {
                selectBus(state.buses[0].bus_id, false);
            }
        } catch (err) {
            console.warn("GPS sync fetch error:", err);
            elements.syncStatusLabel.textContent = "Reconnecting...";
        }
    }

    async function fetchDashboard() {
        try {
            const resp = await fetch("/api/admin/dashboard");
            if (!resp.ok) return;
            const data = await resp.json();
            const dash = data.dashboard || {};
            renderDashboardMetrics(dash);
            renderDashStorageCard(dash.storage || {});
        } catch (err) {
            console.error("Dashboard fetch error:", err);
        }
    }

    async function fetchCollegeConfig() {
        try {
            const resp = await fetch("/api/college");
            if (!resp.ok) return;
            const data = await resp.json();
            state.collegeConfig = data.college || {};

            elements.headerCollegeName.textContent = (state.collegeConfig.college_name || "Sphoorthy Engineering College").toUpperCase();
            elements.selectorCollegeTitle.textContent = (state.collegeConfig.college_name || "Sphoorthy Fleet").split(",")[0];

            if (elements.collegeNameInput) elements.collegeNameInput.value = state.collegeConfig.college_name || "";
            if (elements.collegeLatInput) elements.collegeLatInput.value = state.collegeConfig.college_latitude || 17.3156;
            if (elements.collegeLngInput) elements.collegeLngInput.value = state.collegeConfig.college_longitude || 78.5833;
            if (elements.collegeRadiusInput) elements.collegeRadiusInput.value = state.collegeConfig.college_geofence_radius_meters || 120;

            if (elements.lblCollegeRadius) elements.lblCollegeRadius.textContent = state.collegeConfig.college_geofence_radius_meters || 120;
            if (elements.lblCollegeCoords) elements.lblCollegeCoords.textContent = `${state.collegeConfig.college_latitude}, ${state.collegeConfig.college_longitude}`;

            updateCollegeCircle(
                state.collegeConfig.college_latitude || 17.3156,
                state.collegeConfig.college_longitude || 78.5833,
                state.collegeConfig.college_geofence_radius_meters || 120
            );
        } catch (err) {
            console.error("College config fetch error:", err);
        }
    }

    async function fetchStorageMetrics() {
        try {
            const resp = await fetch("/api/admin/storage");
            if (!resp.ok) return;
            const data = await resp.json();
            state.storageMetrics = data.storage || {};
            renderStorageView(state.storageMetrics);
            renderHeaderStorage(state.storageMetrics);
        } catch (err) {
            console.error("Storage fetch error:", err);
        }
    }

    async function fetchRoutes() {
        try {
            const resp = await fetch("/api/routes");
            if (!resp.ok) return;
            const data = await resp.json();
            state.routes = data.routes || [];
            renderRoutesGrid(state.routes);
            populateRouteDropdowns(state.routes);
        } catch (err) {
            console.error("Routes fetch error:", err);
        }
    }

    async function fetchDevices() {
        try {
            const resp = await fetch("/api/devices");
            if (!resp.ok) return;
            const data = await resp.json();
            state.devices = data.devices || [];
            renderDevicesView(data);
        } catch (err) {
            console.error("Devices fetch error:", err);
        }
    }

    async function checkAuthSession() {
        try {
            const resp = await fetch("/api/auth/session");
            if (!resp.ok) return;
            const data = await resp.json();
            state.currentUser = data.user || null;
            updateUserSessionDisplay();
        } catch (err) {
            console.warn("Auth session check error:", err);
        }
    }

    // ==========================================
    // 6. DASHBOARD & FLEET RENDERING
    // ==========================================
    function updateHeaderMetrics(m) {
        const total = m.total_buses || state.buses.length || 30;
        const active = m.active_buses || 0;
        elements.headerActiveBusCount.textContent = active;
        elements.headerTotalBusCount.textContent = total;
        elements.navBusesCount.textContent = total;
        elements.countAllBuses.textContent = total;
        elements.footerTotalCount.textContent = total;
        elements.mobileBusCount.textContent = total;
        if (elements.fleetCountAll) elements.fleetCountAll.textContent = total;

        const running = m.running_buses || 0;
        const reached = m.reached_college_buses || 0;
        const offline = m.offline_buses || (total - active);

        elements.countRunningBuses.textContent = running;
        elements.countReachedCollegeBuses.textContent = reached;
        elements.countOfflineBuses.textContent = offline;

        if (elements.fleetCountRunning) elements.fleetCountRunning.textContent = running;
        if (elements.fleetCountCollege) elements.fleetCountCollege.textContent = reached;
        if (elements.fleetCountOffline) elements.fleetCountOffline.textContent = offline;
    }

    function renderDashboardMetrics(m) {
        if (!elements.dashTotalBuses) return;
        const total = m.total_buses || state.buses.length || 30;
        elements.dashTotalBuses.textContent = total;
        elements.dashActiveBuses.textContent = m.active_buses || 0;
        elements.dashSendingGps.textContent = m.sending_gps_buses || m.active_buses || 0;
        elements.dashRunningBuses.textContent = m.running_buses || 0;
        elements.dashReachedCollege.textContent = m.reached_college_buses || 0;
        elements.dashOfflineDevices.textContent = m.offline_devices || 0;
        elements.dashTotalRoutes.textContent = m.total_routes || (state.routes.length || 3);
        elements.dashCompletedTrips.textContent = m.completed_trips_today || 0;
        elements.dashFleetDistance.textContent = `${(m.total_distance_today_km || 0).toFixed(1)} km`;
    }

    function renderDashStorageCard(storage) {
        if (!elements.dashStorageUsed || !storage) return;
        const usedMb = storage.total_used_mb || 0.5;
        const availMb = storage.available_mb || 299.5;
        const pct = storage.percent_used || 0.17;
        const warning = storage.warning_level || "NORMAL";

        elements.dashStorageUsed.textContent = `${usedMb.toFixed(2)} MB`;
        elements.dashStorageAvailable.textContent = `${availMb.toFixed(2)} MB`;
        elements.dashStoragePercent.textContent = `${pct.toFixed(2)}%`;

        const fillEl = elements.dashStorageProgressFill;
        fillEl.style.width = `${Math.max(1, Math.min(100, pct))}%`;
        fillEl.className = `storage-progress-fill ${warning.toLowerCase()}`;

        const badgeEl = elements.dashStorageWarningBadge;
        badgeEl.className = `storage-status-pill ${warning.toLowerCase()}`;
        if (warning === "NORMAL") {
            elements.dashStorageStatusText.textContent = "Storage Normal (<70%)";
        } else if (warning === "WARNING_70") {
            elements.dashStorageStatusText.textContent = "Storage Warning (>=70%)";
        } else if (warning === "WARNING_85") {
            elements.dashStorageStatusText.textContent = "Storage Alert (>=85%)";
        } else if (warning === "CRITICAL_95") {
            elements.dashStorageStatusText.textContent = "Critical Limit (>=95%)";
        }
    }

    function renderHeaderStorage(storage) {
        if (!elements.headerStorageText || !storage) return;
        const used = storage.total_used_mb || 0.5;
        const warning = (storage.warning_level || "NORMAL").toLowerCase();
        elements.headerStorageText.textContent = `${used.toFixed(1)} / 300 MB`;
        elements.headerStorageDot.className = `storage-badge-dot ${warning.includes("crit") ? "critical" : (warning.includes("warn") ? "warning" : "normal")}`;
    }

    function renderDashFleetTable() {
        if (!elements.dashFleetTableBody) return;
        const busesSlice = state.buses.slice(0, 8);
        elements.dashFleetTableBody.innerHTML = busesSlice.map(b => {
            const statusClass = b.is_reached_college ? "reached_college" : (b.is_moving ? "moving" : (b.is_online ? "stopped" : "offline"));
            const statusLabel = b.is_reached_college ? "Reached College" : (b.is_moving ? "Moving" : (b.is_online ? "Stopped" : "Offline"));
            const distMetrics = b.distance_metrics || {};

            return `
                <tr>
                    <td><span class="status-pill ${statusClass}">${statusLabel}</span></td>
                    <td><strong>${escapeHtml(b.bus_name)}</strong><br><small class="text-muted">${b.bus_id}</small></td>
                    <td><span class="mono">${escapeHtml(b.bus_number)}</span></td>
                    <td><code>${escapeHtml(b.device_id)}</code></td>
                    <td>${b.current_location ? b.current_location.speed : 0} km/h</td>
                    <td>${escapeHtml(b.current_route_status)}</td>
                    <td><strong class="text-primary">${distMetrics.trip_distance_km || 0.0} km</strong></td>
                    <td><strong class="text-success">${distMetrics.daily_distance_km || 0.0} km</strong></td>
                    <td>
                        <button class="btn btn-outline btn-xs" onclick="window.trackBusOnMap('${b.bus_id}')">
                            <i class="fa-solid fa-crosshairs"></i> Track
                        </button>
                    </td>
                </tr>
            `;
        }).join("");
    }

    // ==========================================
    // 7. BUS SELECTOR PANEL & LIVE MAP
    // ==========================================
    function renderBusesList() {
        if (!elements.busesListContainer) return;

        let filtered = state.buses;
        if (state.searchQuery) {
            const q = state.searchQuery.toLowerCase();
            filtered = filtered.filter(b =>
                b.bus_id.toLowerCase().includes(q) ||
                b.bus_name.toLowerCase().includes(q) ||
                b.bus_number.toLowerCase().includes(q) ||
                b.device_id.toLowerCase().includes(q) ||
                (b.driver_name && b.driver_name.toLowerCase().includes(q))
            );
        }

        if (state.activeFilter === "running") {
            filtered = filtered.filter(b => b.is_moving || (b.is_online && !b.is_reached_college));
        } else if (state.activeFilter === "reached_college") {
            filtered = filtered.filter(b => b.is_reached_college);
        } else if (state.activeFilter === "offline") {
            filtered = filtered.filter(b => !b.is_online);
        }

        if (filtered.length === 0) {
            elements.busesListContainer.innerHTML = `
                <div class="empty-state">
                    <i class="fa-solid fa-bus"></i>
                    <p>No buses found matching filter</p>
                </div>
            `;
            return;
        }

        elements.busesListContainer.innerHTML = filtered.map(b => {
            const isSelected = b.bus_id === state.selectedBusId;
            const statusClass = b.is_reached_college ? "reached_college" : (b.is_moving ? "moving" : (b.is_online ? "stopped" : "offline"));
            const statusLabel = b.is_reached_college ? "Reached College" : (b.is_moving ? "Moving" : (b.is_online ? "Stopped" : "Offline"));
            const speed = b.current_location ? b.current_location.speed : 0;
            const dist = b.distance_metrics ? b.distance_metrics.daily_distance_km : 0.0;

            return `
                <div class="bus-card ${isSelected ? "selected" : ""}" data-bus-id="${b.bus_id}">
                    <div class="bus-card-top">
                        <div>
                            <strong class="bus-card-name">${escapeHtml(b.bus_name)}</strong>
                            <div class="bus-card-sub">
                                <span class="bus-card-no">${escapeHtml(b.bus_number)}</span>
                                <span class="bus-card-esp" title="Assigned Hardware Device">
                                    <i class="fa-solid fa-microchip"></i> ${escapeHtml(b.device_id)}
                                </span>
                            </div>
                        </div>
                        <span class="card-status-badge ${statusClass}">${statusLabel}</span>
                    </div>

                    <div class="bus-card-meta">
                        <span><i class="fa-solid fa-gauge"></i> ${speed} km/h</span>
                        <span><i class="fa-solid fa-road"></i> ${dist} km today</span>
                        <span><i class="fa-solid fa-user"></i> ${escapeHtml(b.driver_name || "Driver")}</span>
                    </div>
                </div>
            `;
        }).join("");

        // Attach click listeners
        elements.busesListContainer.querySelectorAll(".bus-card").forEach(card => {
            card.addEventListener("click", () => {
                selectBus(card.dataset.busId, true);
            });
        });
    }

    function selectBus(busId, panTo = true) {
        state.selectedBusId = busId;
        renderBusesList();

        const bus = state.buses.find(b => b.bus_id === busId);
        if (!bus) return;

        updateTelemetryHud(bus);
        loadBusAssignedRoute(bus);

        if (panTo && bus.current_location) {
            centerBus(busId);
        }
    }

    window.trackBusOnMap = function(busId) {
        switchView("live-tracking");
        setTimeout(() => selectBus(busId, true), 120);
    };

    function centerBus(busId) {
        const bus = state.buses.find(b => b.bus_id === busId);
        if (!bus || !bus.current_location) return;
        const lat = parseFloat(bus.current_location.latitude);
        const lng = parseFloat(bus.current_location.longitude);
        if (elements.map && !isNaN(lat) && !isNaN(lng)) {
            elements.map.setView([lat, lng], 15, { animate: true });
        }
    }

    function updateTelemetryHud(bus) {
        elements.hudBusName.textContent = bus.bus_name;
        elements.hudBusNumber.textContent = bus.bus_number;
        elements.hudEspVal.textContent = bus.device_id;
        elements.hudRouteVal.textContent = bus.route_name;

        const statusClass = bus.is_reached_college ? "reached_college" : (bus.is_moving ? "moving" : (bus.is_online ? "stopped" : "offline"));
        const statusLabel = bus.is_reached_college ? "Reached College" : (bus.is_moving ? "Live Moving" : (bus.is_online ? "Stopped" : "Offline / Parked"));
        elements.hudConnectionBadge.className = `card-status-badge ${statusClass}`;
        elements.hudConnectionBadge.textContent = statusLabel;

        const loc = bus.current_location;
        if (loc) {
            elements.hudCoordsVal.textContent = `${loc.latitude.toFixed(6)}, ${loc.longitude.toFixed(6)}`;
            elements.hudGoogleMapsLink.href = `https://www.google.com/maps?q=${loc.latitude},${loc.longitude}`;
            elements.hudSpeedVal.textContent = `${loc.speed} km/h`;
            elements.hudHeadingVal.textContent = `${loc.heading}°`;
            elements.hudSatsVal.textContent = `${loc.satellites || 8} Sats`;
            elements.hudUpdatedVal.textContent = loc.time || "Just now";
        } else {
            elements.hudCoordsVal.textContent = "--";
            elements.hudSpeedVal.textContent = "0 km/h";
            elements.hudHeadingVal.textContent = "0° (N)";
            elements.hudSatsVal.textContent = "0 Sats";
            elements.hudUpdatedVal.textContent = "Never";
        }

        // Distance Metrics
        const dm = bus.distance_metrics || {};
        elements.hudTripDistVal.textContent = `${(dm.trip_distance_km || 0.0).toFixed(1)} km`;
        elements.hudTripStatusSub.textContent = dm.current_trip_status ? `Trip #${dm.current_trip_number || 1} (${dm.current_trip_status})` : "Current Trip";
        elements.hudDailyDistVal.textContent = `${(dm.daily_distance_km || 0.0).toFixed(1)} km`;
        elements.hudRemainingDistVal.textContent = `${(dm.remaining_distance_km || 0.0).toFixed(1)} km`;
        elements.hud7DayDistVal.textContent = `${(dm.seven_day_total_km || 0.0).toFixed(1)} km`;
    }

    function updateMapMarkers() {
        if (!elements.map) return;

        state.buses.forEach(b => {
            const loc = b.current_location;
            if (!loc || isNaN(loc.latitude) || isNaN(loc.longitude)) return;
            const lat = parseFloat(loc.latitude);
            const lng = parseFloat(loc.longitude);

            const isSelected = b.bus_id === state.selectedBusId;
            const statusClass = b.is_reached_college ? "reached-college" : (b.is_moving ? "moving" : (b.is_online ? "stopped" : "offline"));

            const iconHtml = `
                <div class="bus-map-pin ${statusClass} ${isSelected ? "selected-pulse" : ""}">
                    <i class="fa-solid fa-bus"></i>
                </div>
            `;

            const icon = L.divIcon({
                className: "custom-bus-pin-container",
                html: iconHtml,
                iconSize: [36, 36],
                iconAnchor: [18, 18]
            });

            if (state.busMarkers[b.bus_id]) {
                state.busMarkers[b.bus_id].setLatLng([lat, lng]);
                state.busMarkers[b.bus_id].setIcon(icon);
            } else {
                const marker = L.marker([lat, lng], { icon: icon }).addTo(elements.map);
                marker.bindTooltip(`<strong>${escapeHtml(b.bus_name)}</strong><br>${b.bus_number} (${b.current_route_status})`, { direction: "top" });
                marker.on("click", () => selectBus(b.bus_id, true));
                state.busMarkers[b.bus_id] = marker;
            }
        });
    }

    async function loadBusAssignedRoute(bus) {
        if (!elements.map || !bus.route_id) return;

        if (state.routePolyline) {
            elements.map.removeLayer(state.routePolyline);
            state.routePolyline = null;
        }
        elements.stopsMarkersGroup.clearLayers();

        try {
            const resp = await fetch(`/api/routes/${bus.route_id}`);
            if (!resp.ok) return;
            const data = await resp.json();
            const route = data.route;
            if (!route || !route.waypoints || route.waypoints.length === 0) return;

            state.routePolyline = L.polyline(route.waypoints, {
                color: "#2563eb",
                weight: 5,
                opacity: 0.85,
                dashArray: "1, 8",
                lineJoin: "round"
            }).addTo(elements.map);

            // Draw Starting point marker
            const startPt = route.waypoints[0];
            const startIcon = L.divIcon({
                className: "route-terminal-pin start",
                html: `<div style="background:#10b981; color:#fff; width:28px; height:28px; border-radius:50%; display:flex; align-items:center; justify-content:center; box-shadow:0 2px 6px rgba(0,0,0,0.25); border:2px solid #fff;"><i class="fa-solid fa-play"></i></div>`,
                iconSize: [28, 28],
                iconAnchor: [14, 14]
            });
            L.marker(startPt, { icon: startIcon })
                .bindTooltip(`<strong>Starting Location:</strong> ${escapeHtml(route.origin)}`, { direction: "top" })
                .addTo(elements.stopsMarkersGroup);

            // Draw intermediate stops if assigned
            const stopsResp = await fetch(`/api/stops?route_id=${bus.route_id}`);
            if (stopsResp.ok) {
                const stopsData = await stopsResp.json();
                (stopsData.stops || []).forEach((st, idx) => {
                    const stopIcon = L.divIcon({
                        className: "intermediate-stop-pin",
                        html: `<div style="background:#f59e0b; color:#fff; width:22px; height:22px; border-radius:50%; display:flex; align-items:center; justify-content:center; font-size:10px; font-weight:800; border:2px solid #fff;">${idx + 1}</div>`,
                        iconSize: [22, 22],
                        iconAnchor: [11, 11]
                    });
                    L.marker([st.latitude, st.longitude], { icon: stopIcon })
                        .bindTooltip(`<strong>Stop ${idx + 1}:</strong> ${escapeHtml(st.name)}`, { direction: "top" })
                        .addTo(elements.stopsMarkersGroup);
                });
            }
        } catch (err) {
            console.warn("Could not load route polyline:", err);
        }
    }

    // ==========================================
    // 8. VIEW 3: BUSES (30-Bus Fleet Table)
    // ==========================================
    function renderFleetTable() {
        if (!elements.fleetTableBody) return;

        let filtered = state.buses;
        if (state.fleetSearchQuery) {
            const q = state.fleetSearchQuery.toLowerCase();
            filtered = filtered.filter(b =>
                b.bus_id.toLowerCase().includes(q) ||
                b.bus_name.toLowerCase().includes(q) ||
                b.bus_number.toLowerCase().includes(q) ||
                b.device_id.toLowerCase().includes(q) ||
                (b.route_name && b.route_name.toLowerCase().includes(q)) ||
                (b.driver_name && b.driver_name.toLowerCase().includes(q))
            );
        }

        if (state.fleetFilter === "running") {
            filtered = filtered.filter(b => b.is_moving || (b.is_online && !b.is_reached_college));
        } else if (state.fleetFilter === "reached_college") {
            filtered = filtered.filter(b => b.is_reached_college);
        } else if (state.fleetFilter === "offline") {
            filtered = filtered.filter(b => !b.is_online);
        }

        if (filtered.length === 0) {
            elements.fleetTableBody.innerHTML = `<tr><td colspan="9" class="text-center text-muted" style="padding:24px;">No buses found</td></tr>`;
            return;
        }

        elements.fleetTableBody.innerHTML = filtered.map(b => {
            const statusClass = b.is_reached_college ? "reached_college" : (b.is_moving ? "moving" : (b.is_online ? "stopped" : "offline"));
            const statusLabel = b.is_reached_college ? "Reached College" : (b.is_moving ? "Running" : (b.is_online ? "Stopped" : "Offline"));
            const dm = b.distance_metrics || {};

            return `
                <tr>
                    <td><span class="status-pill ${statusClass}">${statusLabel}</span></td>
                    <td><strong>${escapeHtml(b.bus_name)}</strong><br><small class="text-muted font-mono">${b.bus_id}</small></td>
                    <td><span class="mono">${escapeHtml(b.bus_number)}</span></td>
                    <td><code>${escapeHtml(b.device_id)}</code></td>
                    <td>${escapeHtml(b.route_name)}</td>
                    <td>${escapeHtml(b.driver_name || "Unassigned")}<br><small class="text-muted">${escapeHtml(b.driver_phone || "N/A")}</small></td>
                    <td><strong class="text-success">${(dm.daily_distance_km || 0.0).toFixed(1)} km</strong></td>
                    <td>${b.current_location ? b.current_location.time : "Never"}</td>
                    <td>
                        <div class="table-actions">
                            <button class="btn btn-outline btn-xs" onclick="window.trackBusOnMap('${b.bus_id}')" title="Live Track on Map">
                                <i class="fa-solid fa-location-crosshairs"></i> Track
                            </button>
                            <button class="btn btn-outline btn-xs" onclick="window.editBusModal('${b.bus_id}')" title="Edit Bus Details">
                                <i class="fa-solid fa-pen"></i>
                            </button>
                            <button class="btn btn-danger btn-xs" onclick="window.deleteBusAction('${b.bus_id}')" title="Delete Bus">
                                <i class="fa-solid fa-trash"></i>
                            </button>
                        </div>
                    </td>
                </tr>
            `;
        }).join("");
    }

    window.editBusModal = async function(busId) {
        const bus = state.buses.find(b => b.bus_id === busId);
        if (!bus) return;

        const newName = prompt("Edit Bus Name:", bus.bus_name);
        if (newName === null) return;
        const newDriver = prompt("Edit Driver Name:", bus.driver_name || "");
        const newPhone = prompt("Edit Driver Phone:", bus.driver_phone || "");

        try {
            const resp = await fetch(`/api/admin/buses/${busId}`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    bus_name: newName,
                    driver_name: newDriver,
                    driver_phone: newPhone
                })
            });
            const res = await resp.json();
            if (resp.ok) {
                showToast(`Bus ${busId} updated successfully`, "success");
                fetchBuses();
            } else {
                showToast(res.message || "Failed to update bus", "error");
            }
        } catch (err) {
            showToast("Server error updating bus", "error");
        }
    };

    window.deleteBusAction = async function(busId) {
        if (!confirm(`Are you sure you want to delete ${busId}? This action requires administrator permissions.`)) return;

        try {
            const resp = await fetch(`/api/admin/buses/${busId}`, { method: "DELETE" });
            const res = await resp.json();
            if (resp.ok) {
                showToast(`Bus ${busId} deleted successfully`, "success");
                fetchBuses();
            } else {
                showToast(res.message || "Failed to delete bus", "error");
            }
        } catch (err) {
            showToast("Server error deleting bus", "error");
        }
    };

    // ==========================================
    // 9. VIEW 4: REGISTER BUS
    // ==========================================
    function setupRegisterBusForm() {
        if (!elements.dedicatedRegisterBusForm) return;

        elements.dedicatedRegisterBusForm.addEventListener("submit", async (e) => {
            e.preventDefault();

            const busData = {
                bus_name: elements.regBusName.value.trim(),
                bus_id: elements.regBusId.value.trim().toUpperCase(),
                bus_number: elements.regBusNumber.value.trim().toUpperCase(),
                device_id: elements.regDeviceId.value.trim().toUpperCase(),
                driver_name: elements.regDriverName.value.trim(),
                driver_phone: elements.regDriverPhone.value.trim(),
                route_id: elements.regRouteSelect.value,
                college_destination: elements.regCollegeDest.value
            };

            try {
                const resp = await fetch("/api/buses", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(busData)
                });
                const res = await resp.json();

                if (resp.ok) {
                    showToast(`Bus ${busData.bus_name} registered successfully!`, "success");
                    elements.dedicatedRegisterBusForm.reset();
                    await fetchBuses();
                    switchView("buses");
                } else {
                    showToast(res.message || "Registration failed", "error");
                }
            } catch (err) {
                showToast("Server error during bus registration", "error");
            }
        });
    }

    function populateRouteDropdowns(routes) {
        if (!elements.regRouteSelect) return;
        elements.regRouteSelect.innerHTML = routes.map(r => `
            <option value="${r.id}">${escapeHtml(r.route_name)} (${r.distance_km || 12} km)</option>
        `).join("");
    }

    // ==========================================
    // 10. VIEW 5: ROUTE MANAGEMENT & GEOCODING
    // ==========================================
    function renderRoutesGrid(routes) {
        if (!elements.routesCardsGrid) return;
        elements.routesCardsGrid.innerHTML = routes.map(r => `
            <div class="route-card">
                <div class="route-card-header">
                    <span class="route-title">${escapeHtml(r.route_name)}</span>
                    <span class="route-code-badge">${escapeHtml(r.route_code || r.id)}</span>
                </div>
                <div class="route-path-flow">
                    <div class="route-path-step text-success">
                        <i class="fa-solid fa-play"></i> <strong>Start:</strong> ${escapeHtml(r.origin)}
                    </div>
                    <div class="route-path-step text-muted">
                        <i class="fa-solid fa-map-pin"></i> <strong>Stops:</strong> ${(r.assigned_stops || []).length} Intermediate Stops
                    </div>
                    <div class="route-path-step text-primary">
                        <i class="fa-solid fa-flag-checkered"></i> <strong>End:</strong> ${escapeHtml(r.destination)}
                    </div>
                </div>
                <div class="route-card-footer">
                    <span><i class="fa-solid fa-road"></i> ${r.distance_km || 12} km</span>
                    <span><i class="fa-solid fa-clock"></i> ${r.duration_minutes || 60} mins</span>
                    <button class="btn btn-outline btn-xs" onclick="window.previewRouteOnMap('${r.id}')">
                        <i class="fa-solid fa-eye"></i> View on Map
                    </button>
                </div>
            </div>
        `).join("");
    }

    window.previewRouteOnMap = function(routeId) {
        const route = state.routes.find(r => r.id === routeId);
        if (!route) return;

        switchView("live-tracking");
        setTimeout(() => {
            if (elements.map && route.waypoints && route.waypoints.length > 0) {
                if (state.routePolyline) elements.map.removeLayer(state.routePolyline);
                state.routePolyline = L.polyline(route.waypoints, {
                    color: "#2563eb",
                    weight: 5,
                    dashArray: "2, 6"
                }).addTo(elements.map);
                elements.map.fitBounds(state.routePolyline.getBounds(), { padding: [40, 40] });
            }
        }, 150);
    };

    function setupRouteGeocoding() {
        if (!elements.btnGeocodeOrigin) return;

        elements.btnGeocodeOrigin.addEventListener("click", async () => {
            const query = elements.routeOriginInput.value.trim();
            if (!query) return;

            try {
                const resp = await fetch(`/api/routes/geocode?q=${encodeURIComponent(query)}`);
                const data = await resp.json();
                const suggestions = data.suggestions || [];

                if (suggestions.length === 0) {
                    elements.originSuggestionsBox.innerHTML = `<div class="geocoding-item text-muted">No locations found.</div>`;
                    elements.originSuggestionsBox.classList.remove("hidden");
                    return;
                }

                elements.originSuggestionsBox.innerHTML = suggestions.map((s, idx) => `
                    <div class="geocoding-item" data-idx="${idx}">
                        <strong>${escapeHtml(s.name)}</strong><br>
                        <small class="text-muted">${escapeHtml(s.display_name)}</small>
                    </div>
                `).join("");
                elements.originSuggestionsBox.classList.remove("hidden");

                elements.originSuggestionsBox.querySelectorAll(".geocoding-item").forEach(item => {
                    item.addEventListener("click", () => {
                        const sel = suggestions[parseInt(item.dataset.idx)];
                        elements.routeOriginInput.value = sel.name;
                        confirmedOriginCoords = [sel.latitude, sel.longitude];
                        elements.originCoordsText.textContent = `Confirmed: ${sel.latitude}, ${sel.longitude}`;
                        elements.originConfirmedPill.classList.remove("hidden");
                        elements.originSuggestionsBox.classList.add("hidden");
                    });
                });
            } catch (err) {
                showToast("Geocoding lookup failed", "error");
            }
        });

        elements.btnToggleCreateRoute.addEventListener("click", () => {
            elements.routeCreateCard.classList.toggle("hidden");
        });

        elements.btnCancelRouteForm.addEventListener("click", () => {
            elements.routeCreateCard.classList.add("hidden");
        });

        elements.routeForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            const name = elements.routeNameInput.value.trim();
            const code = elements.routeCodeInput.value.trim() || `R${state.routes.length + 1}`;
            const origin = elements.routeOriginInput.value.trim();
            const dest = elements.routeDestInput.value.trim();

            const waypoints = confirmedOriginCoords ? [confirmedOriginCoords, [17.3156, 78.5833]] : [[17.3850, 78.4866], [17.3156, 78.5833]];

            try {
                const resp = await fetch("/api/routes", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        route_name: name,
                        route_code: code,
                        origin: origin,
                        destination: dest,
                        distance_km: 14.5,
                        duration_minutes: 55,
                        waypoints: waypoints
                    })
                });
                const res = await resp.json();
                if (resp.ok) {
                    showToast(`Route ${name} created successfully!`, "success");
                    elements.routeForm.reset();
                    elements.routeCreateCard.classList.add("hidden");
                    fetchRoutes();
                } else {
                    showToast(res.message || "Failed to create route", "error");
                }
            } catch (err) {
                showToast("Server error creating route", "error");
            }
        });
    }

    // ==========================================
    // 11. VIEW 6: TRIP HISTORY (2-4 Trips Daily)
    // ==========================================
    async function loadTripHistoryView() {
        if (!elements.tripHistoryBusSelect) return;

        // Populate Bus Dropdown
        elements.tripHistoryBusSelect.innerHTML = state.buses.map(b => `
            <option value="${b.bus_id}" ${b.bus_id === state.selectedTripBusId ? "selected" : ""}>
                ${escapeHtml(b.bus_name)} (${b.bus_id})
            </option>
        `).join("");

        if (!state.selectedTripBusId && state.buses.length > 0) {
            state.selectedTripBusId = state.buses[0].bus_id;
        }

        // Populate 7-Day Date Dropdown
        const now = new Date();
        const dateOptions = [];
        for (let i = 0; i < 7; i++) {
            const d = new Date(now.getTime() - i * 86400000);
            const dStr = `${String(d.getDate()).padStart(2, "0")}-${String(d.getMonth() + 1).padStart(2, "0")}-${d.getFullYear()}`;
            const label = i === 0 ? `Today (${dStr})` : (i === 1 ? `Yesterday (${dStr})` : `${d.toLocaleDateString("en-US", { weekday: "short" })} (${dStr})`);
            dateOptions.push(`<option value="${dStr}">${label}</option>`);
        }
        elements.tripHistoryDateSelect.innerHTML = dateOptions.join("");

        await fetchBusTripHistory(state.selectedTripBusId, elements.tripHistoryDateSelect.value);
    }

    async function fetchBusTripHistory(busId, dateStr) {
        if (!busId) return;

        try {
            // 1. Fetch 3 Distance measurements
            const distResp = await fetch(`/api/buses/${busId}/distances`);
            if (distResp.ok) {
                const distData = await distResp.json();
                const dm = distData.distance_metrics || {};
                elements.tripViewDist.textContent = `${(dm.trip_distance_km || 0.0).toFixed(1)} km`;
                elements.tripViewStatus.textContent = dm.current_trip_status ? `Trip #${dm.current_trip_number || 1} (${dm.current_trip_status})` : "Active Trip";
                elements.dailyViewDist.textContent = `${(dm.daily_distance_km || 0.0).toFixed(1)} km`;
                elements.sevenDayViewDist.textContent = `${(dm.seven_day_total_km || 0.0).toFixed(1)} km`;
            }

            // 2. Fetch individual daily trips for this date
            const tripsResp = await fetch(`/api/buses/${busId}/trips?date=${encodeURIComponent(dateStr)}`);
            if (tripsResp.ok) {
                const tripsData = await tripsResp.json();
                const trips = tripsData.trips || [];
                elements.tripCountBadge.textContent = `${trips.length} Trips Recorded for ${dateStr}`;

                if (trips.length === 0) {
                    elements.tripsTableBody.innerHTML = `<tr><td colspan="8" class="text-center text-muted" style="padding:20px;">No trips recorded for this date</td></tr>`;
                    return;
                }

                elements.tripsTableBody.innerHTML = trips.map(t => {
                    const statusClass = t.status === "COMPLETED" ? "badge-success" : "badge-info";
                    const sCoord = t.start_coordinates ? `${t.start_coordinates[0].toFixed(4)}, ${t.start_coordinates[1].toFixed(4)}` : "--";
                    const eCoord = t.end_coordinates ? `${t.end_coordinates[0].toFixed(4)}, ${t.end_coordinates[1].toFixed(4)}` : "--";

                    return `
                        <tr>
                            <td><strong>Trip #${t.trip_number || 1}</strong></td>
                            <td>${t.start_time || "--"}</td>
                            <td><span class="mono">${sCoord}</span></td>
                            <td>${t.end_time || (t.status === "RUNNING" ? "<span class='text-primary'>In Progress</span>" : "--")}</td>
                            <td><span class="mono">${eCoord}</span></td>
                            <td><strong>${(t.distance_km || 0.0).toFixed(1)} km</strong></td>
                            <td><span class="badge ${statusClass}">${t.status}</span></td>
                            <td>${t.arrival_time || (t.status === "COMPLETED" ? t.end_time : "--")}</td>
                        </tr>
                    `;
                }).join("");
            }
        } catch (err) {
            console.error("Trip history fetch error:", err);
        }
    }

    // ==========================================
    // 12. VIEW 7: COLLEGE SETTINGS
    // ==========================================
    function loadCollegeSettingsView() {
        if (!state.collegeConfig) {
            fetchCollegeConfig();
        }
    }

    function setupCollegeSettingsForm() {
        if (!elements.collegeConfigForm) return;

        elements.collegeConfigForm.addEventListener("submit", async (e) => {
            e.preventDefault();

            const configData = {
                college_name: elements.collegeNameInput.value.trim(),
                college_latitude: parseFloat(elements.collegeLatInput.value),
                college_longitude: parseFloat(elements.collegeLngInput.value),
                college_geofence_radius_meters: parseInt(elements.collegeRadiusInput.value)
            };

            try {
                const resp = await fetch("/api/college", {
                    method: "PUT",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(configData)
                });
                const res = await resp.json();

                if (resp.ok) {
                    showToast("College destination & geofence updated successfully!", "success");
                    await fetchCollegeConfig();
                } else {
                    showToast(res.message || "Failed to update college settings", "error");
                }
            } catch (err) {
                showToast("Server error updating college settings", "error");
            }
        });
    }

    // ==========================================
    // 13. VIEW 8: DEVICE MANAGEMENT
    // ==========================================
    function renderDevicesView(data) {
        const metrics = data.metrics || {};
        elements.devTotalCount.textContent = metrics.total_devices || state.devices.length || 30;
        elements.devOnlineCount.textContent = metrics.online_devices || 0;
        elements.devGpsCount.textContent = metrics.gps_active_devices || 0;
        elements.devUnassignedCount.textContent = metrics.unassigned_devices || 0;

        if (metrics.unassigned_devices > 0) {
            elements.devUnassignedBanner.classList.remove("hidden");
        } else {
            elements.devUnassignedBanner.classList.add("hidden");
        }

        if (!elements.devicesTableViewBody) return;
        elements.devicesTableViewBody.innerHTML = state.devices.map(d => {
            const statusClass = d.is_online ? "connected" : "offline";
            const statusText = d.is_online ? "Online" : "Offline";
            const busOptions = state.buses.map(b => `
                <option value="${b.bus_id}" ${b.bus_id === d.assigned_bus_id ? "selected" : ""}>
                    ${escapeHtml(b.bus_name)} (${b.bus_id})
                </option>
            `).join("");

            return `
                <tr>
                    <td><span class="status-pill ${statusClass}">${statusText}</span></td>
                    <td><strong>${escapeHtml(d.device_name)}</strong><br><small class="mono text-muted">${d.device_id}</small></td>
                    <td><span class="badge badge-info">${escapeHtml(d.device_type || "ESP8266")}</span></td>
                    <td><span class="mono">${escapeHtml(d.mac_address || "--")}</span></td>
                    <td>${d.gps_available ? "<span class='text-success'><i class='fa-solid fa-satellite'></i> Fix Acquired</span>" : "<span class='text-muted'>Searching</span>"}</td>
                    <td>
                        <select class="form-select form-select-sm" onchange="window.assignDeviceToBus('${d.device_id}', this.value)">
                            <option value="">-- Unassigned --</option>
                            ${busOptions}
                        </select>
                    </td>
                    <td>${d.last_seen_relative || "Never"}</td>
                    <td>
                        <button class="btn btn-outline btn-xs" onclick="window.renameDeviceModal('${d.device_id}')">
                            <i class="fa-solid fa-pen"></i> Rename
                        </button>
                    </td>
                </tr>
            `;
        }).join("");
    }

    window.assignDeviceToBus = async function(deviceId, busId) {
        try {
            const resp = await fetch(`/api/devices/${deviceId}/assign`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ bus_id: busId })
            });
            const res = await resp.json();
            if (resp.ok) {
                showToast(`Device ${deviceId} mapped to bus ${busId || "Unassigned"}`, "success");
                fetchDevices();
                fetchBuses();
            } else {
                showToast(res.message || "Failed to assign device", "error");
            }
        } catch (err) {
            showToast("Server error assigning device", "error");
        }
    };

    window.renameDeviceModal = async function(deviceId) {
        const dev = state.devices.find(d => d.device_id === deviceId);
        if (!dev) return;
        const newName = prompt("Rename Hardware Tracker:", dev.device_name);
        if (!newName) return;

        try {
            const resp = await fetch(`/api/devices/${deviceId}`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ device_name: newName })
            });
            const res = await resp.json();
            if (resp.ok) {
                showToast("Device renamed successfully", "success");
                fetchDevices();
            } else {
                showToast(res.message || "Failed to rename device", "error");
            }
        } catch (err) {
            showToast("Server error renaming device", "error");
        }
    };

    // ==========================================
    // 14. VIEW 9: STORAGE MANAGEMENT (300 MB)
    // ==========================================
    function renderStorageView(s) {
        if (!elements.storageHeroUsageText || !s) return;
        const used = s.total_used_mb || 0.5;
        const maxMb = s.max_storage_mb || 300.0;
        const pct = s.percent_used || 0.17;
        const warning = s.warning_level || "NORMAL";

        elements.storageHeroUsageText.textContent = `${used.toFixed(2)} MB of ${maxMb.toFixed(1)} MB Allocated`;
        elements.storageHeroProgressFill.style.width = `${Math.max(1, Math.min(100, pct))}%`;
        elements.storageHeroProgressFill.className = `storage-progress-fill ${warning.toLowerCase()}`;

        const badge = elements.storageHeroBadge;
        badge.className = `storage-warning-badge ${warning.toLowerCase()}`;
        badge.innerHTML = `<i class="fa-solid fa-circle-check"></i> ${warning} (${pct.toFixed(2)}% USED)`;

        const cats = s.category_breakdown_mb || {};
        elements.storageCatDb.textContent = `${(cats.database || 0.05).toFixed(2)} MB`;
        elements.storageCatTracking.textContent = `${(cats.tracking || 0.12).toFixed(2)} MB`;
        elements.storageCatTrips.textContent = `${(cats.trips || 0.15).toFixed(2)} MB`;
        elements.storageCatBackups.textContent = `${(cats.backups || 0.18).toFixed(2)} MB`;
        elements.storageCatSecurity.textContent = `${(cats.security || 0.02).toFixed(2)} MB`;

        if (!elements.storageFilesTableBody) return;
        const files = s.files || [];
        elements.storageFilesTableBody.innerHTML = files.map(f => `
            <tr>
                <td><code>${escapeHtml(f.filename)}</code></td>
                <td><span class="badge badge-info">${escapeHtml(f.category)}</span></td>
                <td><strong>${f.size_kb} KB</strong> (${f.size_mb} MB)</td>
                <td>${f.last_modified ? new Date(f.last_modified).toLocaleString() : "Recent"}</td>
                <td>
                    ${f.is_permanent ?
                        "<span class='text-primary'><i class='fa-solid fa-lock'></i> Permanent Config</span>" :
                        "<span class='text-success'><i class='fa-solid fa-clock-rotate-left'></i> Rolling 7-Day Pruned</span>"}
                </td>
            </tr>
        `).join("");
    }

    function setupStorageControls() {
        if (!elements.btnTriggerStorageCleanup) return;

        elements.btnTriggerStorageCleanup.addEventListener("click", async () => {
            if (!confirm("Execute immediate 7-day rolling data retention cleanup and backup snapshot creation?")) return;

            try {
                const resp = await fetch("/api/admin/storage/cleanup", { method: "POST" });
                const res = await resp.json();
                if (resp.ok) {
                    showToast(`Cleanup executed: ${res.result ? res.result.pruned_history_records : 0} records pruned`, "success");
                    fetchStorageMetrics();
                } else {
                    showToast(res.message || "Cleanup failed", "error");
                }
            } catch (err) {
                showToast("Server error executing storage cleanup", "error");
            }
        });
    }

    // ==========================================
    // 15. VIEW 10: SECURITY SETTINGS & RBAC
    // ==========================================
    async function fetchSecurityData() {
        try {
            // 1. Fetch Users
            const uResp = await fetch("/api/admin/users");
            if (uResp.ok) {
                const uData = await uResp.json();
                renderUsersTable(uData.users || []);
            }

            // 2. Fetch Audit Logs
            const aResp = await fetch("/api/admin/audit-logs");
            if (aResp.ok) {
                const aData = await aResp.json();
                renderAuditLogsTable(aData.audit_logs || []);
            }
        } catch (err) {
            console.warn("Security data fetch error:", err);
        }
    }

    function renderUsersTable(users) {
        if (!elements.secUsersTableBody) return;
        elements.secUsersTableBody.innerHTML = users.map(u => `
            <tr>
                <td><strong>${escapeHtml(u.username)}</strong></td>
                <td><span class="role-tag ${u.role.toLowerCase()}">${u.role}</span></td>
                <td>${escapeHtml(u.full_name || u.username)}</td>
            </tr>
        `).join("");
    }

    function renderAuditLogsTable(logs) {
        if (!elements.secAuditLogsTableBody) return;
        if (logs.length === 0) {
            elements.secAuditLogsTableBody.innerHTML = `<tr><td colspan="7" class="text-center text-muted" style="padding:16px;">No audit logs recorded</td></tr>`;
            return;
        }

        elements.secAuditLogsTableBody.innerHTML = logs.slice(0, 15).map(l => `
            <tr>
                <td>${l.date} ${l.time}</td>
                <td><strong>${escapeHtml(l.username)}</strong></td>
                <td><span class="role-tag ${(l.role || "admin").toLowerCase()}">${l.role}</span></td>
                <td><code>${escapeHtml(l.action)}</code></td>
                <td>${escapeHtml(l.target_type)} (${escapeHtml(l.target_id || "")})</td>
                <td><small>${escapeHtml(l.details || "")}</small></td>
                <td><code>${escapeHtml(l.ip_address || "127.0.0.1")}</code></td>
            </tr>
        `).join("");
    }

    function setupSecurityForms() {
        // Change Password Form
        if (elements.changePasswordForm) {
            elements.changePasswordForm.addEventListener("submit", async (e) => {
                e.preventDefault();
                const oldPass = elements.oldPassInput.value;
                const newPass = elements.newPassInput.value;
                const username = state.currentUser ? state.currentUser.username : "admin";

                try {
                    const resp = await fetch(`/api/admin/users/${username}/password`, {
                        method: "PUT",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ old_password: oldPass, new_password: newPass })
                    });
                    const res = await resp.json();
                    if (resp.ok) {
                        showToast("Password updated successfully!", "success");
                        elements.changePasswordForm.reset();
                    } else {
                        showToast(res.message || "Failed to update password", "error");
                    }
                } catch (err) {
                    showToast("Server error updating password", "error");
                }
            });
        }

        // Create User Form
        if (elements.createNewUserForm) {
            elements.createNewUserForm.addEventListener("submit", async (e) => {
                e.preventDefault();
                const uData = {
                    username: elements.newUserNameInput.value.trim().toLowerCase(),
                    role: elements.newUserRoleSelect.value,
                    password: elements.newUserPasswordInput.value
                };

                try {
                    const resp = await fetch("/api/admin/users", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify(uData)
                    });
                    const res = await resp.json();
                    if (resp.ok) {
                        showToast(`User ${uData.username} created successfully!`, "success");
                        elements.createNewUserForm.reset();
                        fetchSecurityData();
                    } else {
                        showToast(res.message || "Failed to create user", "error");
                    }
                } catch (err) {
                    showToast("Server error creating user", "error");
                }
            });
        }

        // Auth Login Form
        if (elements.authLoginForm) {
            elements.authLoginForm.addEventListener("submit", async (e) => {
                e.preventDefault();
                const creds = {
                    username: elements.loginUsername.value.trim(),
                    password: elements.loginPassword.value.trim()
                };

                try {
                    const resp = await fetch("/api/auth/login", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify(creds)
                    });
                    const res = await resp.json();
                    if (resp.ok) {
                        showToast(`Welcome back, ${res.user.username}!`, "success");
                        state.currentUser = res.user;
                        updateUserSessionDisplay();
                        elements.authLoginModal.classList.add("hidden");
                    } else {
                        showToast(res.message || "Login failed", "error");
                    }
                } catch (err) {
                    showToast("Server error during login", "error");
                }
            });
        }

        elements.headerAuthBtn.addEventListener("click", () => {
            if (state.currentUser && !state.currentUser.is_guest) {
                // Logout
                fetch("/api/auth/logout", { method: "POST" }).then(() => {
                    state.currentUser = null;
                    updateUserSessionDisplay();
                    showToast("Logged out successfully", "info");
                });
            } else {
                elements.authLoginModal.classList.remove("hidden");
            }
        });

        elements.closeAuthModalBtn.addEventListener("click", () => {
            elements.authLoginModal.classList.add("hidden");
        });
    }

    function updateUserSessionDisplay() {
        if (!elements.sessionUsername) return;
        if (state.currentUser && !state.currentUser.is_guest) {
            elements.sessionUsername.textContent = state.currentUser.username;
            elements.sessionRoleTag.textContent = state.currentUser.role;
            elements.sessionRoleTag.className = `role-tag ${state.currentUser.role.toLowerCase()}`;
            elements.authBtnLabel.textContent = "Logout";
            if (elements.secCurrentUsername) elements.secCurrentUsername.textContent = state.currentUser.username;
            if (elements.secCurrentRole) elements.secCurrentRole.textContent = state.currentUser.role;
        } else {
            elements.sessionUsername.textContent = "Viewer";
            elements.sessionRoleTag.textContent = "VIEWER";
            elements.sessionRoleTag.className = "role-tag viewer";
            elements.authBtnLabel.textContent = "Admin Login";
            if (elements.secCurrentUsername) elements.secCurrentUsername.textContent = "viewer";
            if (elements.secCurrentRole) elements.secCurrentRole.textContent = "VIEWER";
        }
    }

    // ==========================================
    // 16. EVENT LISTENERS & NAVIGATION
    // ==========================================
    function setupEventListeners() {
        // Primary 10-Section Navigation Bar Click Handling
        elements.navButtons.forEach(btn => {
            btn.addEventListener("click", () => {
                switchView(btn.dataset.view);
            });
        });

        // Brand Logo click -> Dashboard
        if (elements.brandLogoHome) {
            elements.brandLogoHome.addEventListener("click", () => switchView("dashboard"));
        }

        if (elements.btnDashboardToMap) {
            elements.btnDashboardToMap.addEventListener("click", () => switchView("live-tracking"));
        }

        if (elements.btnViewAllBuses) {
            elements.btnViewAllBuses.addEventListener("click", () => switchView("buses"));
        }

        if (elements.btnFleetRegisterBus) {
            elements.btnFleetRegisterBus.addEventListener("click", () => switchView("register-bus"));
        }

        // Live Tracking Bus Search
        if (elements.busSearchInput) {
            elements.busSearchInput.addEventListener("input", (e) => {
                state.searchQuery = e.target.value.trim();
                elements.clearSearchBtn.classList.toggle("hidden", !state.searchQuery);
                renderBusesList();
            });

            elements.clearSearchBtn.addEventListener("click", () => {
                elements.busSearchInput.value = "";
                state.searchQuery = "";
                elements.clearSearchBtn.classList.add("hidden");
                renderBusesList();
            });
        }

        // Live Tracking Status Filter Tabs
        elements.statusTabBtns.forEach(btn => {
            btn.addEventListener("click", () => {
                elements.statusTabBtns.forEach(b => b.classList.remove("active"));
                btn.classList.add("active");
                state.activeFilter = btn.dataset.filter;
                renderBusesList();
            });
        });

        // Fleet Table Search and Filter
        if (elements.fleetSearchInput) {
            elements.fleetSearchInput.addEventListener("input", (e) => {
                state.fleetSearchQuery = e.target.value.trim();
                renderFleetTable();
            });
        }

        document.querySelectorAll("#fleetStatusTabs .status-tab-btn").forEach(btn => {
            btn.addEventListener("click", () => {
                document.querySelectorAll("#fleetStatusTabs .status-tab-btn").forEach(b => b.classList.remove("active"));
                btn.classList.add("active");
                state.fleetFilter = btn.dataset.fleetFilter;
                renderFleetTable();
            });
        });

        // Mobile View Tabs Toggle
        if (elements.mobileTabBusesBtn && elements.mobileTabMapBtn) {
            elements.mobileTabBusesBtn.addEventListener("click", () => {
                elements.mobileTabBusesBtn.classList.add("active");
                elements.mobileTabMapBtn.classList.remove("active");
                elements.busSelectorPanel.classList.remove("mobile-hidden");
                elements.liveMapPanel.classList.add("mobile-hidden");
            });

            elements.mobileTabMapBtn.addEventListener("click", () => {
                elements.mobileTabMapBtn.classList.add("active");
                elements.mobileTabBusesBtn.classList.remove("active");
                elements.busSelectorPanel.classList.add("mobile-hidden");
                elements.liveMapPanel.classList.remove("mobile-hidden");
                if (elements.map) elements.map.invalidateSize();
            });
        }

        // Copy Coordinates Button
        if (elements.hudCopyCoordsBtn) {
            elements.hudCopyCoordsBtn.addEventListener("click", () => {
                const text = elements.hudCoordsVal.textContent;
                if (text && text !== "--") {
                    navigator.clipboard.writeText(text).then(() => {
                        showToast(`Coordinates copied: ${text}`, "success");
                    });
                }
            });
        }

        // Map Floating Controls
        if (elements.centerSelectedBusBtn) {
            elements.centerSelectedBusBtn.addEventListener("click", () => {
                if (state.selectedBusId) centerBus(state.selectedBusId);
            });
        }

        if (elements.fitAllBusesBtn) {
            elements.fitAllBusesBtn.addEventListener("click", () => {
                const latlngs = [];
                state.buses.forEach(b => {
                    if (b.current_location) {
                        latlngs.push([b.current_location.latitude, b.current_location.longitude]);
                    }
                });
                if (latlngs.length > 0 && elements.map) {
                    elements.map.fitBounds(L.latLngBounds(latlngs), { padding: [50, 50] });
                }
            });
        }

        // Live vs 7-Day History Mode Toggle
        if (elements.btnModeLive && elements.btnModeHistory) {
            elements.btnModeLive.addEventListener("click", () => {
                elements.btnModeLive.classList.add("active");
                elements.btnModeHistory.classList.remove("active");
                elements.liveTelemetrySection.classList.remove("hidden");
                elements.historyTelemetrySection.classList.add("hidden");
            });

            elements.btnModeHistory.addEventListener("click", () => {
                elements.btnModeHistory.classList.add("active");
                elements.btnModeLive.classList.remove("active");
                elements.liveTelemetrySection.classList.add("hidden");
                elements.historyTelemetrySection.classList.remove("hidden");
                load7DayHistoryHUD(state.selectedBusId);
            });
        }

        // Trip History Toolbar Listeners
        if (elements.tripHistoryBusSelect) {
            elements.tripHistoryBusSelect.addEventListener("change", (e) => {
                state.selectedTripBusId = e.target.value;
                fetchBusTripHistory(state.selectedTripBusId, elements.tripHistoryDateSelect.value);
            });
        }

        if (elements.tripHistoryDateSelect) {
            elements.tripHistoryDateSelect.addEventListener("change", (e) => {
                fetchBusTripHistory(state.selectedTripBusId, e.target.value);
            });
        }
    }

    async function load7DayHistoryHUD(busId) {
        if (!busId || !elements.sevenDayNavPills) return;

        // Generate 7-day pill buttons
        const now = new Date();
        const pills = [];
        for (let i = 0; i < 7; i++) {
            const d = new Date(now.getTime() - i * 86400000);
            const dStr = `${String(d.getDate()).padStart(2, "0")}-${String(d.getMonth() + 1).padStart(2, "0")}-${d.getFullYear()}`;
            const dayName = d.toLocaleDateString("en-US", { weekday: "short" });
            pills.push(`
                <button class="day-pill-btn ${i === 0 ? "active" : ""}" data-date="${dStr}">
                    ${dayName} <small>${d.getDate()}</small>
                </button>
            `);
        }
        elements.sevenDayNavPills.innerHTML = pills.join("");

        elements.sevenDayNavPills.querySelectorAll(".day-pill-btn").forEach(btn => {
            btn.addEventListener("click", async () => {
                elements.sevenDayNavPills.querySelectorAll(".day-pill-btn").forEach(b => b.classList.remove("active"));
                btn.classList.add("active");
                loadHistoryDataForDate(busId, btn.dataset.date);
            });
        });

        // Load today's initial history
        const todayStr = `${String(now.getDate()).padStart(2, "0")}-${String(now.getMonth() + 1).padStart(2, "0")}-${now.getFullYear()}`;
        loadHistoryDataForDate(busId, todayStr);
    }

    async function loadHistoryDataForDate(busId, dateStr) {
        try {
            const resp = await fetch(`/api/buses/${busId}/history?date=${encodeURIComponent(dateStr)}`);
            if (!resp.ok) return;
            const data = await resp.json();
            const sum = data.trip_summary || {};
            elements.histDistVal.textContent = `${(sum.total_distance_km || 0.0).toFixed(1)} km`;
            elements.histMaxSpeedVal.textContent = `${sum.max_speed_kmh || 0} km/h`;
            elements.histPointsVal.textContent = data.total_count || 0;
            elements.histStopsVal.textContent = sum.stops_count || 0;
        } catch (err) {
            console.warn("History data load error:", err);
        }
    }

    // ==========================================
    // 17. AUTO REFRESH LOOP
    // ==========================================
    function startAutoRefreshLoop() {
        fetchBuses();
        fetchDashboard();
        fetchStorageMetrics();

        state.timerId = setInterval(() => {
            fetchBuses();
            if (state.currentView === "dashboard") {
                fetchDashboard();
            } else if (state.currentView === "storage") {
                fetchStorageMetrics();
            }
        }, state.autoRefreshInterval * 1000);
    }

    // ==========================================
    // 18. TOAST NOTIFICATIONS & UTILITIES
    // ==========================================
    function showToast(message, type = "info") {
        const toast = document.createElement("div");
        toast.className = `toast toast-${type}`;
        const iconClass = type === "success" ? "fa-circle-check" : (type === "error" ? "fa-circle-exclamation" : "fa-circle-info");
        toast.innerHTML = `<i class="fa-solid ${iconClass}"></i> <span>${escapeHtml(message)}</span>`;
        elements.toastContainer.appendChild(toast);

        setTimeout(() => toast.classList.add("visible"), 10);
        setTimeout(() => {
            toast.classList.remove("visible");
            setTimeout(() => toast.remove(), 300);
        }, 3500);
    }

    function roundCoord(val) {
        return Math.round(parseFloat(val) * 1000000) / 1000000;
    }

    function escapeHtml(str) {
        if (!str) return "";
        return String(str)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    // ==========================================
    // 19. INITIALIZE APPLICATION
    // ==========================================
    initMap();
    checkAuthSession();
    fetchCollegeConfig();
    fetchRoutes();
    setupEventListeners();
    setupRegisterBusForm();
    setupRouteGeocoding();
    setupCollegeSettingsForm();
    setupStorageControls();
    setupSecurityForms();
    startAutoRefreshLoop();

    // Default View: Dashboard
    switchView("dashboard");
});
