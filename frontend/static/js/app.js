/**
 * SmartBus Live Fleet Tracking System - Client Application JavaScript
 * Full-Stack 10-Section Navigation, Live GPS, 300 MB Storage Optimization & 7-Day History
 * Enterprise Edition - Fully Responsive & Modular
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
        collegeMarker: null,
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

    // Temporary storage for intermediate stops during route creation
    let currentNewRouteStops = [];
    let confirmedOriginCoords = null;
    let confirmedDestCoords = null;
    let loadedStorageRecords = [];
    let pendingDeleteItems = [];

    // Helper debounce utility
    function debounce(fn, delay = 250) {
        let timer = null;
        return function (...args) {
            clearTimeout(timer);
            timer = setTimeout(() => fn.apply(this, args), delay);
        };
    }

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
        btnDashboardToMap: document.getElementById("btnDashboardToMap"),
        cardNavBuses: document.getElementById("cardNavBuses"),
        cardNavMap: document.getElementById("cardNavMap"),
        cardNavRoutes: document.getElementById("cardNavRoutes"),
        cardNavStorage: document.getElementById("cardNavStorage"),

        // View 2: Live Tracking
        mobileTabBusesBtn: document.getElementById("mobileTabBusesBtn"),
        mobileTabMapBtn: document.getElementById("mobileTabMapBtn"),
        mobileBusCount: document.getElementById("mobileBusCount"),
        busSelectorPanel: document.getElementById("busSelectorPanel"),
        liveMapPanel: document.getElementById("liveMapPanel"),
        mapEmptyStateOverlay: document.getElementById("mapEmptyStateOverlay"),
        busSearchInput: document.getElementById("busSearchInput"),
        clearSearchBtn: document.getElementById("clearSearchBtn"),
        statusTabBtns: document.querySelectorAll(".status-tab-btn[data-filter]"),
        countAllBuses: document.getElementById("countAllBuses"),
        countRunningBuses: document.getElementById("countRunningBuses"),
        countReachedCollegeBuses: document.getElementById("countReachedCollegeBuses"),
        countOfflineBuses: document.getElementById("countOfflineBuses"),
        busesListContainer: document.getElementById("busesListContainer"),
        footerTotalCount: document.getElementById("footerTotalCount"),
        selectorCollegeTitle: document.getElementById("selectorCollegeTitle"),

        // Telemetry HUD
        telemetryHudCard: document.getElementById("telemetryHudCard"),
        hudBusName: document.getElementById("hudBusName"),
        hudBusNumber: document.getElementById("hudBusNumber"),
        hudEspTag: document.getElementById("hudEspTag"),
        hudEspVal: document.getElementById("hudEspVal"),
        hudConnectionBadge: document.getElementById("hudConnectionBadge"),
        btnModeLive: document.getElementById("btnModeLive"),
        btnModeHistory: document.getElementById("btnModeHistory"),
        liveTelemetrySection: document.getElementById("liveTelemetrySection"),
        hudCoordsVal: document.getElementById("hudCoordsVal"),
        hudCopyCoordsBtn: document.getElementById("hudCopyCoordsBtn"),
        hudGoogleMapsLink: document.getElementById("hudGoogleMapsLink"),
        hudTripDistVal: document.getElementById("hudTripDistVal"),
        hudTripStatusSub: document.getElementById("hudTripStatusSub"),
        hudDailyDistVal: document.getElementById("hudDailyDistVal"),
        hudRemainingDistVal: document.getElementById("hudRemainingDistVal"),
        hud7DayDistVal: document.getElementById("hud7DayDistVal"),
        hudSpeedVal: document.getElementById("hudSpeedVal"),
        hudHeadingVal: document.getElementById("hudHeadingVal"),
        hudSatsVal: document.getElementById("hudSatsVal"),
        hudUpdatedVal: document.getElementById("hudUpdatedVal"),
        hudRouteVal: document.getElementById("hudRouteVal"),

        // 7-Day History & Replay
        historyTelemetrySection: document.getElementById("historyTelemetrySection"),
        sevenDayNavPills: document.getElementById("sevenDayNavPills"),
        histDistVal: document.getElementById("histDistVal"),
        histMaxSpeedVal: document.getElementById("histMaxSpeedVal"),
        histStopsVal: document.getElementById("histStopsVal"),
        histPointsVal: document.getElementById("histPointsVal"),
        replayPlayPauseBtn: document.getElementById("replayPlayPauseBtn"),
        replayResetBtn: document.getElementById("replayResetBtn"),
        replayScrubber: document.getElementById("replayScrubber"),
        speedOptBtns: document.querySelectorAll(".speed-opt-btn[data-speed]"),
        replayCurrentTime: document.getElementById("replayCurrentTime"),
        replayCurrentSpeed: document.getElementById("replayCurrentSpeed"),
        replayWaypointProgress: document.getElementById("replayWaypointProgress"),
        centerSelectedBusBtn: document.getElementById("centerSelectedBusBtn"),
        fitAllBusesBtn: document.getElementById("fitAllBusesBtn"),

        // View 3: Fleet Buses
        fleetSearchInput: document.getElementById("fleetSearchInput"),
        fleetStatusTabs: document.querySelectorAll(".status-tab-btn[data-fleet-filter]"),
        fleetCountAll: document.getElementById("fleetCountAll"),
        fleetCountOnline: document.getElementById("fleetCountOnline"),
        fleetCountOffline: document.getElementById("fleetCountOffline"),
        fleetCountMoving: document.getElementById("fleetCountMoving"),
        fleetCountStopped: document.getElementById("fleetCountStopped"),
        fleetTableBody: document.getElementById("fleetTableBody"),
        btnFleetRegisterBus: document.getElementById("btnFleetRegisterBus"),

        // Register Bus Elements
        registerBusModal: document.getElementById("registerBusModal"),
        closeRegisterBusModalBtn: document.getElementById("closeRegisterBusModalBtn"),
        btnCancelRegisterModal: document.getElementById("btnCancelRegisterModal"),
        dedicatedRegisterBusForm: document.getElementById("dedicatedRegisterBusForm"),
        regBusName: document.getElementById("regBusName"),
        regBusId: document.getElementById("regBusId"),
        regBusNumber: document.getElementById("regBusNumber"),
        regDeviceId: document.getElementById("regDeviceId"),
        regDeviceSelect: document.getElementById("regDeviceSelect"),
        regDriverName: document.getElementById("regDriverName"),
        regDriverPhone: document.getElementById("regDriverPhone"),
        regRouteSelect: document.getElementById("regRouteSelect"),
        regCollegeDest: document.getElementById("regCollegeDest"),
        btnResetRegisterForm: document.getElementById("btnResetRegisterForm"),

        // View 4: Route Management
        btnToggleCreateRoute: document.getElementById("btnToggleCreateRoute"),
        routeCreateCard: document.getElementById("routeCreateCard"),
        routeFormTitle: document.getElementById("routeFormTitle"),
        routeForm: document.getElementById("routeForm"),
        routeNameInput: document.getElementById("routeNameInput"),
        routeCodeInput: document.getElementById("routeCodeInput"),
        routeOriginInput: document.getElementById("routeOriginInput"),
        btnGeocodeOrigin: document.getElementById("btnGeocodeOrigin"),
        originSuggestionsBox: document.getElementById("originSuggestionsBox"),
        originConfirmedPill: document.getElementById("originConfirmedPill"),
        originCoordsText: document.getElementById("originCoordsText"),
        routeDestInput: document.getElementById("routeDestInput"),
        btnGeocodeDest: document.getElementById("btnGeocodeDest"),
        destSuggestionsBox: document.getElementById("destSuggestionsBox"),
        destConfirmedPill: document.getElementById("destConfirmedPill"),
        destCoordsText: document.getElementById("destCoordsText"),
        routeStopSearchInput: document.getElementById("routeStopSearchInput"),
        btnAddStopSearch: document.getElementById("btnAddStopSearch"),
        stopSuggestionsBox: document.getElementById("stopSuggestionsBox"),
        selectedStopsList: document.getElementById("selectedStopsList"),
        btnCancelRouteForm: document.getElementById("btnCancelRouteForm"),
        routesCardsGrid: document.getElementById("routesCardsGrid"),

        // View 5: Trip History
        tripHistoryBusSelect: document.getElementById("tripHistoryBusSelect"),
        tripHistoryDateSelect: document.getElementById("tripHistoryDateSelect"),
        tripViewDist: document.getElementById("tripViewDist"),
        tripViewStatus: document.getElementById("tripViewStatus"),
        dailyViewDist: document.getElementById("dailyViewDist"),
        sevenDayViewDist: document.getElementById("sevenDayViewDist"),
        tripCountBadge: document.getElementById("tripCountBadge"),
        tripsTableBody: document.getElementById("tripsTableBody"),

        // View 6: College Settings
        collegeConfigForm: document.getElementById("collegeConfigForm"),
        collegeNameInput: document.getElementById("collegeNameInput"),
        collegeAddressInput: document.getElementById("collegeAddressInput"),
        campusDetailsInput: document.getElementById("campusDetailsInput"),
        collegeRadiusInput: document.getElementById("collegeRadiusInput"),
        collegeLatInput: document.getElementById("collegeLatInput"),
        collegeLngInput: document.getElementById("collegeLngInput"),
        lblCollegeRadius: document.getElementById("lblCollegeRadius"),
        lblCollegeCoords: document.getElementById("lblCollegeCoords"),

        // View 7: Storage Management & Records Explorer
        btnTriggerStorageCleanup: document.getElementById("btnTriggerStorageCleanup"),
        storageHeroUsageText: document.getElementById("storageHeroUsageText"),
        storageHeroBadge: document.getElementById("storageHeroBadge"),
        storageHeroProgressFill: document.getElementById("storageHeroProgressFill"),
        storageRecordsCount: document.getElementById("storageRecordsCount"),
        storageOldestDate: document.getElementById("storageOldestDate"),
        storageLatestDate: document.getElementById("storageLatestDate"),
        storageRetentionStatus: document.getElementById("storageRetentionStatus"),
        storageAvailMb: document.getElementById("storageAvailMb"),
        storageBusFilter: document.getElementById("storageBusFilter"),
        storageDateFilter: document.getElementById("storageDateFilter"),
        btnFilterStorageRecords: document.getElementById("btnFilterStorageRecords"),
        storageRecordsTableBody: document.getElementById("storageRecordsTableBody"),
        chkSelectAllStorageRecords: document.getElementById("chkSelectAllStorageRecords"),
        btnDeleteSelectedRecords: document.getElementById("btnDeleteSelectedRecords"),
        storageDeleteConfirmModal: document.getElementById("storageDeleteConfirmModal"),
        closeDeleteConfirmModalBtn: document.getElementById("closeDeleteConfirmModalBtn"),
        btnConfirmDeleteRecords: document.getElementById("btnConfirmDeleteRecords"),
        btnCancelDeleteRecords: document.getElementById("btnCancelDeleteRecords"),
        deleteRecordsCountText: document.getElementById("deleteRecordsCountText"),
        storageFilesTableBody: document.getElementById("storageFilesTableBody"),

        // Modals
        authLoginModal: document.getElementById("authLoginModal"),
        authLoginForm: document.getElementById("authLoginForm"),
        loginUsername: document.getElementById("loginUsername"),
        loginPassword: document.getElementById("loginPassword"),
        closeAuthModalBtn: document.getElementById("closeAuthModalBtn"),

        editBusModal: document.getElementById("editBusModal"),
        editBusForm: document.getElementById("editBusForm"),
        editBusId: document.getElementById("editBusId"),
        editBusName: document.getElementById("editBusName"),
        editBusNumber: document.getElementById("editBusNumber"),
        editDeviceId: document.getElementById("editDeviceId"),
        editRouteSelect: document.getElementById("editRouteSelect"),
        editDriverName: document.getElementById("editDriverName"),
        editDriverPhone: document.getElementById("editDriverPhone"),
        closeEditBusModalBtn: document.getElementById("closeEditBusModalBtn"),
        btnCancelEditBusModal: document.getElementById("btnCancelEditBusModal"),

        // Toast Container
        toastContainer: document.getElementById("toastContainer")
    };

    // ==========================================
    // 3. MAP INITIALIZATION (Leaflet)
    // ==========================================
    function initMap() {
        const defaultCenter = [17.3156, 78.5833];
        const defaultZoom = 13;

        elements.map = L.map("map", {
            zoomControl: false,
            attributionControl: false
        }).setView(defaultCenter, defaultZoom);

        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
            maxZoom: 19,
            attribution: "&copy; OpenStreetMap contributors"
        }).addTo(elements.map);

        L.control.zoom({ position: "topright" }).addTo(elements.map);

        elements.stopsMarkersGroup = L.layerGroup().addTo(elements.map);

        // Click on map to set College coordinates when in College Settings view
        elements.map.on("click", (e) => {
            if (state.currentView === "college-settings") {
                const lat = roundCoord(e.latlng.lat);
                const lng = roundCoord(e.latlng.lng);
                if (elements.collegeLatInput) elements.collegeLatInput.value = lat;
                if (elements.collegeLngInput) elements.collegeLngInput.value = lng;
                updateCollegeCircle(lat, lng, parseInt(elements.collegeRadiusInput.value || 120));
                showToast(`College coordinates pinned: ${lat}, ${lng}`, "info");
            }
        });
    }

    // Directional Arrow Bus Marker Icon
    function createBusMarkerIcon(bus, isSelected = false) {
        let statusClass = "offline";
        if (bus.is_reached_college) {
            statusClass = "reached_college";
        } else if (bus.is_online) {
            statusClass = bus.is_moving ? "moving" : "stopped";
        }

        const selectedClass = isSelected ? "selected" : "";
        const heading = bus.current_location ? (bus.current_location.heading || 0) : 0;

        const html = `
            <div class="bus-marker-container">
                <div class="bus-marker-pin ${statusClass} ${selectedClass}" style="transform: rotate(${heading}deg);" title="${escapeHtml(bus.bus_name)} (${escapeHtml(bus.bus_number)})">
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
            <div class="history-pin ${pinClass}" title="${escapeHtml(label)}">
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

    // College Geofence Circle & Destination Marker
    function updateCollegeCircle(lat, lng, radiusMeters) {
        if (!elements.map) return;
        if (elements.collegeCircle) {
            elements.map.removeLayer(elements.collegeCircle);
            elements.collegeCircle = null;
        }
        if (elements.collegeMarker) {
            elements.map.removeLayer(elements.collegeMarker);
            elements.collegeMarker = null;
        }

        elements.collegeCircle = L.circle([lat, lng], {
            radius: radiusMeters,
            color: "#2563eb",
            fillColor: "#3b82f6",
            fillOpacity: 0.16,
            weight: 2,
            dashArray: "4, 4"
        }).addTo(elements.map);

        const collegeIcon = L.divIcon({
            className: "college-terminal-marker",
            html: `<div style="background:#1e40af; color:#fff; width:34px; height:34px; border-radius:50%; display:flex; align-items:center; justify-content:center; box-shadow:0 3px 8px rgba(0,0,0,0.3); border:2px solid #fff;"><i class="fa-solid fa-graduation-cap"></i></div>`,
            iconSize: [34, 34],
            iconAnchor: [17, 17]
        });

        const collegeName = state.collegeConfig ? state.collegeConfig.college_name : "College Terminal";
        elements.collegeMarker = L.marker([lat, lng], { icon: collegeIcon })
            .bindTooltip(`<strong>${escapeHtml(collegeName)}</strong><br>Arrival Geofence: ${radiusMeters}m`, { direction: "top" })
            .addTo(elements.map);
    }

    // ==========================================
    // 4. VIEW SWITCHING LOGIC (7 PRIMARY SECTIONS)
    // ==========================================
    function getViewId(viewName) {
        switch (viewName) {
            case "dashboard": return "viewDashboard";
            case "buses": return "viewBuses";
            case "live-tracking": return "viewLiveTracking";
            case "routes": return "viewRouteManagement";
            case "trip-history": return "viewTripHistory";
            case "college-settings": return "viewCollegeSettings";
            case "storage": return "viewStorage";
            default: return "viewDashboard";
        }
    }

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

        // Contextual activation for individual views
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
        } else if (viewName === "storage") {
            fetchStorageMetrics();
            loadStorageRecords();
        }
    }

    // ==========================================
    // 5. DATA FETCHING & SYNCHRONIZATION
    // ==========================================

    // Auto-refresh core fleet buses every 5s
    async function fetchBuses() {
        try {
            const resp = await fetch("/api/buses");
            if (!resp.ok) throw new Error("Failed to fetch buses");
            const data = await resp.json();

            state.buses = data.buses || [];

            updateCounts();
            updateHeaderMetrics(data.metrics || {});
            renderBusesList();
            updateMapMarkers();

            if (state.currentView === "dashboard") {
                renderDashboardMetrics(data.metrics || {});
            } else if (state.currentView === "buses") {
                renderFleetTable();
            }

            // If a bus is selected, update HUD telemetry and distance metrics
            if (state.selectedBusId) {
                const current = state.buses.find(b => b.bus_id === state.selectedBusId);
                if (current) {
                    updateTelemetryHUD(current);
                }
            } else if (state.buses.length > 0) {
                const firstOnline = state.buses.find(b => b.is_online) || state.buses[0];
                selectBus(firstOnline.bus_id, false);
            }

            if (elements.syncStatusLabel) elements.syncStatusLabel.textContent = "Live GPS (5s)";
        } catch (err) {
            console.warn("GPS sync fetch error:", err);
            if (elements.syncStatusLabel) elements.syncStatusLabel.textContent = "Reconnecting...";
        }
    }

    function updateCounts() {
        const total = state.buses.length;
        const online = state.buses.filter(b => b.is_online).length;
        const offline = state.buses.filter(b => !b.is_online).length;
        const moving = state.buses.filter(b => b.is_moving).length;
        const stopped = state.buses.filter(b => b.is_online && !b.is_moving).length;
        const reached = state.buses.filter(b => b.is_reached_college).length;

        if (elements.countAllBuses) elements.countAllBuses.textContent = total;
        if (elements.countRunningBuses) elements.countRunningBuses.textContent = moving;
        if (elements.countReachedCollegeBuses) elements.countReachedCollegeBuses.textContent = reached;
        if (elements.countOfflineBuses) elements.countOfflineBuses.textContent = offline;

        if (elements.fleetCountAll) elements.fleetCountAll.textContent = total;
        if (elements.fleetCountOnline) elements.fleetCountOnline.textContent = online;
        if (elements.fleetCountOffline) elements.fleetCountOffline.textContent = offline;
        if (elements.fleetCountMoving) elements.fleetCountMoving.textContent = moving;
        if (elements.fleetCountStopped) elements.fleetCountStopped.textContent = stopped;

        if (elements.mobileBusCount) elements.mobileBusCount.textContent = total;
        if (elements.footerTotalCount) elements.footerTotalCount.textContent = total;
        if (elements.navBusesCount) elements.navBusesCount.textContent = total;
    }

    function updateHeaderMetrics(metrics) {
        if (elements.headerActiveBusCount) elements.headerActiveBusCount.textContent = metrics.active_buses || 0;
        if (elements.headerTotalBusCount) elements.headerTotalBusCount.textContent = metrics.total_buses || state.buses.length;

        if (metrics.college_name && elements.headerCollegeName) {
            elements.headerCollegeName.textContent = metrics.college_name.toUpperCase();
        }
    }

    // Dashboard Fetch
    async function fetchDashboard() {
        try {
            const resp = await fetch("/api/admin/dashboard");
            if (!resp.ok) return;
            const data = await resp.json();
            const m = data.metrics || data.dashboard;
            if (data.status === "success" && m) {
                renderDashboardMetrics(m);
            }
        } catch (err) {
            console.error("Dashboard error:", err);
        }
    }

    function renderDashboardMetrics(m) {
        if (elements.dashTotalBuses) elements.dashTotalBuses.textContent = m.total_buses || state.buses.length;
        if (elements.dashActiveBuses) elements.dashActiveBuses.textContent = m.active_buses || 0;
        if (elements.dashSendingGps) elements.dashSendingGps.textContent = m.active_buses || 0;
        if (elements.dashRunningBuses) elements.dashRunningBuses.textContent = m.running_buses || 0;
        if (elements.dashReachedCollege) elements.dashReachedCollege.textContent = m.reached_college_buses || 0;
        if (elements.dashOfflineDevices) elements.dashOfflineDevices.textContent = m.offline_devices || 0;
        if (elements.dashTotalRoutes) elements.dashTotalRoutes.textContent = m.total_routes || state.routes.length;
        if (elements.dashCompletedTrips) elements.dashCompletedTrips.textContent = m.completed_trips_today || 0;
        if (elements.dashFleetDistance) elements.dashFleetDistance.textContent = `${(m.total_fleet_distance_today_km || 0.0).toFixed(1)} km`;

        // 300 MB Storage Allocation metrics
        const stor = m.storage || state.storageMetrics;
        if (stor) {
            updateStorageWidgets(stor);
        }
    }

    function updateStorageWidgets(stor) {
        state.storageMetrics = stor;
        const used = stor.total_used_mb !== undefined ? stor.total_used_mb : (stor.used_mb || 0);
        const total = stor.max_storage_mb || stor.max_limit_mb || 300.0;
        const pct = stor.percent_used !== undefined ? stor.percent_used : 0;
        const lvl = stor.warning_level || "NORMAL";

        // Header Pill
        if (elements.headerStorageText) elements.headerStorageText.textContent = `${used.toFixed(2)} / 300 MB`;
        if (elements.headerStorageDot) {
            elements.headerStorageDot.className = `storage-badge-dot ${lvl.toLowerCase().replace(/_/g, "-")}`;
        }

        // Dashboard Card
        if (elements.dashStorageUsed) elements.dashStorageUsed.textContent = `${used.toFixed(2)} MB`;
        if (elements.dashStorageAvailable) elements.dashStorageAvailable.textContent = `${(stor.available_mb || total - used).toFixed(2)} MB`;
        if (elements.dashStoragePercent) elements.dashStoragePercent.textContent = `${pct.toFixed(2)}%`;
        if (elements.dashStorageProgressFill) {
            elements.dashStorageProgressFill.style.width = `${Math.min(pct, 100)}%`;
            elements.dashStorageProgressFill.className = `storage-progress-fill ${lvl.toLowerCase().replace(/_/g, "-")}`;
        }
        if (elements.dashStorageWarningBadge) {
            elements.dashStorageWarningBadge.className = `storage-status-pill ${lvl.toLowerCase().replace(/_/g, "-")}`;
        }
        if (elements.dashStorageStatusText) {
            elements.dashStorageStatusText.textContent = lvl === "NORMAL" ? "Storage Normal (<70%)" : `${lvl} Alert!`;
        }

        // Storage Dedicated View
        if (elements.storageHeroUsageText) elements.storageHeroUsageText.textContent = `${used.toFixed(2)} MB of ${total.toFixed(1)} MB Used`;
        if (elements.storageHeroBadge) {
            elements.storageHeroBadge.className = `storage-warning-badge ${lvl.toLowerCase().replace(/_/g, "-")}`;
            elements.storageHeroBadge.innerHTML = `<i class="fa-solid fa-circle-check"></i> ${lvl} STATUS`;
        }
        if (elements.storageHeroProgressFill) {
            elements.storageHeroProgressFill.style.width = `${Math.min(pct, 100)}%`;
            elements.storageHeroProgressFill.className = `storage-progress-fill ${lvl.toLowerCase().replace(/_/g, "-")}`;
        }
        if (elements.storageRecordsCount) elements.storageRecordsCount.textContent = stor.tracking_records_stored !== undefined ? stor.tracking_records_stored : 0;
        if (elements.storageOldestDate) elements.storageOldestDate.textContent = stor.oldest_tracking_date || "N/A";
        if (elements.storageLatestDate) elements.storageLatestDate.textContent = stor.latest_tracking_date || "N/A";
        if (elements.storageRetentionStatus) elements.storageRetentionStatus.textContent = stor.cleanup_status || "Active 7-Day Window";
        if (elements.storageAvailMb) elements.storageAvailMb.textContent = `${(stor.available_mb || total - used).toFixed(2)} MB`;

        // Populate Bus Filter in Storage Explorer if empty
        if (elements.storageBusFilter && elements.storageBusFilter.options.length <= 1 && state.buses.length > 0) {
            state.buses.forEach(b => {
                const opt = document.createElement("option");
                opt.value = b.bus_id;
                opt.textContent = `${b.bus_id} (${b.bus_name})`;
                elements.storageBusFilter.appendChild(opt);
            });
        }

        const cat = stor.category_breakdown_mb || stor.categories_mb || {};
        if (elements.storageCatDb) elements.storageCatDb.textContent = `${(cat.database || 0).toFixed(2)} MB`;
        if (elements.storageCatTracking) elements.storageCatTracking.textContent = `${(cat.tracking || 0).toFixed(2)} MB`;
        if (elements.storageCatTrips) elements.storageCatTrips.textContent = `${(cat.trips || 0).toFixed(2)} MB`;
        if (elements.storageCatBackups) elements.storageCatBackups.textContent = `${(cat.backups || 0).toFixed(2)} MB`;
        if (elements.storageCatSecurity) elements.storageCatSecurity.textContent = `${(cat.security || 0).toFixed(2)} MB`;

        const fileList = stor.files || stor.files_breakdown || [];
        if (elements.storageFilesTableBody) {
            elements.storageFilesTableBody.innerHTML = fileList.map(f => {
                const sizeKb = f.size_kb !== undefined ? f.size_kb : (f.size_bytes ? f.size_bytes / 1024 : 0);
                const sizeStr = sizeKb > 1024 ? (sizeKb / 1024).toFixed(2) + " MB" : sizeKb.toFixed(1) + " KB";
                return `
                    <tr>
                        <td><code>${escapeHtml(f.name || f.filename)}</code></td>
                        <td><span class="badge badge-info">${escapeHtml(f.category || "General")}</span></td>
                        <td><strong>${sizeStr}</strong></td>
                        <td class="text-muted">${f.modified || "N/A"}</td>
                        <td><span class="badge ${String(f.policy || '').includes('7-Day') ? 'badge-success' : 'badge-secondary'}">${escapeHtml(f.policy || "Permanent")}</span></td>
                    </tr>
                `;
            }).join("");
        }
    }

    // Dashboard Fleet Snapshot Table
    function renderDashFleetTable() {
        if (!elements.dashFleetTableBody) return;
        const snapshot = state.buses.slice(0, 10);
        elements.dashFleetTableBody.innerHTML = snapshot.map(b => {
            const statusClass = b.is_reached_college ? "reached_college" : (b.is_moving ? "moving" : (b.is_online ? "stopped" : "offline"));
            const statusLabel = b.is_reached_college ? "Reached College" : (b.is_moving ? "Running" : (b.is_online ? "Stopped" : "Offline"));
            const dm = b.distance_metrics || {};

            return `
                <tr>
                    <td><span class="status-pill ${statusClass}">${statusLabel}</span></td>
                    <td><strong>${escapeHtml(b.bus_name)}</strong><br><small class="text-muted font-mono">${b.bus_id}</small></td>
                    <td><span class="mono">${escapeHtml(b.bus_number)}</span></td>
                    <td><code>${escapeHtml(b.device_id)}</code></td>
                    <td><strong>${b.current_location ? (b.current_location.speed_kmh || 0).toFixed(1) + " km/h" : "0 km/h"}</strong></td>
                    <td>${b.is_reached_college ? "<span class='text-warning font-bold'>At College Terminal</span>" : (b.is_moving ? "<span class='text-success'>In Transit</span>" : "Idle")}</td>
                    <td><span class="text-primary font-bold">${(dm.trip_distance_km || 0.0).toFixed(1)} km</span></td>
                    <td><span class="text-success font-bold">${(dm.daily_distance_km || 0.0).toFixed(1)} km</span></td>
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
    // 6. LIVE TRACKING BUS SELECTOR & MAP HUD
    // ==========================================

    function getFilteredBuses() {
        const query = (state.searchQuery || "").toLowerCase().trim();
        return state.buses.filter(bus => {
            if (state.activeFilter === "running" && !bus.is_moving) return false;
            if (state.activeFilter === "reached_college" && !bus.is_reached_college) return false;
            if (state.activeFilter === "offline" && bus.is_online) return false;

            if (query) {
                const matchName = (bus.bus_name || "").toLowerCase().includes(query);
                const matchId = (bus.bus_id || "").toLowerCase().includes(query);
                const matchNum = (bus.bus_number || "").toLowerCase().includes(query);
                const matchDev = (bus.device_id || "").toLowerCase().includes(query);
                const matchDriver = (bus.driver_name || "").toLowerCase().includes(query);
                const matchRoute = (bus.route_name || "").toLowerCase().includes(query);
                if (!matchName && !matchId && !matchNum && !matchDev && !matchDriver && !matchRoute) {
                    return false;
                }
            }
            return true;
        });
    }

    function renderBusesList() {
        if (!elements.busesListContainer) return;
        const filtered = getFilteredBuses();

        if (filtered.length === 0) {
            elements.busesListContainer.innerHTML = `
                <div class="empty-state-card" style="padding: 24px; text-align: center; color: var(--text-muted);">
                    <i class="fa-solid fa-bus" style="font-size: 28px; margin-bottom: 8px; opacity: 0.5;"></i>
                    <p>No buses match the filter</p>
                </div>
            `;
            return;
        }

        elements.busesListContainer.innerHTML = filtered.map(b => {
            const isSelected = b.bus_id === state.selectedBusId;
            const statusClass = b.is_reached_college ? "reached_college" : (b.is_moving ? "moving" : (b.is_online ? "stopped" : "offline"));
            const statusLabel = b.is_reached_college ? "Reached College" : (b.is_moving ? "Moving" : (b.is_online ? "Stopped" : "Offline"));
            const dm = b.distance_metrics || {};

            return `
                <div class="bus-select-card ${isSelected ? 'selected' : ''}" data-bus-id="${b.bus_id}">
                    <div class="card-top-row">
                        <strong class="bus-card-title">${escapeHtml(b.bus_name)}</strong>
                        <span class="card-status-badge ${statusClass}">${statusLabel}</span>
                    </div>
                    <div class="card-sub-row">
                        <span class="card-license">${escapeHtml(b.bus_number)}</span>
                        <span class="card-device"><i class="fa-solid fa-microchip"></i> ${escapeHtml(b.device_id)}</span>
                    </div>
                    <div class="card-route-row" title="${escapeHtml(b.route_name)}">
                        <i class="fa-solid fa-route"></i> <span>${escapeHtml(b.route_name)}</span>
                    </div>
                    <div class="card-footer-row">
                        <span><i class="fa-solid fa-user"></i> ${escapeHtml(b.driver_name || "Driver")}</span>
                        <strong class="text-success"><i class="fa-solid fa-gauge-high"></i> ${(dm.daily_distance_km || 0.0).toFixed(1)} km today</strong>
                    </div>
                </div>
            `;
        }).join("");

        // Attach click listeners to cards
        elements.busesListContainer.querySelectorAll(".bus-select-card").forEach(card => {
            card.addEventListener("click", () => {
                const busId = card.dataset.busId;
                selectBus(busId, true);
            });
        });
    }

    function selectBus(busId, shouldCenter = false) {
        state.selectedBusId = busId;

        // Re-render list highlighting
        renderBusesList();

        const bus = state.buses.find(b => b.bus_id === busId);
        if (!bus) return;

        updateTelemetryHUD(bus);
        updateMapMarkers();
        loadAndDisplayRoutePath(bus);

        if (shouldCenter) {
            centerBus(busId);
        }

        // If in 7-day history mode, load records for currently selected date
        if (state.viewMode === "history") {
            loadHistoryForDate(busId, state.selectedDate);
        }
    }

    function centerBus(busId) {
        if (!elements.map) return;
        const bus = state.buses.find(b => b.bus_id === busId);
        if (bus && bus.current_location && bus.current_location.latitude && bus.current_location.longitude) {
            elements.map.setView([bus.current_location.latitude, bus.current_location.longitude], 15, { animate: true });
        }
    }

    function updateMapMarkers() {
        if (!elements.map) return;

        let activeGpsCount = 0;

        state.buses.forEach(b => {
            const loc = b.current_location;
            const hasValidCoord = loc && loc.latitude && loc.longitude && Math.abs(loc.latitude) > 0.0001;

            if (!hasValidCoord) {
                // If a marker previously existed for this bus, remove it
                if (state.busMarkers[b.bus_id]) {
                    elements.map.removeLayer(state.busMarkers[b.bus_id]);
                    delete state.busMarkers[b.bus_id];
                }
                return;
            }

            activeGpsCount++;
            const isSelected = (b.bus_id === state.selectedBusId);
            const latLng = [loc.latitude, loc.longitude];
            const icon = createBusMarkerIcon(b, isSelected);

            if (state.busMarkers[b.bus_id]) {
                state.busMarkers[b.bus_id].setLatLng(latLng);
                state.busMarkers[b.bus_id].setIcon(icon);
            } else {
                const marker = L.marker(latLng, { icon: icon }).addTo(elements.map);
                marker.on("click", () => selectBus(b.bus_id, true));
                state.busMarkers[b.bus_id] = marker;
            }

            // Rich popup displaying: Bus ID, Bus Number, Speed, Heading, Last Update
            const popupHtml = `
                <div class="bus-map-popup">
                    <h4 style="margin:0 0 6px 0; font-size:14px; font-weight:700; color:var(--primary);">${escapeHtml(b.bus_name)} (${escapeHtml(b.bus_id)})</h4>
                    <div style="font-size:12px; line-height:1.6;">
                        <div><strong>Bus Number:</strong> ${escapeHtml(b.bus_number)}</div>
                        <div><strong>ESP Device:</strong> ${escapeHtml(b.device_id || 'N/A')}</div>
                        <div><strong>Speed:</strong> ${(loc.speed_kmh || 0).toFixed(1)} km/h</div>
                        <div><strong>Heading:</strong> ${(loc.heading || 0).toFixed(0)}°</div>
                        <div><strong>Last Update:</strong> ${loc.time ? escapeHtml(loc.time) : (b.last_communication || 'Just now')}</div>
                        <div style="margin-top:4px;"><strong>Status:</strong> <span class="badge ${b.is_moving ? 'badge-success' : 'badge-secondary'}">${b.movement_status || (b.is_moving ? 'Moving' : 'Stopped')}</span></div>
                    </div>
                </div>
            `;
            state.busMarkers[b.bus_id].bindPopup(popupHtml);
            state.busMarkers[b.bus_id].bindTooltip(
                `<strong>${escapeHtml(b.bus_name)}</strong> (${b.bus_id})<br>Speed: ${(loc.speed_kmh || 0).toFixed(1)} km/h`,
                { direction: "top" }
            );
        });

        // Toggle "Waiting for GPS data from ESP devices" empty state overlay
        const emptyOverlay = document.getElementById("mapEmptyStateOverlay");
        if (emptyOverlay) {
            if (activeGpsCount === 0) {
                emptyOverlay.classList.remove("hidden");
            } else {
                emptyOverlay.classList.add("hidden");
            }
        }
    }

    // Telemetry HUD Updating
    function updateTelemetryHUD(bus) {
        if (!elements.hudBusName) return;

        elements.hudBusName.textContent = bus.bus_name;
        elements.hudBusNumber.textContent = bus.bus_number;
        elements.hudEspVal.textContent = bus.device_id;

        let statusClass = "offline";
        let statusLabel = "Offline";
        if (bus.is_reached_college) {
            statusClass = "reached_college";
            statusLabel = "Reached College";
        } else if (bus.is_online) {
            statusClass = bus.is_moving ? "moving" : "stopped";
            statusLabel = bus.is_moving ? "Live Moving" : "Stopped (Idle)";
        }
        elements.hudConnectionBadge.className = `card-status-badge ${statusClass}`;
        elements.hudConnectionBadge.textContent = statusLabel;

        const loc = bus.current_location || {};
        const lat = loc.latitude ? roundCoord(loc.latitude) : "--";
        const lng = loc.longitude ? roundCoord(loc.longitude) : "--";
        elements.hudCoordsVal.textContent = (lat !== "--") ? `${lat}, ${lng}` : "Awaiting GPS Fix";

        if (lat !== "--") {
            elements.hudGoogleMapsLink.href = `https://www.google.com/maps?q=${lat},${lng}`;
            elements.hudGoogleMapsLink.style.display = "inline-flex";
        } else {
            elements.hudGoogleMapsLink.style.display = "none";
        }

        // 3-TIER DISTANCE MEASUREMENT DISPLAY
        const dm = bus.distance_metrics || {};
        elements.hudTripDistVal.textContent = `${(dm.trip_distance_km || 0.0).toFixed(1)} km`;
        elements.hudDailyDistVal.textContent = `${(dm.daily_distance_km || 0.0).toFixed(1)} km`;
        elements.hudRemainingDistVal.textContent = `${(dm.remaining_route_km || 0.0).toFixed(1)} km`;
        elements.hud7DayDistVal.textContent = `${(dm.seven_day_distance_km || 0.0).toFixed(1)} km`;
        elements.hudTripStatusSub.textContent = dm.trip_status ? dm.trip_status : "Current Trip";

        elements.hudSpeedVal.textContent = `${(loc.speed_kmh || 0).toFixed(1)} km/h`;
        const heading = loc.heading || 0;
        elements.hudHeadingVal.textContent = `${heading}° (${getCompassDirection(heading)})`;
        elements.hudSatsVal.textContent = `${loc.satellites || 0} Sats`;
        elements.hudUpdatedVal.textContent = loc.time || "Never";
        elements.hudRouteVal.textContent = bus.route_name;
    }

    // Load and Display Route Polyline & Stops on Map
    async function loadAndDisplayRoutePath(bus) {
        if (!elements.map) return;

        // Clear existing route line & stop markers
        if (state.routePolyline) {
            elements.map.removeLayer(state.routePolyline);
            state.routePolyline = null;
        }
        if (elements.stopsMarkersGroup) {
            elements.stopsMarkersGroup.clearLayers();
        }

        const route = state.routes.find(r => r.route_id === bus.route_id) || state.routes[0];
        if (!route) return;

        const waypoints = route.waypoints || [];
        if (waypoints.length > 0) {
            const latLngs = waypoints.map(w => [w.lat || w.latitude, w.lng || w.longitude]);
            state.routePolyline = L.polyline(latLngs, {
                color: "#2563eb",
                weight: 4,
                opacity: 0.8,
                dashArray: "6, 8"
            }).addTo(elements.map);
        }

        const stops = route.stops || [];
        stops.forEach((stop, idx) => {
            const stopIcon = L.divIcon({
                className: "custom-stop-marker",
                html: `<div style="background:#0284c7; color:#fff; width:22px; height:22px; border-radius:50%; display:flex; align-items:center; justify-content:center; font-size:10px; font-weight:800; border:2px solid #fff; box-shadow:0 2px 4px rgba(0,0,0,0.2);">${idx + 1}</div>`,
                iconSize: [22, 22],
                iconAnchor: [11, 11]
            });
            L.marker([stop.latitude, stop.longitude], { icon: stopIcon })
                .bindTooltip(`<strong>Stop ${idx + 1}: ${escapeHtml(stop.name)}</strong>`, { direction: "top" })
                .addTo(elements.stopsMarkersGroup);
        });
    }

    // ==========================================
    // 7. SEVEN-DAY ROUTE HISTORY & REPLAY SCRUBBER
    // ==========================================

    function render7DayPills() {
        if (!elements.sevenDayNavPills) return;
        const days = [];
        const today = new Date();

        for (let i = 0; i < 7; i++) {
            const d = new Date(today);
            d.setDate(today.getDate() - i);
            const dateStr = d.toISOString().split("T")[0];
            const dayName = i === 0 ? "Today" : d.toLocaleDateString("en-US", { weekday: "short" });
            const dayNum = d.toLocaleDateString("en-US", { day: "2-digit", month: "short" });
            days.push({ date: dateStr, label: `${dayName} (${dayNum})`, isToday: i === 0 });
        }

        state.availableDates = days;
        if (!state.selectedDate) state.selectedDate = days[0].date;

        elements.sevenDayNavPills.innerHTML = days.map(d => `
            <button class="day-pill-btn ${d.date === state.selectedDate ? 'active' : ''}" data-date="${d.date}">
                ${d.label}
            </button>
        `).join("");

        elements.sevenDayNavPills.querySelectorAll(".day-pill-btn").forEach(btn => {
            btn.addEventListener("click", () => {
                state.selectedDate = btn.dataset.date;
                render7DayPills();
                if (state.selectedBusId) {
                    loadHistoryForDate(state.selectedBusId, state.selectedDate);
                }
            });
        });
    }

    async function loadHistoryForDate(busId, dateStr) {
        if (!busId || !dateStr) return;
        try {
            stopReplay();
            clearHistoryLayers();

            const resp = await fetch(`/api/locations/history?bus_id=${encodeURIComponent(busId)}&date=${encodeURIComponent(dateStr)}`);
            if (!resp.ok) throw new Error("History fetch failed");
            const data = await resp.json();

            state.historyRecords = data.records || [];

            // Update Day Summary Box
            if (elements.histPointsVal) elements.histPointsVal.textContent = state.historyRecords.length;
            if (elements.histDistVal) elements.histDistVal.textContent = `${(data.summary ? data.summary.total_distance_km || 0.0 : 0.0).toFixed(1)} km`;
            if (elements.histMaxSpeedVal) elements.histMaxSpeedVal.textContent = `${(data.summary ? data.summary.max_speed_kmh || 0 : 0).toFixed(0)} km/h`;
            if (elements.histStopsVal) elements.histStopsVal.textContent = data.summary ? (data.summary.stop_events_count || 0) : 0;

            if (state.historyRecords.length > 0) {
                drawHistoryPolyline(state.historyRecords);
                initReplayControls(state.historyRecords);
            } else {
                if (elements.replayWaypointProgress) elements.replayWaypointProgress.textContent = "No GPS records for this day";
                if (elements.replayScrubber) {
                    elements.replayScrubber.max = 0;
                    elements.replayScrubber.value = 0;
                }
            }
        } catch (err) {
            console.error("Load history error:", err);
            showToast("Failed to load 7-day history", "error");
        }
    }

    function clearHistoryLayers() {
        if (state.historyPolyline && elements.map) {
            elements.map.removeLayer(state.historyPolyline);
            state.historyPolyline = null;
        }
        state.historyLayers.forEach(l => {
            if (elements.map) elements.map.removeLayer(l);
        });
        state.historyLayers = [];
        if (state.replay.marker && elements.map) {
            elements.map.removeLayer(state.replay.marker);
            state.replay.marker = null;
        }
    }

    function drawHistoryPolyline(records) {
        if (!elements.map || records.length === 0) return;

        const latLngs = records.map(r => [r.latitude, r.longitude]);
        state.historyPolyline = L.polyline(latLngs, {
            color: "#10b981",
            weight: 5,
            opacity: 0.85
        }).addTo(elements.map);

        // Start Pin
        const startPoint = records[0];
        const startMarker = L.marker([startPoint.latitude, startPoint.longitude], {
            icon: createHistoryPinIcon("start", `Trip Start: ${startPoint.time || ""}`)
        }).addTo(elements.map);
        state.historyLayers.push(startMarker);

        // End Pin
        const endPoint = records[records.length - 1];
        const endMarker = L.marker([endPoint.latitude, endPoint.longitude], {
            icon: createHistoryPinIcon("end", `Trip End: ${endPoint.time || ""}`)
        }).addTo(elements.map);
        state.historyLayers.push(endMarker);

        elements.map.fitBounds(state.historyPolyline.getBounds(), { padding: [40, 40] });
    }

    function initReplayControls(records) {
        state.replay.index = 0;
        state.replay.isPlaying = false;
        if (elements.replayScrubber) {
            elements.replayScrubber.max = records.length - 1;
            elements.replayScrubber.value = 0;
        }
        updateReplayScrubberDisplay(0);
    }

    function updateReplayScrubberDisplay(idx) {
        if (!state.historyRecords || state.historyRecords.length === 0) return;
        const pt = state.historyRecords[idx] || state.historyRecords[0];

        if (elements.replayCurrentTime) elements.replayCurrentTime.textContent = pt.time || "--:--";
        if (elements.replayCurrentSpeed) elements.replayCurrentSpeed.textContent = `${(pt.speed_kmh || 0).toFixed(1)} km/h`;
        if (elements.replayWaypointProgress) elements.replayWaypointProgress.textContent = `Point ${idx + 1} / ${state.historyRecords.length}`;
        if (elements.replayScrubber) elements.replayScrubber.value = idx;

        // Position animated bus replay marker
        if (elements.map) {
            const latLng = [pt.latitude, pt.longitude];
            const icon = createReplayMarkerIcon(pt.heading || 0);

            if (state.replay.marker) {
                state.replay.marker.setLatLng(latLng);
                state.replay.marker.setIcon(icon);
            } else {
                state.replay.marker = L.marker(latLng, { icon: icon }).addTo(elements.map);
            }
        }
    }

    function playReplay() {
        if (state.historyRecords.length === 0) return;
        state.replay.isPlaying = true;
        if (elements.replayPlayPauseBtn) {
            elements.replayPlayPauseBtn.innerHTML = `<i class="fa-solid fa-pause"></i>`;
        }

        const interval = Math.max(100, Math.floor(800 / state.replay.speedMultiplier));
        state.replay.timer = setInterval(() => {
            if (state.replay.index >= state.historyRecords.length - 1) {
                stopReplay();
                return;
            }
            state.replay.index++;
            updateReplayScrubberDisplay(state.replay.index);
        }, interval);
    }

    function stopReplay() {
        state.replay.isPlaying = false;
        if (state.replay.timer) {
            clearInterval(state.replay.timer);
            state.replay.timer = null;
        }
        if (elements.replayPlayPauseBtn) {
            elements.replayPlayPauseBtn.innerHTML = `<i class="fa-solid fa-play"></i>`;
        }
    }

    // ==========================================
    // 8. VIEW 3: BUSES (FLEET TABLE & MANAGEMENT)
    // ==========================================

    function renderFleetTable() {
        if (!elements.fleetTableBody) return;
        const query = (state.fleetSearchQuery || "").toLowerCase().trim();

        const filtered = state.buses.filter(b => {
            if (state.fleetFilter === "online" && !b.is_online) return false;
            if (state.fleetFilter === "offline" && b.is_online) return false;
            if (state.fleetFilter === "moving" && !b.is_moving) return false;
            if (state.fleetFilter === "stopped" && (!b.is_online || b.is_moving)) return false;

            if (query) {
                const matchName = (b.bus_name || "").toLowerCase().includes(query);
                const matchId = (b.bus_id || "").toLowerCase().includes(query);
                const matchNum = (b.bus_number || "").toLowerCase().includes(query);
                const matchDev = (b.device_id || "").toLowerCase().includes(query);
                const matchDriver = (b.driver_name || "").toLowerCase().includes(query);
                const matchRoute = (b.route_name || "").toLowerCase().includes(query);
                if (!matchName && !matchId && !matchNum && !matchDev && !matchDriver && !matchRoute) {
                    return false;
                }
            }
            return true;
        });

        if (filtered.length === 0) {
            elements.fleetTableBody.innerHTML = `<tr><td colspan="8" class="text-center text-muted" style="padding:24px;">No buses found for this filter</td></tr>`;
            return;
        }

        elements.fleetTableBody.innerHTML = filtered.map(b => {
            const isOnline = !!b.is_online;
            const isMoving = !!b.is_moving;
            const statusClass = b.is_reached_college ? "reached_college" : (isOnline ? (isMoving ? "moving" : "stopped") : "offline");
            const statusLabel = b.is_reached_college ? "Reached College" : (isOnline ? (isMoving ? "Moving" : "Stopped") : "Offline");

            const hasGps = b.current_location && b.current_location.latitude && b.current_location.longitude && Math.abs(b.current_location.latitude) > 0.0001;
            const gpsBadge = hasGps 
                ? `<span class="badge badge-success"><i class="fa-solid fa-satellite"></i> GPS Available</span>`
                : `<span class="badge badge-warning" style="background:#fef3c7; color:#92400e; border:1px solid #fde68a;"><i class="fa-solid fa-hourglass-half"></i> Waiting for GPS data</span>`;

            const coordsText = hasGps 
                ? `<code class="mono" style="font-size:12px;">${roundCoord(b.current_location.latitude)}, ${roundCoord(b.current_location.longitude)}</code>`
                : `<span class="text-muted" style="font-size:12px;"><i class="fa-solid fa-hourglass-half"></i> Waiting for GPS data</span>`;

            const lastComm = b.last_communication || (b.current_location && b.current_location.time ? b.current_location.time : "Never");

            return `
                <tr>
                    <td><span class="status-pill ${statusClass}">${statusLabel}</span></td>
                    <td><strong class="mono" style="color:var(--primary); font-size:13px;">${escapeHtml(b.bus_id)}</strong><br><span style="font-weight:600;">${escapeHtml(b.bus_name)}</span></td>
                    <td><span class="mono" style="font-weight:600;">${escapeHtml(b.bus_number)}</span></td>
                    <td>
                        <code>${escapeHtml(b.device_id)}</code><br>
                        <span class="badge ${isOnline ? 'badge-success' : 'badge-secondary'}" style="font-size:11px; margin-top:2px;">
                            ${isOnline ? '<i class="fa-solid fa-wifi"></i> Connected' : '<i class="fa-solid fa-plug-circle-xmark"></i> Disconnected'}
                        </span>
                    </td>
                    <td>${gpsBadge}</td>
                    <td>${coordsText}</td>
                    <td><span class="text-muted font-mono" style="font-size:12px;">${escapeHtml(lastComm)}</span></td>
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

    // Populate dropdowns for registering and editing buses
    function populateRegisterBusDropdowns() {
        if (elements.regRouteSelect) {
            elements.regRouteSelect.innerHTML = state.routes.map(r => `
                <option value="${r.route_id}">${escapeHtml(r.route_name)} (${r.route_code || r.route_id})</option>
            `).join("");
        }

        // Fill detected / unassigned devices into dropdown
        if (elements.regDeviceSelect) {
            const unassigned = state.devices.filter(d => !d.assigned_bus_id);
            elements.regDeviceSelect.innerHTML = `
                <option value="">-- Pick Unassigned Device --</option>
                ${unassigned.map(d => `<option value="${d.device_id}">${d.device_id} (${d.device_type})</option>`).join("")}
            `;
        }
    }

    // ==========================================
    // 9. VIEW 5: ROUTE MANAGEMENT & GEOCODING
    // ==========================================

    async function fetchRoutes() {
        try {
            const resp = await fetch("/api/routes");
            if (!resp.ok) return;
            const data = await resp.json();
            state.routes = data.routes || [];
            renderRoutesCards();
            populateRegisterBusDropdowns();
        } catch (err) {
            console.error("Fetch routes error:", err);
        }
    }

    function renderRoutesCards() {
        if (!elements.routesCardsGrid) return;
        if (!state.routes || state.routes.length === 0) {
            elements.routesCardsGrid.innerHTML = `
                <div class="empty-routes-card">
                    <div class="empty-icon"><i class="fa-solid fa-route"></i></div>
                    <h3>No routes created yet.</h3>
                    <p>Create custom transit routes and assign intermediate bus stops to your fleet.</p>
                    <button type="button" class="btn btn-primary btn-sm" id="btnEmptyCreateRoute"><i class="fa-solid fa-plus"></i> Create Route</button>
                </div>
            `;
            const btnEmpty = document.getElementById("btnEmptyCreateRoute");
            if (btnEmpty) {
                btnEmpty.addEventListener("click", () => {
                    if (elements.routeCreateCard) {
                        elements.routeCreateCard.classList.remove("hidden");
                        elements.routeCreateCard.scrollIntoView({ behavior: "smooth" });
                    }
                });
            }
            return;
        }

        elements.routesCardsGrid.innerHTML = state.routes.map(r => {
            const waypointsCount = (r.waypoints || []).length;
            const stopsCount = (r.stops || []).length;
            return `
                <div class="route-card">
                    <div class="route-card-header">
                        <span class="route-title">${escapeHtml(r.route_name)}</span>
                        <span class="route-code-badge">${escapeHtml(r.route_code || r.route_id)}</span>
                    </div>
                    <div class="route-path-flow">
                        <div class="route-path-step"><i class="fa-solid fa-circle-dot text-primary"></i> Origin: ${escapeHtml(r.origin_name || "Transit Terminal")}</div>
                        <div class="route-path-step"><i class="fa-solid fa-map-pin text-info"></i> Intermediate Stops: <strong>${stopsCount} stops</strong></div>
                        <div class="route-path-step"><i class="fa-solid fa-graduation-cap text-success"></i> Destination: ${escapeHtml(r.destination_name || "Campus Terminal")}</div>
                    </div>
                    <div class="route-card-footer">
                        <span class="text-muted"><i class="fa-solid fa-route"></i> ${waypointsCount} waypoints</span>
                        <span class="badge badge-info">${(r.total_distance_km || 0.0).toFixed(1)} km</span>
                    </div>
                </div>
            `;
        }).join("");
    }

    // Geocoding Search (debounced location autocomplete)
    async function searchGeocodeLocation(query, suggestionsBox, onSelectCallback) {
        if (!query || query.length < 2) {
            suggestionsBox.classList.add("hidden");
            return;
        }
        try {
            suggestionsBox.innerHTML = `<div class="geocoding-item text-muted"><i class="fa-solid fa-spinner fa-spin"></i> Searching locations...</div>`;
            suggestionsBox.classList.remove("hidden");

            const resp = await fetch(`/api/routes/geocode?q=${encodeURIComponent(query)}`);
            if (!resp.ok) throw new Error("Geocoding failed");
            const data = await resp.json();
            const results = Array.isArray(data) ? data : (data.suggestions || data.results || []);

            if (!results || results.length === 0) {
                suggestionsBox.innerHTML = `<div class="geocoding-item text-muted">No locations found for "${escapeHtml(query)}"</div>`;
                return;
            }

            suggestionsBox.innerHTML = results.slice(0, 5).map(res => {
                const lat = res.lat || res.latitude;
                const lon = res.lon || res.lng || res.longitude;
                const name = res.display_name || res.name || query;
                const mainName = name.split(",")[0];
                return `
                    <div class="geocoding-item" data-lat="${lat}" data-lng="${lon}" data-name="${escapeHtml(name)}">
                        <i class="fa-solid fa-location-dot" style="color:var(--primary); margin-right:6px;"></i> <strong>${escapeHtml(mainName)}</strong><br>
                        <small class="text-muted" style="font-size:11px;">${escapeHtml(name)}</small>
                    </div>
                `;
            }).join("");

            suggestionsBox.querySelectorAll(".geocoding-item").forEach(item => {
                item.addEventListener("click", () => {
                    const lat = parseFloat(item.dataset.lat);
                    const lng = parseFloat(item.dataset.lng);
                    const name = item.dataset.name;
                    suggestionsBox.classList.add("hidden");
                    onSelectCallback(lat, lng, name);
                });
            });
        } catch (err) {
            console.error("Geocoding error:", err);
            suggestionsBox.innerHTML = `<div class="geocoding-item text-danger">Search error</div>`;
        }
    }
        } catch (err) {
            console.error("Geocoding error:", err);
            suggestionsBox.classList.add("hidden");
        }
    }

    // ==========================================
    // 10. VIEW 6: TRIP HISTORY (2-4 DAILY TRIPS)
    // ==========================================

    async function loadTripHistoryView() {
        if (elements.tripHistoryBusSelect) {
            elements.tripHistoryBusSelect.innerHTML = state.buses.map(b => `
                <option value="${b.bus_id}" ${b.bus_id === state.selectedTripBusId ? "selected" : ""}>
                    ${escapeHtml(b.bus_name)} (${b.bus_id})
                </option>
            `).join("");
        }

        // Fill date selector with rolling 7 days
        if (elements.tripHistoryDateSelect) {
            const today = new Date();
            const dateOpts = [];
            for (let i = 0; i < 7; i++) {
                const d = new Date(today);
                d.setDate(today.getDate() - i);
                const dateStr = d.toISOString().split("T")[0];
                const label = i === 0 ? `Today (${dateStr})` : `${d.toLocaleDateString("en-US", { weekday: "short" })} (${dateStr})`;
                dateOpts.push(`<option value="${dateStr}">${label}</option>`);
            }
            elements.tripHistoryDateSelect.innerHTML = dateOpts.join("");
        }

        const busId = elements.tripHistoryBusSelect.value || (state.buses[0] ? state.buses[0].bus_id : null);
        const dateStr = elements.tripHistoryDateSelect.value || new Date().toISOString().split("T")[0];
        fetchBusTrips(busId, dateStr);
    }

    async function fetchBusTrips(busId, dateStr) {
        if (!busId) return;
        try {
            const resp = await fetch(`/api/buses/${encodeURIComponent(busId)}/trips?date=${encodeURIComponent(dateStr)}`);
            if (!resp.ok) return;
            const data = await resp.json();

            // Distance Summary Cards
            const dists = data.distances || {};
            if (elements.tripViewDist) elements.tripViewDist.textContent = `${(dists.trip_distance_km || 0.0).toFixed(1)} km`;
            if (elements.tripViewStatus) elements.tripViewStatus.textContent = dists.trip_status || "Active / Latest Trip";
            if (elements.dailyViewDist) elements.dailyViewDist.textContent = `${(dists.daily_distance_km || 0.0).toFixed(1)} km`;
            if (elements.sevenDayViewDist) elements.sevenDayViewDist.textContent = `${(dists.seven_day_distance_km || 0.0).toFixed(1)} km`;

            // Trips Table
            const trips = data.trips || [];
            if (elements.tripCountBadge) elements.tripCountBadge.textContent = `${trips.length} Trips Recorded`;

            if (elements.tripsTableBody) {
                if (trips.length === 0) {
                    elements.tripsTableBody.innerHTML = `<tr><td colspan="8" class="text-center text-muted" style="padding:20px;">No trips recorded for this date</td></tr>`;
                    return;
                }

                elements.tripsTableBody.innerHTML = trips.map(t => `
                    <tr>
                        <td><strong>Trip #${t.trip_number || 1}</strong></td>
                        <td>${t.start_time || "N/A"}</td>
                        <td class="font-mono text-muted">${t.start_lat ? roundCoord(t.start_lat) + ", " + roundCoord(t.start_lng) : "N/A"}</td>
                        <td>${t.end_time || (t.status === "COMPLETED" ? t.arrival_time : "In Progress")}</td>
                        <td class="font-mono text-muted">${t.end_lat ? roundCoord(t.end_lat) + ", " + roundCoord(t.end_lng) : (t.status === "COMPLETED" ? "College Terminal" : "In Transit")}</td>
                        <td><strong class="text-primary">${(t.trip_distance_km || 0.0).toFixed(1)} km</strong></td>
                        <td><span class="status-pill ${t.status === 'COMPLETED' ? 'reached_college' : 'moving'}">${t.status}</span></td>
                        <td>${t.arrival_time ? "<strong class='text-success'>" + t.arrival_time + "</strong>" : "<span class='text-muted'>--</span>"}</td>
                    </tr>
                `).join("");
            }
        } catch (err) {
            console.error("Trip fetch error:", err);
        }
    }

    // ==========================================
    // 11. VIEW 7: COLLEGE SETTINGS & GEOFENCE
    // ==========================================

    async function loadCollegeSettingsView() {
        try {
            const resp = await fetch("/api/college");
            if (!resp.ok) return;
            const data = await resp.json();
            if (data.status === "success" && data.college) {
                state.collegeConfig = data.college;
                if (elements.collegeNameInput) elements.collegeNameInput.value = data.college.college_name || "";
                if (elements.collegeAddressInput) elements.collegeAddressInput.value = data.college.college_address || "";
                if (elements.campusDetailsInput) elements.campusDetailsInput.value = data.college.campus_details || "";
                if (elements.collegeRadiusInput) elements.collegeRadiusInput.value = data.college.geofence_radius_meters || 120;
                if (elements.collegeLatInput) elements.collegeLatInput.value = roundCoord(data.college.latitude);
                if (elements.collegeLngInput) elements.collegeLngInput.value = roundCoord(data.college.longitude);

                if (elements.lblCollegeRadius) elements.lblCollegeRadius.textContent = data.college.geofence_radius_meters;
                if (elements.lblCollegeCoords) elements.lblCollegeCoords.textContent = `${roundCoord(data.college.latitude)}, ${roundCoord(data.college.longitude)}`;

                updateCollegeCircle(data.college.latitude, data.college.longitude, data.college.geofence_radius_meters);
            }
        } catch (err) {
            console.error("College config fetch error:", err);
        }
    }

    // ==========================================
    // 12. VIEW 8: DEVICE MANAGEMENT
    // ==========================================

    async function fetchDevices() {
        try {
            const resp = await fetch("/api/devices");
            if (!resp.ok) return;
            const data = await resp.json();
            state.devices = data.devices || [];

            // Summary Pills
            const metrics = data.metrics || {};
            if (elements.devTotalCount) elements.devTotalCount.textContent = data.count || state.devices.length;
            if (elements.devOnlineCount) elements.devOnlineCount.textContent = metrics.online_devices || 0;
            if (elements.devGpsCount) elements.devGpsCount.textContent = state.devices.filter(d => d.gps_status === "valid" || d.is_online).length;
            if (elements.devUnassignedCount) elements.devUnassignedCount.textContent = metrics.unassigned_devices || 0;

            // Unassigned alert
            if (elements.devUnassignedBanner) {
                if (metrics.unassigned_devices > 0) {
                    elements.devUnassignedBanner.classList.remove("hidden");
                } else {
                    elements.devUnassignedBanner.classList.add("hidden");
                }
            }

            // Devices Table
            if (elements.devicesTableViewBody) {
                elements.devicesTableViewBody.innerHTML = state.devices.map(d => {
                    const statusClass = d.is_online ? "moving" : "offline";
                    const statusLabel = d.is_online ? "Online" : "Offline";
                    const platformClass = (d.device_type || "").toLowerCase().includes("esp32") ? "esp32" : "esp8266";

                    const busOptions = state.buses.map(b => `
                        <option value="${b.bus_id}" ${b.bus_id === d.assigned_bus_id ? "selected" : ""}>
                            ${escapeHtml(b.bus_name)} (${b.bus_id})
                        </option>
                    `).join("");

                    return `
                        <tr>
                            <td><span class="status-pill ${statusClass}">${statusLabel}</span></td>
                            <td><strong>${escapeHtml(d.device_name || d.device_id)}</strong><br><small class="mono font-bold">${d.device_id}</small></td>
                            <td><span class="badge-platform ${platformClass}">${escapeHtml(d.device_type || "ESP8266")}</span></td>
                            <td><span class="mono">${escapeHtml(d.mac_address || "N/A")}</span></td>
                            <td><span class="badge-gps ${d.gps_status === 'valid' ? 'active' : 'searching'}">${d.gps_status || "N/A"}</span></td>
                            <td>
                                <select class="device-bus-select" onchange="window.assignDeviceToBus('${d.device_id}', this.value)">
                                    <option value="">-- Unassigned --</option>
                                    ${busOptions}
                                </select>
                            </td>
                            <td>${d.last_seen || "Never"}</td>
                            <td>
                                <button class="btn btn-outline btn-xs" onclick="window.quickMapDevice('${d.device_id}')">
                                    <i class="fa-solid fa-link"></i> Map
                                </button>
                            </td>
                        </tr>
                    `;
                }).join("");
            }
        } catch (err) {
            console.error("Fetch devices error:", err);
        }
    }

    // ==========================================
    // 13. VIEW 9: STORAGE MANAGEMENT & RETENTION
    // ==========================================

    async function fetchStorageMetrics() {
        try {
            const resp = await fetch("/api/admin/storage");
            if (!resp.ok) return;
            const data = await resp.json();
            if (data.status === "success" && data.storage) {
                updateStorageWidgets(data.storage);
            }
        } catch (err) {
            console.error("Fetch storage error:", err);
        }
    }

    async function loadStorageRecords() {
        const busId = elements.storageBusFilter ? elements.storageBusFilter.value : "";
        const date = elements.storageDateFilter ? elements.storageDateFilter.value : "";
        let url = `/api/admin/storage/records?limit=100`;
        if (busId) url += `&bus_id=${encodeURIComponent(busId)}`;
        if (date) url += `&date=${encodeURIComponent(date)}`;

        try {
            if (elements.storageRecordsTableBody) {
                elements.storageRecordsTableBody.innerHTML = `<tr><td colspan="7" class="text-center text-muted" style="padding:20px;"><i class="fa-solid fa-spinner fa-spin"></i> Loading records...</td></tr>`;
            }
            const resp = await fetch(url);
            if (!resp.ok) return;
            const data = await resp.json();
            renderStorageRecordsTable(data.records || []);
        } catch (err) {
            console.error("Storage records fetch error:", err);
            if (elements.storageRecordsTableBody) {
                elements.storageRecordsTableBody.innerHTML = `<tr><td colspan="7" class="text-center text-danger" style="padding:20px;">Failed to load records</td></tr>`;
            }
        }
    }

    function renderStorageRecordsTable(records) {
        loadedStorageRecords = records || [];
        if (!elements.storageRecordsTableBody) return;
        if (elements.chkSelectAllStorageRecords) elements.chkSelectAllStorageRecords.checked = false;

        if (!records || records.length === 0) {
            elements.storageRecordsTableBody.innerHTML = `<tr><td colspan="7" class="text-center text-muted" style="padding:24px;">No tracking records found for the selected filter</td></tr>`;
            return;
        }

        elements.storageRecordsTableBody.innerHTML = records.map((r, idx) => `
            <tr>
                <td style="text-align: center;">
                    <input type="checkbox" class="storage-record-chk" data-index="${idx}" data-bus="${escapeHtml(r.bus_id || '')}" data-date="${escapeHtml(r.date || '')}" data-orig-idx="${r.original_index !== undefined ? r.original_index : idx}">
                </td>
                <td class="font-mono text-muted" style="font-size:12px;">${escapeHtml(r.timestamp || r.time || "N/A")}</td>
                <td><strong class="mono text-primary">${escapeHtml(r.bus_id || "")}</strong></td>
                <td class="font-mono">${r.latitude ? roundCoord(r.latitude) : "--"}</td>
                <td class="font-mono">${r.longitude ? roundCoord(r.longitude) : "--"}</td>
                <td><span class="badge badge-info">${(r.speed_kmh || 0).toFixed(1)} km/h</span></td>
                <td><code>${escapeHtml(r.device_id || "N/A")}</code></td>
            </tr>
        `).join("");
    }

    // ==========================================
    // 14. VIEW 10: SECURITY SETTINGS & AUDIT LOGS
    // ==========================================

    async function fetchSecurityData() {
        try {
            // Fetch users
            const usersResp = await fetch("/api/admin/users");
            if (usersResp.ok) {
                const data = await usersResp.json();
                if (elements.secUsersTableBody) {
                    elements.secUsersTableBody.innerHTML = (data.users || []).map(u => `
                        <tr>
                            <td><strong>${escapeHtml(u.username)}</strong></td>
                            <td><span class="role-tag ${u.role === 'ADMIN' ? 'admin' : 'viewer'}">${u.role}</span></td>
                            <td>${escapeHtml(u.full_name || "N/A")}</td>
                        </tr>
                    `).join("");
                }
            }

            // Fetch audit logs
            const logsResp = await fetch("/api/admin/audit-logs");
            if (logsResp.ok) {
                const logsData = await logsResp.json();
                if (elements.secAuditLogsTableBody) {
                    elements.secAuditLogsTableBody.innerHTML = (logsData.logs || []).slice(0, 25).map(l => `
                        <tr>
                            <td><small>${l.timestamp ? l.timestamp.split("T")[1].slice(0, 8) : "N/A"}</small></td>
                            <td><strong>${escapeHtml(l.username || "system")}</strong></td>
                            <td><span class="role-tag ${l.role === 'ADMIN' ? 'admin' : 'viewer'}">${l.role || "SYSTEM"}</span></td>
                            <td><code>${escapeHtml(l.action)}</code></td>
                            <td>${escapeHtml(l.target || "--")}</td>
                            <td>${escapeHtml(l.details || "")}</td>
                            <td><small class="mono text-muted">${escapeHtml(l.ip_address || "127.0.0.1")}</small></td>
                        </tr>
                    `).join("");
                }
            }
        } catch (err) {
            console.error("Security fetch error:", err);
        }
    }

    // Check user session
    async function checkAuthSession() {
        try {
            const resp = await fetch("/api/auth/session");
            if (!resp.ok) return;
            const data = await resp.json();
            if (data.authenticated && data.user) {
                state.currentUser = data.user;
                if (elements.sessionUsername) elements.sessionUsername.textContent = data.user.username;
                if (elements.sessionRoleTag) {
                    elements.sessionRoleTag.className = `role-tag ${data.user.role.toLowerCase()}`;
                    elements.sessionRoleTag.textContent = data.user.role;
                }
                if (elements.authBtnLabel) elements.authBtnLabel.textContent = "Logout";
                if (elements.secCurrentUsername) elements.secCurrentUsername.textContent = data.user.username;
                if (elements.secCurrentRole) {
                    elements.secCurrentRole.className = `role-tag ${data.user.role.toLowerCase()}`;
                    elements.secCurrentRole.textContent = data.user.role;
                }
            } else {
                state.currentUser = null;
                if (elements.sessionUsername) elements.sessionUsername.textContent = "Guest";
                if (elements.sessionRoleTag) {
                    elements.sessionRoleTag.className = "role-tag viewer";
                    elements.sessionRoleTag.textContent = "VIEWER";
                }
                if (elements.authBtnLabel) elements.authBtnLabel.textContent = "Login";
            }
        } catch (err) {
            console.warn("Auth session check error:", err);
        }
    }

    // ==========================================
    // 15. GLOBAL HELPER FUNCTIONS
    // ==========================================

    function roundCoord(c) {
        return typeof c === "number" ? c.toFixed(6) : c;
    }

    function getCompassDirection(deg) {
        const directions = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];
        return directions[Math.round(deg / 45) % 8];
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

    function showToast(message, type = "info") {
        if (!elements.toastContainer) return;
        const toast = document.createElement("div");
        toast.className = `toast-pill ${type}`;
        const icon = type === "success" ? "fa-circle-check" : (type === "error" ? "fa-circle-exclamation" : "fa-info-circle");
        toast.innerHTML = `<i class="fa-solid ${icon}"></i> <span>${escapeHtml(message)}</span>`;
        elements.toastContainer.appendChild(toast);
        setTimeout(() => {
            toast.style.opacity = "0";
            toast.style.transform = "translateY(10px)";
            setTimeout(() => toast.remove(), 300);
        }, 3200);
    }

    // Window global functions for inline HTML event handlers
    window.trackBusOnMap = function (busId) {
        switchView("live-tracking");
        selectBus(busId, true);
    };

    window.assignDeviceToBus = async function (deviceId, busId) {
        try {
            const resp = await fetch(`/api/devices/${encodeURIComponent(deviceId)}/assign`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ bus_id: busId || null })
            });
            const data = await resp.json();
            if (resp.ok && data.status === "success") {
                showToast(data.message, "success");
                fetchDevices();
                fetchBuses();
            } else {
                showToast(data.message || "Failed to assign device", "error");
            }
        } catch (err) {
            showToast("Device assignment failed", "error");
        }
    };

    window.quickMapDevice = function (deviceId) {
        const bus = prompt(`Enter Bus ID to map device '${deviceId}' (e.g. BUS-01 to BUS-30):`);
        if (bus) {
            window.assignDeviceToBus(deviceId, bus.trim().toUpperCase());
        }
    };

    window.editBusModal = function (busId) {
        const bus = state.buses.find(b => b.bus_id === busId);
        if (!bus) return;

        if (elements.editBusId) elements.editBusId.value = bus.bus_id;
        if (elements.editBusName) elements.editBusName.value = bus.bus_name;
        if (elements.editBusNumber) elements.editBusNumber.value = bus.bus_number;
        if (elements.editDeviceId) elements.editDeviceId.value = bus.device_id;
        if (elements.editDriverName) elements.editDriverName.value = bus.driver_name || "";
        if (elements.editDriverPhone) elements.editDriverPhone.value = bus.driver_phone || "";

        if (elements.editRouteSelect) {
            elements.editRouteSelect.innerHTML = state.routes.map(r => `
                <option value="${r.route_id}" ${r.route_id === bus.route_id ? "selected" : ""}>
                    ${escapeHtml(r.route_name)}
                </option>
            `).join("");
        }

        if (elements.editBusModal) elements.editBusModal.classList.remove("hidden");
    };

    window.deleteBusAction = async function (busId) {
        if (!confirm(`Are you sure you want to delete bus '${busId}'? This action cannot be undone.`)) return;
        try {
            const resp = await fetch(`/api/admin/buses/${encodeURIComponent(busId)}`, {
                method: "DELETE"
            });
            const data = await resp.json();
            if (resp.ok && data.status === "success") {
                showToast(`Bus '${busId}' deleted successfully`, "success");
                fetchBuses();
            } else {
                showToast(data.message || "Failed to delete bus", "error");
            }
        } catch (err) {
            showToast("Delete bus failed", "error");
        }
    };

    // ==========================================
    // 16. EVENT LISTENERS ATTACHMENT
    // ==========================================

    // Top Brand Logo
    if (elements.brandLogoHome) {
        elements.brandLogoHome.addEventListener("click", () => switchView("dashboard"));
    }

    // 10 Primary Nav Buttons
    elements.navButtons.forEach(btn => {
        btn.addEventListener("click", () => {
            const view = btn.dataset.view;
            if (view) switchView(view);
        });
    });

    // Dashboard Quick Buttons & Action Cards
    if (elements.btnDashboardToMap) {
        elements.btnDashboardToMap.addEventListener("click", () => switchView("live-tracking"));
    }
    if (elements.btnViewAllBuses) {
        elements.btnViewAllBuses.addEventListener("click", () => switchView("buses"));
    }
    if (elements.cardNavBuses) {
        elements.cardNavBuses.addEventListener("click", () => switchView("buses"));
    }
    if (elements.cardNavMap) {
        elements.cardNavMap.addEventListener("click", () => switchView("live-tracking"));
    }
    if (elements.cardNavRoutes) {
        elements.cardNavRoutes.addEventListener("click", () => switchView("routes"));
    }
    if (elements.cardNavStorage) {
        elements.cardNavStorage.addEventListener("click", () => switchView("storage"));
    }

    // Register Bus Modal Triggers
    if (elements.btnFleetRegisterBus) {
        elements.btnFleetRegisterBus.addEventListener("click", () => {
            populateRegisterBusDropdowns();
            if (elements.registerBusModal) elements.registerBusModal.classList.remove("hidden");
        });
    }
    if (elements.closeRegisterBusModalBtn) {
        elements.closeRegisterBusModalBtn.addEventListener("click", () => {
            if (elements.registerBusModal) elements.registerBusModal.classList.add("hidden");
        });
    }
    if (elements.btnCancelRegisterModal) {
        elements.btnCancelRegisterModal.addEventListener("click", () => {
            if (elements.registerBusModal) elements.registerBusModal.classList.add("hidden");
        });
    }

    // Live Tracking Bus Search
    if (elements.busSearchInput) {
        elements.busSearchInput.addEventListener("input", (e) => {
            state.searchQuery = e.target.value;
            if (elements.clearSearchBtn) {
                elements.clearSearchBtn.classList.toggle("hidden", !state.searchQuery);
            }
            renderBusesList();
        });
    }

    if (elements.clearSearchBtn) {
        elements.clearSearchBtn.addEventListener("click", () => {
            elements.busSearchInput.value = "";
            state.searchQuery = "";
            elements.clearSearchBtn.classList.add("hidden");
            renderBusesList();
        });
    }

    // Live Tracking Status Tabs (All, Running, College, Offline)
    elements.statusTabBtns.forEach(btn => {
        btn.addEventListener("click", () => {
            elements.statusTabBtns.forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            state.activeFilter = btn.dataset.filter;
            renderBusesList();
        });
    });

    // Fleet Table Search & Tabs
    if (elements.fleetSearchInput) {
        elements.fleetSearchInput.addEventListener("input", (e) => {
            state.fleetSearchQuery = e.target.value;
            renderFleetTable();
        });
    }

    elements.fleetStatusTabs.forEach(btn => {
        btn.addEventListener("click", () => {
            elements.fleetStatusTabs.forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            state.fleetFilter = btn.dataset.fleetFilter;
            renderFleetTable();
        });
    });

    // Mobile View Toggle Tabs (Buses List vs Live Map)
    if (elements.mobileTabBusesBtn && elements.mobileTabMapBtn) {
        elements.mobileTabBusesBtn.addEventListener("click", () => {
            elements.mobileTabBusesBtn.classList.add("active");
            elements.mobileTabMapBtn.classList.remove("active");
            if (elements.busSelectorPanel) elements.busSelectorPanel.classList.remove("mobile-hidden");
            if (elements.liveMapPanel) elements.liveMapPanel.classList.add("mobile-hidden");
        });

        elements.mobileTabMapBtn.addEventListener("click", () => {
            elements.mobileTabMapBtn.classList.add("active");
            elements.mobileTabBusesBtn.classList.remove("active");
            if (elements.busSelectorPanel) elements.busSelectorPanel.classList.add("mobile-hidden");
            if (elements.liveMapPanel) elements.liveMapPanel.classList.remove("mobile-hidden");
            if (elements.map) elements.map.invalidateSize();
        });
    }

    // Copy Coordinates button
    if (elements.hudCopyCoordsBtn) {
        elements.hudCopyCoordsBtn.addEventListener("click", () => {
            const coords = elements.hudCoordsVal.textContent;
            if (coords && coords !== "Awaiting GPS Fix") {
                navigator.clipboard.writeText(coords);
                showToast("GPS Coordinates copied to clipboard", "success");
            }
        });
    }

    // Live Telemetry vs 7-Day History Mode Toggle
    if (elements.btnModeLive && elements.btnModeHistory) {
        elements.btnModeLive.addEventListener("click", () => {
            elements.btnModeLive.classList.add("active");
            elements.btnModeHistory.classList.remove("active");
            state.viewMode = "live";
            if (elements.liveTelemetrySection) elements.liveTelemetrySection.classList.remove("hidden");
            if (elements.historyTelemetrySection) elements.historyTelemetrySection.classList.add("hidden");
            stopReplay();
            clearHistoryLayers();
            updateMapMarkers();
            if (state.selectedBusId) {
                const bus = state.buses.find(b => b.bus_id === state.selectedBusId);
                if (bus) loadAndDisplayRoutePath(bus);
            }
        });

        elements.btnModeHistory.addEventListener("click", () => {
            elements.btnModeHistory.classList.add("active");
            elements.btnModeLive.classList.remove("active");
            state.viewMode = "history";
            if (elements.liveTelemetrySection) elements.liveTelemetrySection.classList.add("hidden");
            if (elements.historyTelemetrySection) elements.historyTelemetrySection.classList.remove("hidden");
            render7DayPills();
            if (state.selectedBusId) {
                loadHistoryForDate(state.selectedBusId, state.selectedDate);
            }
        });
    }

    // Replay Controls
    if (elements.replayPlayPauseBtn) {
        elements.replayPlayPauseBtn.addEventListener("click", () => {
            if (state.replay.isPlaying) {
                stopReplay();
            } else {
                playReplay();
            }
        });
    }

    if (elements.replayResetBtn) {
        elements.replayResetBtn.addEventListener("click", () => {
            stopReplay();
            state.replay.index = 0;
            updateReplayScrubberDisplay(0);
        });
    }

    if (elements.replayScrubber) {
        elements.replayScrubber.addEventListener("input", (e) => {
            const idx = parseInt(e.target.value);
            state.replay.index = idx;
            updateReplayScrubberDisplay(idx);
        });
    }

    elements.speedOptBtns.forEach(btn => {
        btn.addEventListener("click", () => {
            elements.speedOptBtns.forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            state.replay.speedMultiplier = parseFloat(btn.dataset.speed || 1);
            if (state.replay.isPlaying) {
                stopReplay();
                playReplay();
            }
        });
    });

    // Map Center and Fit Buttons
    if (elements.centerSelectedBusBtn) {
        elements.centerSelectedBusBtn.addEventListener("click", () => {
            if (state.selectedBusId) centerBus(state.selectedBusId);
        });
    }

    if (elements.fitAllBusesBtn) {
        elements.fitAllBusesBtn.addEventListener("click", () => {
            if (!elements.map) return;
            const markers = Object.values(state.busMarkers);
            if (markers.length > 0) {
                const group = L.featureGroup(markers);
                elements.map.fitBounds(group.getBounds(), { padding: [50, 50] });
            }
        });
    }

    // Register Bus Form
    if (elements.regDeviceSelect) {
        elements.regDeviceSelect.addEventListener("change", (e) => {
            if (e.target.value && elements.regDeviceId) {
                elements.regDeviceId.value = e.target.value;
            }
        });
    }

    if (elements.dedicatedRegisterBusForm) {
        elements.dedicatedRegisterBusForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            const payload = {
                bus_name: elements.regBusName.value.trim(),
                bus_id: elements.regBusId.value.trim().toUpperCase(),
                bus_number: elements.regBusNumber.value.trim().toUpperCase(),
                device_id: elements.regDeviceId.value.trim().toUpperCase(),
                driver_name: elements.regDriverName.value.trim(),
                driver_phone: elements.regDriverPhone.value.trim(),
                route_id: elements.regRouteSelect.value,
                capacity: 52
            };

            try {
                const resp = await fetch("/api/buses", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload)
                });
                const data = await resp.json();
                if (resp.ok && data.status === "success") {
                    showToast(`Bus '${payload.bus_name}' registered successfully!`, "success");
                    elements.dedicatedRegisterBusForm.reset();
                    fetchBuses();
                    fetchDevices();
                    switchView("buses");
                } else {
                    showToast(data.message || "Failed to register bus", "error");
                }
            } catch (err) {
                showToast("Bus registration error", "error");
            }
        });
    }

    // Edit Bus Form
    if (elements.editBusForm) {
        elements.editBusForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            const busId = elements.editBusId.value;
            const payload = {
                bus_name: elements.editBusName.value.trim(),
                bus_number: elements.editBusNumber.value.trim().toUpperCase(),
                device_id: elements.editDeviceId.value.trim().toUpperCase(),
                route_id: elements.editRouteSelect.value,
                driver_name: elements.editDriverName.value.trim(),
                driver_phone: elements.editDriverPhone.value.trim()
            };

            try {
                const resp = await fetch(`/api/admin/buses/${encodeURIComponent(busId)}`, {
                    method: "PUT",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload)
                });
                const data = await resp.json();
                if (resp.ok && data.status === "success") {
                    showToast("Bus updated successfully!", "success");
                    if (elements.editBusModal) elements.editBusModal.classList.add("hidden");
                    fetchBuses();
                    fetchDevices();
                } else {
                    showToast(data.message || "Failed to update bus", "error");
                }
            } catch (err) {
                showToast("Bus update failed", "error");
            }
        });
    }

    if (elements.closeEditBusModalBtn) {
        elements.closeEditBusModalBtn.addEventListener("click", () => {
            if (elements.editBusModal) elements.editBusModal.classList.add("hidden");
        });
    }
    if (elements.btnCancelEditBusModal) {
        elements.btnCancelEditBusModal.addEventListener("click", () => {
            if (elements.editBusModal) elements.editBusModal.classList.add("hidden");
        });
    }

    // Route Management Geocoding Origin
    if (elements.btnToggleCreateRoute) {
        elements.btnToggleCreateRoute.addEventListener("click", () => {
            if (elements.routeCreateCard) {
                elements.routeCreateCard.classList.toggle("hidden");
            }
        });
    }
    if (elements.btnCancelRouteForm) {
        elements.btnCancelRouteForm.addEventListener("click", () => {
            if (elements.routeCreateCard) elements.routeCreateCard.classList.add("hidden");
        });
    }

    if (elements.btnGeocodeOrigin && elements.routeOriginInput && elements.originSuggestionsBox) {
        elements.btnGeocodeOrigin.addEventListener("click", () => {
            searchGeocodeLocation(elements.routeOriginInput.value.trim(), elements.originSuggestionsBox, (lat, lng, name) => {
                confirmedOriginCoords = { lat, lng };
                elements.routeOriginInput.value = name.split(",")[0];
                if (elements.originConfirmedPill) {
                    elements.originConfirmedPill.classList.remove("hidden");
                    if (elements.originCoordsText) elements.originCoordsText.textContent = `${roundCoord(lat)}, ${roundCoord(lng)}`;
                }
            });
        });
    }

    if (elements.routeOriginInput && elements.originSuggestionsBox) {
        elements.routeOriginInput.addEventListener("input", debounce((e) => {
            searchGeocodeLocation(e.target.value.trim(), elements.originSuggestionsBox, (lat, lng, name) => {
                confirmedOriginCoords = { lat, lng };
                elements.routeOriginInput.value = name.split(",")[0];
                if (elements.originConfirmedPill) {
                    elements.originConfirmedPill.classList.remove("hidden");
                    if (elements.originCoordsText) elements.originCoordsText.textContent = `${roundCoord(lat)}, ${roundCoord(lng)}`;
                }
            });
        }, 250));
    }

    // Destination Autocomplete
    if (elements.btnGeocodeDest && elements.routeDestInput && elements.destSuggestionsBox) {
        elements.btnGeocodeDest.addEventListener("click", () => {
            searchGeocodeLocation(elements.routeDestInput.value.trim(), elements.destSuggestionsBox, (lat, lng, name) => {
                confirmedDestCoords = { lat, lng };
                elements.routeDestInput.value = name.split(",")[0];
                if (elements.destConfirmedPill) {
                    elements.destConfirmedPill.classList.remove("hidden");
                    if (elements.destCoordsText) elements.destCoordsText.textContent = `${roundCoord(lat)}, ${roundCoord(lng)}`;
                }
            });
        });
    }

    if (elements.routeDestInput && elements.destSuggestionsBox) {
        elements.routeDestInput.addEventListener("input", debounce((e) => {
            searchGeocodeLocation(e.target.value.trim(), elements.destSuggestionsBox, (lat, lng, name) => {
                confirmedDestCoords = { lat, lng };
                elements.routeDestInput.value = name.split(",")[0];
                if (elements.destConfirmedPill) {
                    elements.destConfirmedPill.classList.remove("hidden");
                    if (elements.destCoordsText) elements.destCoordsText.textContent = `${roundCoord(lat)}, ${roundCoord(lng)}`;
                }
            });
        }, 250));
    }

    // Route Management Stops Search
    if (elements.btnAddStopSearch && elements.routeStopSearchInput && elements.stopSuggestionsBox) {
        elements.btnAddStopSearch.addEventListener("click", () => {
            searchGeocodeLocation(elements.routeStopSearchInput.value.trim(), elements.stopSuggestionsBox, (lat, lng, name) => {
                const stopName = name.split(",")[0];
                currentNewRouteStops.push({ name: stopName, latitude: lat, longitude: lng });
                renderSelectedStopsList();
                elements.routeStopSearchInput.value = "";
            });
        });
    }

    if (elements.routeStopSearchInput && elements.stopSuggestionsBox) {
        elements.routeStopSearchInput.addEventListener("input", debounce((e) => {
            searchGeocodeLocation(e.target.value.trim(), elements.stopSuggestionsBox, (lat, lng, name) => {
                const stopName = name.split(",")[0];
                currentNewRouteStops.push({ name: stopName, latitude: lat, longitude: lng });
                renderSelectedStopsList();
                elements.routeStopSearchInput.value = "";
            });
        }, 250));
    }

    // Dismiss suggestions on outside click
    document.addEventListener("click", (e) => {
        if (!e.target.closest(".search-input-wrapper")) {
            if (elements.originSuggestionsBox) elements.originSuggestionsBox.classList.add("hidden");
            if (elements.destSuggestionsBox) elements.destSuggestionsBox.classList.add("hidden");
            if (elements.stopSuggestionsBox) elements.stopSuggestionsBox.classList.add("hidden");
        }
    });

    function renderSelectedStopsList() {
        if (!elements.selectedStopsList) return;
        elements.selectedStopsList.innerHTML = currentNewRouteStops.map((s, idx) => `
            <div class="selected-stop-chip" style="display:inline-flex; align-items:center; gap:6px; background:var(--bg-subtle); padding:4px 8px; border-radius:4px; font-size:12px; margin:4px;">
                <span>${idx + 1}. ${escapeHtml(s.name)}</span>
                <button type="button" onclick="window.removeRouteStop(${idx})" style="background:none; border:none; cursor:pointer; color:var(--danger);"><i class="fa-solid fa-xmark"></i></button>
            </div>
        `).join("");
    }

    window.removeRouteStop = function (idx) {
        currentNewRouteStops.splice(idx, 1);
        renderSelectedStopsList();
    };

    // Route Form Submit
    if (elements.routeForm) {
        elements.routeForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            const routeName = elements.routeNameInput.value.trim();
            const routeCode = elements.routeCodeInput ? elements.routeCodeInput.value.trim().toUpperCase() : "";

            const originLat = confirmedOriginCoords ? confirmedOriginCoords.lat : 17.3850;
            const originLng = confirmedOriginCoords ? confirmedOriginCoords.lng : 78.4866;
            const destLat = confirmedDestCoords ? confirmedDestCoords.lat : (state.collegeConfig ? state.collegeConfig.latitude : 17.3156);
            const destLng = confirmedDestCoords ? confirmedDestCoords.lng : (state.collegeConfig ? state.collegeConfig.longitude : 78.5833);
            const destName = elements.routeDestInput ? elements.routeDestInput.value.trim() : "Sphoorthy Engineering College";

            const waypoints = [
                { lat: originLat, lng: originLng },
                ...currentNewRouteStops.map(s => ({ lat: s.latitude, lng: s.longitude })),
                { lat: destLat, lng: destLng }
            ];

            const payload = {
                route_name: routeName,
                route_code: routeCode || `R${state.routes.length + 1}`,
                origin_name: elements.routeOriginInput.value.trim() || "Transit Terminal",
                destination_name: destName || "Sphoorthy Engineering College",
                stops: currentNewRouteStops,
                waypoints: waypoints
            };

            try {
                const resp = await fetch("/api/routes", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload)
                });
                const data = await resp.json();
                if (resp.ok && data.status === "success") {
                    showToast(`Route '${routeName}' created!`, "success");
                    elements.routeForm.reset();
                    currentNewRouteStops = [];
                    confirmedOriginCoords = null;
                    confirmedDestCoords = null;
                    renderSelectedStopsList();
                    if (elements.originConfirmedPill) elements.originConfirmedPill.classList.add("hidden");
                    if (elements.destConfirmedPill) elements.destConfirmedPill.classList.add("hidden");
                    if (elements.routeCreateCard) elements.routeCreateCard.classList.add("hidden");
                    fetchRoutes();
                } else {
                    showToast(data.message || "Route creation failed", "error");
                }
            } catch (err) {
                showToast("Route creation error", "error");
            }
        });
    }

    // Trip History Selectors
    if (elements.tripHistoryBusSelect) {
        elements.tripHistoryBusSelect.addEventListener("change", (e) => {
            state.selectedTripBusId = e.target.value;
            fetchBusTrips(state.selectedTripBusId, elements.tripHistoryDateSelect.value);
        });
    }
    if (elements.tripHistoryDateSelect) {
        elements.tripHistoryDateSelect.addEventListener("change", (e) => {
            const busId = elements.tripHistoryBusSelect.value;
            fetchBusTrips(busId, e.target.value);
        });
    }

    // College Config Form
    if (elements.collegeConfigForm) {
        elements.collegeConfigForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            const payload = {
                college_name: elements.collegeNameInput.value.trim(),
                college_address: elements.collegeAddressInput ? elements.collegeAddressInput.value.trim() : "",
                campus_details: elements.campusDetailsInput ? elements.campusDetailsInput.value.trim() : "",
                geofence_radius_meters: parseInt(elements.collegeRadiusInput.value),
                latitude: parseFloat(elements.collegeLatInput.value),
                longitude: parseFloat(elements.collegeLngInput.value)
            };

            try {
                const resp = await fetch("/api/college", {
                    method: "PUT",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload)
                });
                const data = await resp.json();
                if (resp.ok && data.status === "success") {
                    showToast("College configuration and arrival geofence updated!", "success");
                    state.collegeConfig = data.college;
                    updateCollegeCircle(payload.latitude, payload.longitude, payload.geofence_radius_meters);
                    if (elements.headerCollegeName) elements.headerCollegeName.textContent = payload.college_name.toUpperCase();
                } else {
                    showToast(data.message || "Failed to update college settings", "error");
                }
            } catch (err) {
                showToast("College configuration error", "error");
            }
        });
    }

    // Storage Manual Cleanup Trigger
    if (elements.btnTriggerStorageCleanup) {
        elements.btnTriggerStorageCleanup.addEventListener("click", async () => {
            if (!confirm("Run 7-day rolling data retention cleanup and automated backup now?")) return;
            try {
                const resp = await fetch("/api/admin/storage/cleanup", { method: "POST" });
                const data = await resp.json();
                if (resp.ok && data.status === "success") {
                    showToast("7-day cleanup & backup completed successfully!", "success");
                    fetchStorageMetrics();
                    loadStorageRecords();
                    fetchDashboard();
                } else {
                    showToast(data.message || "Cleanup failed", "error");
                }
            } catch (err) {
                showToast("Cleanup error", "error");
            }
        });
    }

    // Storage Records Explorer Controls
    if (elements.btnFilterStorageRecords) {
        elements.btnFilterStorageRecords.addEventListener("click", () => {
            loadStorageRecords();
        });
    }

    if (elements.chkSelectAllStorageRecords) {
        elements.chkSelectAllStorageRecords.addEventListener("change", (e) => {
            const chks = document.querySelectorAll(".storage-record-chk");
            chks.forEach(c => c.checked = e.target.checked);
        });
    }

    if (elements.btnDeleteSelectedRecords) {
        elements.btnDeleteSelectedRecords.addEventListener("click", () => {
            const selectedChks = document.querySelectorAll(".storage-record-chk:checked");
            if (selectedChks.length === 0) {
                showToast("Please select at least one record to delete", "info");
                return;
            }
            pendingDeleteItems = Array.from(selectedChks).map(c => ({
                bus_id: c.dataset.bus,
                date: c.dataset.date,
                orig_idx: parseInt(c.dataset.origIdx)
            }));

            if (elements.deleteRecordsCountText) elements.deleteRecordsCountText.textContent = pendingDeleteItems.length;
            if (elements.storageDeleteConfirmModal) elements.storageDeleteConfirmModal.classList.remove("hidden");
        });
    }

    if (elements.closeDeleteConfirmModalBtn) {
        elements.closeDeleteConfirmModalBtn.addEventListener("click", () => {
            if (elements.storageDeleteConfirmModal) elements.storageDeleteConfirmModal.classList.add("hidden");
        });
    }
    if (elements.btnCancelDeleteRecords) {
        elements.btnCancelDeleteRecords.addEventListener("click", () => {
            if (elements.storageDeleteConfirmModal) elements.storageDeleteConfirmModal.classList.add("hidden");
        });
    }

    if (elements.btnConfirmDeleteRecords) {
        elements.btnConfirmDeleteRecords.addEventListener("click", async () => {
            if (elements.storageDeleteConfirmModal) elements.storageDeleteConfirmModal.classList.add("hidden");
            if (pendingDeleteItems.length === 0) return;

            const busId = pendingDeleteItems[0].bus_id;
            const date = pendingDeleteItems[0].date;
            const indices = pendingDeleteItems.map(p => p.orig_idx);

            try {
                const resp = await fetch("/api/admin/storage/delete-records", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ bus_id: busId, date: date, indices: indices })
                });
                const data = await resp.json();
                if (resp.ok && data.status === "success") {
                    showToast(data.message || `Deleted ${pendingDeleteItems.length} records`, "success");
                    loadStorageRecords();
                    fetchStorageMetrics();
                } else {
                    showToast(data.message || "Failed to delete records", "error");
                }
            } catch (err) {
                showToast("Delete records error", "error");
            }
        });
    }

    // Security Settings Form
    if (elements.changePasswordForm) {
        elements.changePasswordForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            const username = state.currentUser ? state.currentUser.username : "admin";
            const newPassword = elements.newPassInput.value;

            try {
                const resp = await fetch(`/api/admin/users/${encodeURIComponent(username)}/password`, {
                    method: "PUT",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ password: newPassword })
                });
                const data = await resp.json();
                if (resp.ok && data.status === "success") {
                    showToast("Password updated successfully!", "success");
                    elements.changePasswordForm.reset();
                    fetchSecurityData();
                } else {
                    showToast(data.message || "Failed to change password", "error");
                }
            } catch (err) {
                showToast("Change password error", "error");
            }
        });
    }

    // Create New Authorized User Form
    if (elements.createNewUserForm) {
        elements.createNewUserForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            const payload = {
                username: elements.newUserNameInput.value.trim(),
                role: elements.newUserRoleSelect.value,
                password: elements.newUserPasswordInput.value
            };

            try {
                const resp = await fetch("/api/admin/users", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload)
                });
                const data = await resp.json();
                if (resp.ok && data.status === "success") {
                    showToast(`User '${payload.username}' created!`, "success");
                    elements.createNewUserForm.reset();
                    fetchSecurityData();
                } else {
                    showToast(data.message || "Failed to create user", "error");
                }
            } catch (err) {
                showToast("Create user error", "error");
            }
        });
    }

    // Auth Login Modal & Form
    if (elements.headerAuthBtn) {
        elements.headerAuthBtn.addEventListener("click", () => {
            if (state.currentUser) {
                // If logged in, logout
                fetch("/api/auth/logout", { method: "POST" }).then(() => {
                    showToast("Logged out successfully", "info");
                    checkAuthSession();
                });
            } else {
                if (elements.authLoginModal) elements.authLoginModal.classList.remove("hidden");
            }
        });
    }

    if (elements.closeAuthModalBtn) {
        elements.closeAuthModalBtn.addEventListener("click", () => {
            if (elements.authLoginModal) elements.authLoginModal.classList.add("hidden");
        });
    }

    if (elements.authLoginForm) {
        elements.authLoginForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            const username = elements.loginUsername.value.trim();
            const password = elements.loginPassword.value;

            try {
                const resp = await fetch("/api/auth/login", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ username, password })
                });
                const data = await resp.json();
                if (resp.ok && data.status === "success") {
                    showToast(`Logged in as ${data.user.role}`, "success");
                    if (elements.authLoginModal) elements.authLoginModal.classList.add("hidden");
                    elements.authLoginForm.reset();
                    checkAuthSession();
                } else {
                    showToast(data.message || "Invalid username or password", "error");
                }
            } catch (err) {
                showToast("Authentication failed", "error");
            }
        });
    }

    // ==========================================
    // 17. INITIAL BOOTSTRAP SEQUENCE
    // ==========================================
    async function initApp() {
        initMap();
        await checkAuthSession();
        await fetchRoutes();
        await loadCollegeSettingsView();
        await fetchBuses();
        await fetchDevices();
        await fetchDashboard();

        // Start automatic polling every 5 seconds
        state.timerId = setInterval(() => {
            fetchBuses();
        }, state.autoRefreshInterval * 1000);
    }

    initApp();
});
