(() => {
    const tracker = document.getElementById("orderTracking");
    const mapElement = document.getElementById("customerOrderTrackingMap");
    if (!tracker) return;

    const statusText = document.getElementById("currentOrderStatus");
    const partnerText = document.getElementById("deliveryPartnerName");
    const partnerMetaText = document.getElementById("deliveryPartnerMeta");
    const assignmentStatusText = document.getElementById("deliveryAssignmentStatus");
    const locationText = document.getElementById("deliveryLocation");
    const errorText = document.getElementById("trackingError");
    const timelineItems = [...document.querySelectorAll("[data-order-state]")];
    const restaurantName = document.getElementById("trackingRestaurantName");
    const restaurantCuisine = document.getElementById("trackingRestaurantCuisine");
    const restaurantAddress = document.getElementById("trackingRestaurantAddress");
    const restaurantPhone = document.getElementById("trackingRestaurantPhone");

    const states = [
        "placed",
        "accepted",
        "preparing",
        "ready_for_pickup",
        "finding_delivery_partner",
        "delivery_assigned",
        "assignment_failed",
        "delivery_partner_assigned",
        "arrived_at_pickup",
        "picked_up",
        "out_for_delivery",
        "delivered",
    ];

    const map = mapElement && typeof FoodExMap !== "undefined"
        ? new FoodExMap("customerOrderTrackingMap", { defaultZoom: 14 })
        : null;

    let currentPhase = null;
    let hasInitialBounds = false;

    function hasCoordinates(point) {
        return point && point.latitude !== null && point.longitude !== null
            && Number.isFinite(Number(point.latitude))
            && Number.isFinite(Number(point.longitude));
    }

    function updateTimeline(status, timestamps = {}) {
        const terminal = ["cancelled", "rejected"].includes(status);
        const currentIndex = states.indexOf(status);
        timelineItems.forEach((item) => {
            const itemStatus = item.dataset.orderState;
            const itemIndex = states.indexOf(itemStatus);
            const complete = terminal
                ? itemStatus === status
                : itemIndex >= 0 && itemIndex <= currentIndex;
            const current = itemStatus === status;
            item.classList.toggle("is-complete", complete);
            item.classList.toggle("is-current", current);
            if (current) item.setAttribute("aria-current", "step");
            else item.removeAttribute("aria-current");
            const timestamp = item.querySelector("[data-order-timestamp]");
            const timestampValue = timestamps[itemStatus];
            if (timestamp) {
                timestamp.textContent = timestampValue
                    ? new Date(timestampValue).toLocaleString()
                    : "";
            }
        });
    }

    updateTimeline(tracker.dataset.currentStatus || "");

    /**
     * Map rendering:
     * - Always show BOTH Restaurant (🍽️) and Customer Home (🏠)
     * - Show Delivery Partner (🛵) when partner is active
     * - Flow:
     *   Phase A (to_restaurant): Route Delivery Partner -> Restaurant
     *   Phase B (at_restaurant): Delivery Partner at Restaurant
     *   Phase C/D (to_customer): Route Delivery Partner -> Customer Home
     *   Phase E (delivered): Order delivered
     */
    function updateMap(data) {
        if (!map) return;

        const phase = data.delivery_phase || "preparing";
        const phaseChanged = (phase !== currentPhase);
        currentPhase = phase;

        const hasPartner = hasCoordinates(data.location);
        const hasRest = hasCoordinates(data.restaurant);
        const hasCust = hasCoordinates(data.customer);

        const boundsPoints = [];

        // 1. ALWAYS render Restaurant Marker (🍽️)
        if (hasRest) {
            const rLat = Number(data.restaurant.latitude);
            const rLon = Number(data.restaurant.longitude);
            boundsPoints.push([rLat, rLon]);

            const isRestaurantTarget = ["to_restaurant", "at_restaurant"].includes(phase);
            const statusBadge = isRestaurantTarget
                ? '<span class="badge bg-danger text-white">📍 Current Pickup Destination</span>'
                : '<span class="badge bg-secondary text-white">✓ Order Picked Up</span>';

            const restPopup = `
                <div class="p-1">
                    <strong class="text-danger">🍽️ ${data.restaurant.name || "Restaurant"}</strong>
                    <div class="small text-muted mb-1">${data.restaurant.address || ""}</div>
                    ${statusBadge}
                </div>
            `;

            map.addMarker(
                "restaurant",
                "restaurant",
                rLat,
                rLon,
                data.restaurant.name || "Restaurant",
                restPopup
            );
        }

        // 2. ALWAYS render Customer Home Marker (🏠)
        if (hasCust) {
            const cLat = Number(data.customer.latitude);
            const cLon = Number(data.customer.longitude);
            boundsPoints.push([cLat, cLon]);

            const isCustomerTarget = ["to_customer", "delivered"].includes(phase);
            const statusBadge = isCustomerTarget
                ? '<span class="badge bg-success text-white">📍 Current Delivery Destination</span>'
                : '<span class="badge bg-light text-muted border">🏠 Final Drop-off Location</span>';

            const custPopup = `
                <div class="p-1">
                    <strong class="text-success">🏠 Your Home Address</strong>
                    <div class="small text-muted mb-1">${data.customer.address || ""}</div>
                    ${statusBadge}
                </div>
            `;

            map.addMarker(
                "customer",
                "customer",
                cLat,
                cLon,
                "Delivery Address",
                custPopup
            );
        }

        // 3. Render Delivery Partner Marker (🛵)
        if (hasPartner) {
            const pLat = Number(data.location.latitude);
            const pLon = Number(data.location.longitude);
            boundsPoints.push([pLat, pLon]);

            const partnerName = data.delivery_partner?.name || "Delivery Partner";
            const recordedTime = data.location.recorded_at ? new Date(data.location.recorded_at).toLocaleTimeString() : "";
            const freshnessBadge = data.location.is_fresh
                ? '<span class="badge bg-success text-white">Live GPS</span>'
                : '<span class="badge bg-warning text-dark">Signal Delayed</span>';

            const popupContent = `
                <div class="p-1">
                    <strong class="text-primary">🛵 ${partnerName}</strong><br>
                    ${freshnessBadge}
                    ${recordedTime ? `<br><small class="text-muted">Updated: ${recordedTime}</small>` : ""}
                    ${data.phase_message ? `<br><small class="fw-semibold text-danger">${data.phase_message}</small>` : ""}
                </div>
            `;

            map.addMarker(
                "delivery-partner",
                "delivery",
                pLat,
                pLon,
                partnerName,
                popupContent
            );
        } else {
            map.removeMarker("delivery-partner");
        }

        // 4. Render Active Road Route
        if (data.route && data.route.coordinates && data.route.coordinates.length >= 2) {
            map.drawRoute(data.route.coordinates, {
                isRoadRoute: data.route.is_road_route !== false,
            });
        } else if (hasPartner && hasRest && !["to_customer", "delivered"].includes(phase)) {
            // Straight line Delivery Partner -> Restaurant before pickup
            map.drawRoute([[data.location.latitude, data.location.longitude], [data.restaurant.latitude, data.restaurant.longitude]], { isRoadRoute: false });
        } else if (hasPartner && hasCust && ["to_customer", "delivered"].includes(phase)) {
            // Straight line Delivery Partner -> Customer Home after pickup
            map.drawRoute([[data.location.latitude, data.location.longitude], [data.customer.latitude, data.customer.longitude]], { isRoadRoute: false });
        } else if (hasRest && hasCust) {
            // Preview: Restaurant -> Customer Home
            map.drawRoute([[data.restaurant.latitude, data.restaurant.longitude], [data.customer.latitude, data.customer.longitude]], { isRoadRoute: false });
        } else {
            map.clearRoute();
        }

        // 5. Fit bounds to comfortably frame all points
        if (boundsPoints.length > 0 && (!hasInitialBounds || phaseChanged)) {
            map.fitBounds(boundsPoints);
            hasInitialBounds = true;
        }
    }

    async function refreshTracking() {
        try {
            const response = await fetch(tracker.dataset.trackingUrl, {
                credentials: "same-origin",
            });
            if (!response.ok) {
                throw new Error(response.status === 403
                    ? "You are not allowed to view this order."
                    : "Tracking is temporarily unavailable.");
            }
            const data = await response.json();

            // 1. Order Status & Timeline
            statusText.textContent = data.status_display || data.status;
            updateTimeline(data.status, data.status_timestamps);

            // 2. Partner Assignment Text
            const partnerConfirmed = data.delivery_partner?.is_assigned;
            partnerText.textContent = partnerConfirmed
                ? `Delivery partner: ${data.delivery_partner.name}`
                : data.status === "assignment_failed"
                    ? "We could not confirm a delivery partner yet. Our team has been notified."
                    : "We’re finding a delivery partner for your order.";

            partnerMetaText.textContent = partnerConfirmed
                ? [data.delivery_partner.vehicle, data.delivery_partner.vehicle_number]
                    .filter(Boolean)
                    .join(" · ")
                : "";

            assignmentStatusText.textContent = data.delivery_partner
                ? data.delivery_partner.is_assigned
                    ? `Delivery status: ${data.delivery_partner.status_display || data.delivery_partner.status}`
                    : data.delivery_partner.status === "assigned"
                        ? "A delivery request is waiting for partner confirmation."
                        : "Delivery assignment pending"
                : data.status === "assignment_failed"
                    ? "Assignment needs attention"
                    : "Delivery assignment pending";

            // 3. Phase-Aware Live Location & Status Message
            const phaseMsg = data.phase_message || "";
            const distanceStr = data.distance_km != null ? `${data.distance_km} km remaining` : "";
            const etaStr = data.eta ? `ETA: ${data.eta}` : "";
            const metrics = [distanceStr, etaStr].filter(Boolean).join(" · ");

            if (hasCoordinates(data.location)) {
                const recordedTime = data.location.recorded_at ? new Date(data.location.recorded_at).toLocaleTimeString() : "";
                if (data.location.is_fresh) {
                    locationText.innerHTML = `
                        <div class="fw-semibold text-dark">${phaseMsg}</div>
                        <div class="small text-muted mt-1"><span class="badge bg-success text-white me-1">Live GPS</span> ${recordedTime ? `(${recordedTime})` : ""} ${metrics ? `· ${metrics}` : ""}</div>
                    `;
                } else {
                    locationText.innerHTML = `
                        <div class="fw-semibold text-dark">${phaseMsg}</div>
                        <div class="small text-warning mt-1"><span class="badge bg-warning text-dark me-1">GPS Delayed</span> (last seen ${recordedTime}) ${metrics ? `· ${metrics}` : ""}</div>
                    `;
                }
            } else if (data.status === "delivered") {
                locationText.innerHTML = `<span class="badge bg-success p-2">🎉 Order Delivered</span>`;
            } else {
                locationText.innerHTML = `
                    <div class="fw-semibold text-dark">${phaseMsg}</div>
                    <div class="small text-muted mt-1">${data.eta ? `Estimated delivery: ${data.eta}. Live partner location will appear when the partner is active.` : "Live partner location will appear when the partner is active."}</div>
                `;
            }

            // 4. Restaurant Information
            if (data.restaurant) {
                restaurantName.textContent = data.restaurant.name || "";
                restaurantCuisine.textContent = data.restaurant.cuisine || "";
                restaurantAddress.textContent = [
                    data.restaurant.address,
                    data.restaurant.area,
                    data.restaurant.city,
                ].filter(Boolean).join(", ");
                if (restaurantPhone && data.restaurant.phone) {
                    restaurantPhone.href = `tel:${data.restaurant.phone}`;
                    restaurantPhone.textContent = `Call restaurant: ${data.restaurant.phone}`;
                }
            }

            errorText.textContent = "";

            // 5. Update Map (showing BOTH restaurant & customer home, with delivery partner)
            updateMap(data);

            // 6. Stop polling if completed or terminal
            if (!data.is_live || ["delivered", "cancelled", "rejected"].includes(data.status)) {
                window.clearInterval(polling);
            }
        } catch (error) {
            errorText.textContent = `${error.message} Retrying automatically.`;
        }
    }

    const polling = window.setInterval(refreshTracking, 3000);
    refreshTracking();
})();
