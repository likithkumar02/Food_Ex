document.addEventListener("DOMContentLoaded", () => {
    const mapEl = document.getElementById("deliveryNavigationMap");
    if (!mapEl) return;

    const restLat = mapEl.dataset.restLat ? parseFloat(mapEl.dataset.restLat) : null;
    const restLon = mapEl.dataset.restLon ? parseFloat(mapEl.dataset.restLon) : null;
    const restName = mapEl.dataset.restName || "Pickup Location";
    const restAddr = mapEl.dataset.restAddress || "";

    const custLat = mapEl.dataset.custLat ? parseFloat(mapEl.dataset.custLat) : null;
    const custLon = mapEl.dataset.custLon ? parseFloat(mapEl.dataset.custLon) : null;
    const custAddr = mapEl.dataset.custAddress || "";

    const assignmentId = mapEl.dataset.assignmentId ? parseInt(mapEl.dataset.assignmentId, 10) : null;
    const orderId = mapEl.dataset.orderId ? parseInt(mapEl.dataset.orderId, 10) : null;

    const centerLat = restLat || custLat || 17.6868;
    const centerLon = restLon || custLon || 83.2185;

    const map = new FoodExMap("deliveryNavigationMap", {
        defaultCenter: [centerLat, centerLon],
        defaultZoom: 13,
    });

    const waypoints = [];

    if (restLat !== null && restLon !== null && !isNaN(restLat) && !isNaN(restLon)) {
        map.addMarker(
            "pickupPin",
            "restaurant",
            restLat,
            restLon,
            `Pickup: ${restName}`,
            `<strong>🍽️ Pickup: ${restName}</strong><br>${restAddr}`
        );
        waypoints.push({ latitude: restLat, longitude: restLon });
    }

    if (custLat !== null && custLon !== null && !isNaN(custLat) && !isNaN(custLon)) {
        map.addMarker(
            "dropPin",
            "customer",
            custLat,
            custLon,
            "Drop-off Destination",
            `<strong>🏠 Customer Destination</strong><br>${custAddr}`
        );
        waypoints.push({ latitude: custLat, longitude: custLon });
    }

    if (waypoints.length >= 2) {
        map.drawRoute(waypoints);
        map.fitBounds(waypoints);
    } else if (waypoints.length === 1) {
        map.setCenter(waypoints[0].latitude, waypoints[0].longitude, 15);
    }
    map.invalidateSize();

    // Watch position & transmit to backend while on this delivery
    const gps = new GPSLocationManager({ minIntervalMs: 5000 });
    const riderTelemetry = document.getElementById("riderGpsTelemetry");
    let isSendingGps = false;

    window.addEventListener("beforeunload", () => {
        gps.stopTracking();
    });

    gps.startTracking(
        (pos) => {
            const lat = pos.coords.latitude;
            const lon = pos.coords.longitude;

            map.addMarker("riderPin", "delivery", lat, lon, "Your Location", "<strong>🛵 Your Current Location</strong>");

            if (isSendingGps) {
                return;
            }
            isSendingGps = true;

            gps.sendDeliveryLocation(pos, {
                assignment_id: assignmentId,
                order_id: orderId,
            }).then((res) => {
                if (riderTelemetry) {
                    riderTelemetry.textContent = `Live GPS: ${lat.toFixed(4)}, ${lon.toFixed(4)} (±${Math.round(pos.coords.accuracy)}m)`;
                }
                if (res && res.arrived_at_pickup) {
                    window.location.reload();
                }
            }).catch((error) => {
                if (error.status === 410 || error.data?.code === "DELIVERY_COMPLETED") {
                    gps.stopTracking();
                    if (riderTelemetry) {
                        riderTelemetry.textContent = "Delivery completed. GPS tracking stopped.";
                    }
                } else if (error.status === 403) {
                    gps.stopTracking();
                    if (riderTelemetry) {
                        riderTelemetry.innerHTML = `<span class="text-danger">⚠️ Not authorized for this delivery.</span>`;
                    }
                } else {
                    if (riderTelemetry) {
                        riderTelemetry.textContent = `GPS update failed: ${error.message}`;
                    }
                }
            }).finally(() => {
                isSendingGps = false;
            });
        },
        (errMsg) => {
            if (riderTelemetry) {
                riderTelemetry.innerHTML = `<span class="text-danger">⚠️ GPS: ${errMsg}</span>`;
            }
        }
    );
});
