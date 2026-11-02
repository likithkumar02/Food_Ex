document.addEventListener("DOMContentLoaded", () => {
    const mapEl = document.getElementById("restaurantMap");
    if (!mapEl) return;

    const feedbackEl = document.getElementById("gpsFeedback");
    const latInput = document.getElementById("restLat");
    const lonInput = document.getElementById("restLon");
    const addrLineInput = document.getElementById("restAddressLine");
    const addrInput = document.getElementById("restAddress");
    const cityInput = document.getElementById("restCity");
    const stateInput = document.getElementById("restState");
    const pinInput = document.getElementById("restPincode");

    const fallbackLat = parseFloat(mapEl.dataset.defaultLat) || 17.6868;
    const fallbackLon = parseFloat(mapEl.dataset.defaultLon) || 83.2185;
    const restaurantName = mapEl.dataset.restaurantName || "Restaurant";

    const defaultLat = (latInput && parseFloat(latInput.value)) ? parseFloat(latInput.value) : fallbackLat;
    const defaultLon = (lonInput && parseFloat(lonInput.value)) ? parseFloat(lonInput.value) : fallbackLon;

    const mapOptions = {
        defaultCenter: [defaultLat, defaultLon],
        defaultZoom: 14,
    };
    if (mapEl.dataset.tileUrl) {
        mapOptions.tileUrl = mapEl.dataset.tileUrl;
    }

    const mapManager = new FoodExMap("restaurantMap", mapOptions);
    const gpsManager = new GPSLocationManager();

    function setFeedback(msg, type) {
        if (!feedbackEl) return;
        feedbackEl.className = `gps-feedback status-${type}`;
        feedbackEl.textContent = msg;
        feedbackEl.classList.remove("d-none");
    }

    function updateMarkerAndFields(lat, lon, reverse = true) {
        if (latInput) latInput.value = parseFloat(lat).toFixed(6);
        if (lonInput) lonInput.value = parseFloat(lon).toFixed(6);

        mapManager.addMarker("restPin", "restaurant", lat, lon, restaurantName, "Drag to adjust position", true, (newLat, newLon) => {
            updateMarkerAndFields(newLat, newLon, true);
        });
        mapManager.setCenter(lat, lon, 15);

        if (reverse) {
            setFeedback("Fetching address details...", "loading");
            fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lon}&zoom=18&addressdetails=1`, {
                headers: { "Accept": "application/json" }
            })
            .then(res => res.json())
            .then(data => {
                if (data && data.address) {
                    const road = data.address.road || data.address.suburb || data.address.neighbourhood || "";
                    if (addrLineInput && !addrLineInput.value) {
                        addrLineInput.value = road || data.display_name.split(",")[0];
                    }
                    if (addrInput && !addrInput.value) {
                        addrInput.value = data.display_name;
                    }
                    if (cityInput && (data.address.city || data.address.town || data.address.village)) {
                        cityInput.value = data.address.city || data.address.town || data.address.village;
                    }
                    if (stateInput && data.address.state) stateInput.value = data.address.state;
                    if (pinInput && data.address.postcode) pinInput.value = data.address.postcode;
                    setFeedback("✓ Location updated", "success");
                }
            })
            .catch(() => {
                setFeedback("✓ Position updated", "success");
            });
        }
    }

    // Initialize marker
    updateMarkerAndFields(defaultLat, defaultLon, false);

    // Detect GPS
    const btnGps = document.getElementById("btnDetectGps");
    if (btnGps) {
        btnGps.addEventListener("click", () => {
            setFeedback("⏳ Detecting current location...", "loading");
            gpsManager.getCurrentLocation(
                (pos) => {
                    updateMarkerAndFields(pos.coords.latitude, pos.coords.longitude, true);
                },
                (errMsg) => {
                    setFeedback("⚠ " + errMsg, "error");
                }
            );
        });
    }

    // Save location
    const form = document.getElementById("restaurantLocationForm");
    if (form) {
        form.addEventListener("submit", (e) => {
            e.preventDefault();
            const csrfToken = typeof getCookie === "function" ? getCookie("csrftoken") : "";
            fetch("/api/location/restaurant/update/", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrfToken,
                },
                body: JSON.stringify({
                    latitude: latInput ? latInput.value : "",
                    longitude: lonInput ? lonInput.value : "",
                    address_line: addrLineInput ? addrLineInput.value : "",
                    address: addrInput ? addrInput.value : "",
                    city: cityInput ? cityInput.value : "",
                    state: stateInput ? stateInput.value : "",
                    pincode: pinInput ? pinInput.value : "",
                })
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    alert("Restaurant location saved successfully!");
                    location.reload();
                } else {
                    alert(data.message || "Failed to save location.");
                }
            });
        });
    }
});

