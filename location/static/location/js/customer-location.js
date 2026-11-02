document.addEventListener("DOMContentLoaded", () => {
    const mapEl = document.getElementById("customerLocationMap");
    if (!mapEl) return;

    const feedbackEl = document.getElementById("gpsFeedback");
    const latInput = document.getElementById("custLatitude");
    const lonInput = document.getElementById("custLongitude");
    const addrLineInput = document.getElementById("custAddressLine");
    const fullAddrInput = document.getElementById("custFullAddress");
    const cityInput = document.getElementById("custCity");
    const stateInput = document.getElementById("custState");
    const pinInput = document.getElementById("custPincode");

    const fallbackLat = parseFloat(mapEl.dataset.defaultLat) || 17.6868;
    const fallbackLon = parseFloat(mapEl.dataset.defaultLon) || 83.2185;

    const defaultLat = (latInput && parseFloat(latInput.value)) ? parseFloat(latInput.value) : fallbackLat;
    const defaultLon = (lonInput && parseFloat(lonInput.value)) ? parseFloat(lonInput.value) : fallbackLon;

    const mapOptions = {
        defaultCenter: [defaultLat, defaultLon],
        defaultZoom: 14,
    };
    if (mapEl.dataset.tileUrl) {
        mapOptions.tileUrl = mapEl.dataset.tileUrl;
    }

    const mapManager = new FoodExMap("customerLocationMap", mapOptions);
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

        mapManager.addMarker("custPin", "picker", lat, lon, "Your Doorstep", "Drag to adjust location", true, (newLat, newLon) => {
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
                    if (addrLineInput && (!addrLineInput.value || addrLineInput.value.startsWith("Location"))) {
                        addrLineInput.value = road || data.display_name.split(",")[0];
                    }
                    if (fullAddrInput) fullAddrInput.value = data.display_name || "";
                    if (cityInput && (data.address.city || data.address.town || data.address.village)) {
                        cityInput.value = data.address.city || data.address.town || data.address.village;
                    }
                    if (stateInput && data.address.state) stateInput.value = data.address.state;
                    if (pinInput && data.address.postcode) pinInput.value = data.address.postcode;
                    setFeedback("✓ Location detected & address updated", "success");
                } else {
                    setFeedback("✓ Location updated", "success");
                }
            })
            .catch(() => {
                setFeedback("✓ Location detected (manual address entry)", "success");
            });
        }
    }

    // Initialize marker
    updateMarkerAndFields(defaultLat, defaultLon, false);

    // GPS Button Click
    const btnGps = document.getElementById("btnDetectGps");
    if (btnGps) {
        btnGps.addEventListener("click", () => {
            setFeedback("⏳ Detecting current location...", "loading");
            gpsManager.getCurrentLocation(
                (pos) => {
                    const lat = pos.coords.latitude;
                    const lon = pos.coords.longitude;
                    updateMarkerAndFields(lat, lon, true);
                },
                (errMsg) => {
                    setFeedback("⚠ " + errMsg, "error");
                }
            );
        });
    }

    // Save Profile Location
    const profileForm = document.getElementById("profileLocationForm");
    if (profileForm) {
        profileForm.addEventListener("submit", (e) => {
            e.preventDefault();
            const csrfToken = typeof getCookie === "function" ? getCookie("csrftoken") : "";
            fetch("/api/location/customer/update/", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrfToken,
                },
                body: JSON.stringify({
                    latitude: latInput ? latInput.value : "",
                    longitude: lonInput ? lonInput.value : "",
                })
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    alert("Location preferences saved successfully!");
                } else {
                    alert(data.message || "Failed to save location.");
                }
            });
        });
    }

    // Save New Address
    const addressForm = document.getElementById("newAddressForm");
    if (addressForm) {
        addressForm.addEventListener("submit", (e) => {
            e.preventDefault();
            const csrfToken = typeof getCookie === "function" ? getCookie("csrftoken") : "";
            const nameEl = document.getElementById("newAddrName");
            const textEl = document.getElementById("newAddrText");
            fetch("/api/location/customer/addresses/", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrfToken,
                },
                body: JSON.stringify({
                    name: nameEl ? nameEl.value : "Home",
                    address: textEl ? textEl.value : "",
                    latitude: latInput ? latInput.value : "",
                    longitude: lonInput ? lonInput.value : "",
                    city: cityInput ? cityInput.value : "",
                    state: stateInput ? stateInput.value : "",
                    pincode: pinInput ? pinInput.value : "",
                })
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    location.reload();
                } else {
                    alert(data.message || "Failed to save address.");
                }
            });
        });
    }

    // Delete Address
    document.querySelectorAll(".btn-delete-address").forEach(btn => {
        btn.addEventListener("click", () => {
            const id = btn.dataset.id;
            const csrfToken = typeof getCookie === "function" ? getCookie("csrftoken") : "";
            fetch(`/api/location/customer/addresses/${id}/`, {
                method: "DELETE",
                headers: { "X-CSRFToken": csrfToken }
            }).then(() => location.reload());
        });
    });
});

