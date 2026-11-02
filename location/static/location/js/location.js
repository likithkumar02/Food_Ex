/**
 * Food_Ex Location & GPS Library
 * Provides GPSLocationManager and FoodExMap (Leaflet encapsulation).
 */

class GPSLocationManager {
    constructor(options = {}) {
        this.options = Object.assign({
            enableHighAccuracy: true,
            timeout: 12000,
            maximumAge: 5000,
            minIntervalMs: 5000,
            minDistanceMeters: 10,
        }, options);

        this.watchId = null;
        this.lastPosition = null;
        this.lastUpdateTime = 0;
        this.isTracking = false;
    }

    static isSupported() {
        return "geolocation" in navigator;
    }

    /**
     * Get one-shot current GPS position.
     * @param {Function} onSuccess callback(position)
     * @param {Function} onError callback(errorMessage, errorCode)
     */
    getCurrentLocation(onSuccess, onError) {
        if (!GPSLocationManager.isSupported()) {
            if (onError) onError("Geolocation is not supported by your browser.", "NOT_SUPPORTED");
            return;
        }

        navigator.geolocation.getCurrentPosition(
            (pos) => {
                this.lastPosition = pos;
                if (onSuccess) onSuccess(pos);
            },
            (err) => {
                const message = this._formatError(err);
                if (onError) onError(message, err.code);
            },
            {
                enableHighAccuracy: this.options.enableHighAccuracy,
                timeout: this.options.timeout,
                maximumAge: this.options.maximumAge,
            }
        );
    }

    async sendDeliveryLocation(position, identifiers = {}) {
        const csrfToken = (typeof getCookie === "function" ? getCookie("csrftoken") : "")
            || document.querySelector('input[name="csrfmiddlewaretoken"]')?.value
            || document.querySelector("[data-csrf-token]")?.dataset?.csrfToken
            || "";

        const response = await fetch("/api/location/delivery/update/", {
            method: "POST",
            credentials: "same-origin",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": csrfToken,
            },
            body: JSON.stringify({
                ...identifiers,
                latitude: position.coords.latitude,
                longitude: position.coords.longitude,
                accuracy: position.coords.accuracy,
                speed: position.coords.speed,
                heading: position.coords.heading,
            }),
        });
        const data = await response.json();
        if (!response.ok) {
            const err = new Error(data.message || data.detail || "Unable to update delivery location.");
            err.status = response.status;
            err.data = data;
            throw err;
        }
        return data;
    }

    /**
     * Start continuous GPS tracking via watchPosition.
     * @param {Function} onUpdate callback(position)
     * @param {Function} onError callback(errorMessage, errorCode)
     */
    startTracking(onUpdate, onError) {
        if (!GPSLocationManager.isSupported()) {
            if (onError) onError("Geolocation is not supported by your browser.", "NOT_SUPPORTED");
            return;
        }

        if (this.isTracking) return;
        this.isTracking = true;

        this.watchId = navigator.geolocation.watchPosition(
            (pos) => {
                const now = Date.now();
                // Check throttling: minIntervalMs
                if (now - this.lastUpdateTime < this.options.minIntervalMs) {
                    return;
                }

                // Check distance threshold if previous position exists
                if (this.lastPosition) {
                    const distKm = GPSLocationManager.calculateDistance(
                        this.lastPosition.coords.latitude,
                        this.lastPosition.coords.longitude,
                        pos.coords.latitude,
                        pos.coords.longitude
                    );
                    const distMeters = distKm * 1000;
                    if (distMeters < this.options.minDistanceMeters && (now - this.lastUpdateTime < 30000)) {
                        return;
                    }
                }

                this.lastPosition = pos;
                this.lastUpdateTime = now;
                if (onUpdate) onUpdate(pos);
            },
            (err) => {
                const message = this._formatError(err);
                if (onError) onError(message, err.code);
            },
            {
                enableHighAccuracy: this.options.enableHighAccuracy,
                timeout: this.options.timeout,
                maximumAge: this.options.maximumAge,
            }
        );
    }

    /**
     * Stop continuous GPS tracking.
     */
    stopTracking() {
        if (this.watchId !== null) {
            navigator.geolocation.clearWatch(this.watchId);
            this.watchId = null;
        }
        this.isTracking = false;
    }

    _formatError(err) {
        switch (err.code) {
            case err.PERMISSION_DENIED:
                return "Location permission denied. Please enable location permission in your browser or enter your address manually.";
            case err.POSITION_UNAVAILABLE:
                return "Unable to detect your location. Please check your GPS signal or enter your address manually.";
            case err.TIMEOUT:
                return "Location detection timed out. Please try again or enter your address manually.";
            default:
                return "An error occurred while detecting your location.";
        }
    }

    /**
     * Haversine distance in kilometers.
     */
    static calculateDistance(lat1, lon1, lat2, lon2) {
        if (lat1 == null || lon1 == null || lat2 == null || lon2 == null) return null;
        const R = 6371; // km
        const dLat = (lat2 - lat1) * Math.PI / 180;
        const dLon = (lon2 - lon1) * Math.PI / 180;
        const a =
            Math.sin(dLat / 2) * Math.sin(dLat / 2) +
            Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
            Math.sin(dLon / 2) * Math.sin(dLon / 2);
        const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
        return Math.round(R * c * 100) / 100;
    }
}


class FoodExMap {
    constructor(elementId, options = {}) {
        this.elementId = elementId;
        const container = document.getElementById(elementId);
        const datasetTileUrl = container?.dataset?.tileUrl;
        const datasetAttribution = container?.dataset?.tileAttribution;

        const defaultTileUrl = "https://{s}.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png";
        const defaultAttribution = '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors, Tiles by <a href="https://www.hotosm.org/" target="_blank" rel="noopener">HOT</a>';

        let effectiveTileUrl = options.tileUrl || datasetTileUrl || defaultTileUrl;
        if (effectiveTileUrl.includes("basemaps.cartocdn.com")) {
            effectiveTileUrl = defaultTileUrl;
        }

        this.options = Object.assign({
            defaultCenter: [17.6868, 83.2185],
            defaultZoom: 13,
            tileUrl: effectiveTileUrl,
            fallbackTileUrl: "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
            attribution: options.attribution || datasetAttribution || defaultAttribution,
            subdomains: options.subdomains || "abc",
            zoomControl: true,
        }, options);

        this.map = null;
        this.tileLayer = null;
        this.markers = {};
        this.routeLayer = null;
        this.tileErrorCount = 0;
        this.hasFallenBack = false;
        this.initialize();
    }

    initialize() {
        const container = document.getElementById(this.elementId);
        if (!container || typeof L === "undefined") return;

        this.map = L.map(this.elementId, {
            zoomControl: this.options.zoomControl,
            scrollWheelZoom: false,
        }).setView(this.options.defaultCenter, this.options.defaultZoom);

        this._setupTileLayer(this.options.tileUrl, false);

        // Allow scroll-zoom when clicked
        this.map.on("click", () => {
            this.map.scrollWheelZoom.enable();
        });
    }

    _setupTileLayer(url, isFallback = false) {
        if (this.tileLayer && this.map) {
            this.map.removeLayer(this.tileLayer);
            this.tileLayer = null;
        }

        this.tileLayer = L.tileLayer(url, {
            attribution: this.options.attribution,
            subdomains: this.options.subdomains,
            maxZoom: 19,
        }).addTo(this.map);

        this.tileLayer.on("tileerror", () => {
            this.tileErrorCount++;
            if (this.tileErrorCount >= 4 && !this.hasFallenBack) {
                this.hasFallenBack = true;
                this.tileErrorCount = 0;
                console.warn("[FoodExMap] Primary map tile provider failed. Switching to fallback provider.");
                this._setupTileLayer(this.options.fallbackTileUrl, true);
            } else if (this.tileErrorCount >= 6 && this.hasFallenBack) {
                this._showTileNotice();
            }
        });
    }

    _showTileNotice() {
        const container = document.getElementById(this.elementId);
        if (!container || container.querySelector(".foodex-tile-notice")) return;
        const banner = document.createElement("div");
        banner.className = "foodex-tile-notice";
        banner.style.cssText = "position:absolute;bottom:8px;left:8px;background:rgba(255,255,255,0.92);padding:5px 10px;font-size:12px;border-radius:6px;z-index:999;color:#b91c1c;box-shadow:0 2px 8px rgba(0,0,0,0.15);pointer-events:none;";
        banner.textContent = "Map tiles temporarily unavailable · Live tracking markers remain active";
        container.appendChild(banner);
    }

    _createCustomIcon(type) {
        const iconConfigs = {
            restaurant: { icon: "🍽️", cls: "foodex-marker-restaurant" },
            customer: { icon: "🏠", cls: "foodex-marker-customer" },
            delivery: { icon: "🛵", cls: "foodex-marker-delivery" },
            picker: { icon: "📍", cls: "foodex-marker-picker" },
        };
        const cfg = iconConfigs[type] || { icon: "📍", cls: "foodex-marker-picker" };

        return L.divIcon({
            html: `<div class="foodex-marker-icon ${cfg.cls}">${cfg.icon}</div>`,
            className: "foodex-div-icon",
            iconSize: [44, 44],
            iconAnchor: [22, 22],
            popupAnchor: [0, -24],
        });
    }

    addMarker(key, type, lat, lon, title = "", popupHtml = "", draggable = false, onDragEnd = null) {
        if (!this.map || lat == null || lon == null) return null;

        if (this.markers[key]) {
            this.updateMarker(key, lat, lon);
            return this.markers[key];
        }

        const icon = this._createCustomIcon(type);
        const marker = L.marker([lat, lon], {
            icon: icon,
            title: title,
            draggable: draggable,
        }).addTo(this.map);

        if (popupHtml) {
            marker.bindPopup(popupHtml);
        }

        if (draggable && onDragEnd) {
            marker.on("dragend", (e) => {
                const pos = e.target.getLatLng();
                onDragEnd(pos.lat, pos.lng);
            });
        }

        this.markers[key] = marker;
        return marker;
    }

    updateMarker(key, lat, lon, popupHtml = null) {
        const marker = this.markers[key];
        if (!marker || lat == null || lon == null) return;

        marker.setLatLng([lat, lon]);
        if (popupHtml) {
            marker.setPopupContent(popupHtml);
        }
    }

    removeMarker(key) {
        if (this.markers[key]) {
            this.map.removeLayer(this.markers[key]);
            delete this.markers[key];
        }
    }

    clearMarkers() {
        Object.keys(this.markers).forEach((key) => {
            this.map.removeLayer(this.markers[key]);
        });
        this.markers = {};
    }

    clearRoute() {
        if (this.routeLayer && this.map) {
            this.map.removeLayer(this.routeLayer);
            this.routeLayer = null;
        }
    }

    drawRoute(points, options = {}) {
        if (!this.map) return;
        this.clearRoute();

        if (!points || points.length < 2) return;

        const latLngs = points.map(p => [
            p.latitude != null ? p.latitude : p[0],
            p.longitude != null ? p.longitude : p[1]
        ]);
        const isRoad = options.isRoadRoute !== false && (points.length > 2 || options.isRoadRoute === true);

        const style = Object.assign({
            color: "#e23744",
            weight: isRoad ? 5 : 4,
            opacity: 0.88,
            lineCap: "round",
            lineJoin: "round",
            dashArray: isRoad ? null : "6, 8",
        }, options);

        this.routeLayer = L.polyline(latLngs, style).addTo(this.map);
    }

    fitBounds(pointsOrMarkers) {
        if (!this.map) return;
        let bounds = [];

        if (Array.isArray(pointsOrMarkers) && pointsOrMarkers.length > 0) {
            bounds = pointsOrMarkers.map(p => [p.latitude || p[0], p.longitude || p[1]]);
        } else {
            bounds = Object.values(this.markers).map(m => m.getLatLng());
        }

        if (bounds.length > 0) {
            this.map.fitBounds(bounds, { padding: [40, 40], maxZoom: 16 });
        }
    }

    setCenter(lat, lon, zoom = 14) {
        if (this.map && lat != null && lon != null) {
            this.map.setView([lat, lon], zoom);
        }
    }

    invalidateSize() {
        if (this.map) {
            setTimeout(() => this.map.invalidateSize(), 200);
        }
    }
}

// Utility to read Django CSRF token
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== "") {
        const cookies = document.cookie.split(";");
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + "=")) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    if (!cookieValue && name === "csrftoken") {
        const input = document.querySelector('input[name="csrfmiddlewaretoken"]');
        if (input && input.value) return input.value;
    }
    return cookieValue;
}
