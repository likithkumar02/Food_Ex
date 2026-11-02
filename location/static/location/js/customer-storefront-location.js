document.addEventListener("DOMContentLoaded", () => {
    const btnAutoDetect = document.getElementById("btnAutoDetectLocation");
    const spinner = document.getElementById("gpsDetectSpinner");
    const statusText = document.getElementById("locationStatusText");
    const labelEl = document.getElementById("currentDeliveryLabel");

    const urlParams = new URLSearchParams(window.location.search);
    const hasLocationParam = urlParams.has("state") || urlParams.has("district") || urlParams.has("city") || urlParams.has("lat");

    function setDetecting(isDetecting) {
        if (spinner) {
            if (isDetecting) spinner.classList.remove("d-none");
            else spinner.classList.add("d-none");
        }
        if (btnAutoDetect) {
            btnAutoDetect.disabled = isDetecting;
        }
    }

    async function handleCoords(lat, lon, isManual) {
        setDetecting(true);
        if (statusText) statusText.textContent = "Detecting address, state & district...";

        try {
            const res = await fetch(`/api/location/detect/?lat=${lat}&lon=${lon}`);
            const data = await res.json();

            if (data.success) {
                if (labelEl) {
                    const dispArea = data.area || data.city || data.district || "";
                    const dispDist = (data.district && data.district !== dispArea) ? data.district : "";
                    const parts = [dispArea, dispDist, data.state].filter(Boolean);
                    labelEl.textContent = parts.join(", ") || "Location Detected";
                }

                if (statusText) statusText.textContent = `Filtering nearby restaurants in ${data.district || data.city || ''}, ${data.state}...`;

                // Update URL params and reload to show filtered restaurants
                const params = new URLSearchParams(window.location.search);
                if (data.state) params.set("state", data.state);
                if (data.district) params.set("district", data.district);
                if (data.city && !data.district) params.set("city", data.city);
                params.set("lat", lat.toFixed(6));
                params.set("lon", lon.toFixed(6));

                // Save to sessionStorage
                sessionStorage.setItem("foodex_auto_lat", lat);
                sessionStorage.setItem("foodex_auto_lon", lon);
                sessionStorage.setItem("foodex_auto_state", data.state || "");
                sessionStorage.setItem("foodex_auto_district", data.district || "");

                window.location.search = params.toString();
            } else {
                if (statusText) statusText.textContent = data.message || "Failed to identify address.";
                setDetecting(false);
            }
        } catch (err) {
            console.warn("Location detection error:", err);
            if (statusText) statusText.textContent = "Could not reach location service.";
            setDetecting(false);
        }
    }

    function detectLocation(isManual = false) {
        if (!navigator.geolocation) {
            if (statusText) statusText.textContent = "Geolocation is not supported by your browser.";
            return;
        }

        setDetecting(true);
        if (statusText) statusText.textContent = "📍 Requesting your GPS coordinates...";

        navigator.geolocation.getCurrentPosition(
            (pos) => {
                handleCoords(pos.coords.latitude, pos.coords.longitude, isManual);
            },
            (err) => {
                setDetecting(false);
                let msg = "Location permission denied.";
                if (err.code === 2) msg = "Location position unavailable.";
                if (err.code === 3) msg = "Location request timed out.";
                if (statusText) statusText.textContent = `${msg} You can browse all restaurants below.`;
                if (!hasLocationParam && labelEl) {
                    labelEl.textContent = "Browse all locations";
                }
            },
            {
                enableHighAccuracy: true,
                timeout: 8000,
                maximumAge: 60000,
            }
        );
    }

    // Attach click handler for manual detection
    if (btnAutoDetect) {
        btnAutoDetect.addEventListener("click", () => detectLocation(true));
    }

    // Automatic detection on first visit if no location is specified in URL
    if (!hasLocationParam && !sessionStorage.getItem("foodex_geo_attempted")) {
        sessionStorage.setItem("foodex_geo_attempted", "true");
        detectLocation(false);
    }
});

