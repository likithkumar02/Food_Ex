document.addEventListener("DOMContentLoaded", () => {
    const mapEl = document.getElementById("adminLiveMap");
    if (!mapEl) return;

    const defaultLat = parseFloat(mapEl.dataset.defaultLat) || 17.6868;
    const defaultLon = parseFloat(mapEl.dataset.defaultLon) || 83.2185;

    const mapOptions = {
        defaultCenter: [defaultLat, defaultLon],
        defaultZoom: 12,
    };
    if (mapEl.dataset.tileUrl) {
        mapOptions.tileUrl = mapEl.dataset.tileUrl;
    }

    const map = new FoodExMap("adminLiveMap", mapOptions);

    let currentLiveFeed = null;
    let selectedOrderId = null;

    function fetchLiveFeed() {
        fetch("/api/location/admin/live/")
            .then(res => res.json())
            .then(data => {
                currentLiveFeed = data;
                renderLiveMap(data);
                renderLists(data);
                const lastUpdatedText = document.getElementById("lastUpdatedText");
                const metricPartners = document.getElementById("metricPartners");
                const metricOrders = document.getElementById("metricOrders");
                if (lastUpdatedText) lastUpdatedText.textContent = "Updated " + new Date().toLocaleTimeString();
                if (metricPartners && data.metrics) metricPartners.textContent = data.metrics.online_partners;
                if (metricOrders && data.metrics) metricOrders.textContent = data.metrics.active_deliveries;
            })
            .catch(err => console.error("Admin live feed error:", err));
    }

    function renderLiveMap(data) {
        if (!selectedOrderId) {
            map.clearMarkers();

            // Plot restaurants
            if (data.restaurants) {
                data.restaurants.forEach(r => {
                    if (r.latitude && r.longitude) {
                        map.addMarker(`rest_${r.id}`, "restaurant", r.latitude, r.longitude, r.name,
                            `<strong>${r.name}</strong><br>${r.cuisine || ''}<br><small>${r.address || ''}</small>`
                        );
                    }
                });
            }

            // Plot online partners
            if (data.delivery_partners) {
                data.delivery_partners.forEach(p => {
                    if (p.latitude && p.longitude) {
                        const statusText = p.assigned_order_id ? `Assigned to Order #${p.assigned_order_id}` : "Available";
                        map.addMarker(`partner_${p.id}`, "delivery", p.latitude, p.longitude, p.name,
                            `<strong>🛵 ${p.name}</strong><br>Status: ${statusText}<br>Vehicle: ${p.vehicle || 'Standard'}`
                        );
                    }
                });
            }
        }
    }

    function renderLists(data) {
        // Render Active Orders
        const ordersEl = document.getElementById("ordersList");
        if (ordersEl) {
            if (!data.active_orders || data.active_orders.length === 0) {
                ordersEl.innerHTML = `<p class="text-muted small text-center my-3">No active deliveries right now.</p>`;
            } else {
                ordersEl.innerHTML = data.active_orders.map(o => `
                    <div class="card p-2 border admin-order-item ${selectedOrderId === o.id ? 'active' : ''}" onclick="selectOrder(${o.id})">
                        <div class="d-flex justify-content-between align-items-center mb-1">
                            <strong class="text-danger small">#${o.code || o.id}</strong>
                            <span class="badge bg-danger-subtle text-danger small">${o.status_display}</span>
                        </div>
                        <div class="small fw-semibold text-truncate">${o.restaurant_name}</div>
                        <div class="small text-muted text-truncate">Partner: ${o.partner_name}</div>
                    </div>
                `).join("");
            }
        }

        // Render Online Partners
        const partnersEl = document.getElementById("partnersList");
        if (partnersEl) {
            if (!data.delivery_partners || data.delivery_partners.length === 0) {
                partnersEl.innerHTML = `<p class="text-muted small text-center my-3">No partners currently online.</p>`;
            } else {
                partnersEl.innerHTML = data.delivery_partners.map(p => `
                    <div class="card p-2 border">
                        <div class="d-flex justify-content-between align-items-center">
                            <strong class="small">${p.name}</strong>
                            <span class="badge ${p.assigned_order_id ? 'bg-warning text-dark' : 'bg-success'} small">
                                ${p.assigned_order_id ? 'On Delivery' : 'Available'}
                            </span>
                        </div>
                        <small class="text-muted">${p.vehicle || 'Motorbike'} · ${p.latitude ? 'GPS Active' : 'No GPS'}</small>
                    </div>
                `).join("");
            }
        }
    }

    window.selectOrder = function(orderId) {
        selectedOrderId = orderId;
        if (!currentLiveFeed || !currentLiveFeed.active_orders) return;
        const order = currentLiveFeed.active_orders.find(o => o.id === orderId);
        if (!order) return;

        // Populate detail box
        const box = document.getElementById("orderDetailBox");
        if (box) box.classList.remove("d-none");
        const inspectCode = document.getElementById("inspectCode");
        const inspectStatus = document.getElementById("inspectStatus");
        const inspectRest = document.getElementById("inspectRest");
        const inspectCust = document.getElementById("inspectCust");
        const inspectPartner = document.getElementById("inspectPartner");
        const inspectDist = document.getElementById("inspectDist");
        const inspectEta = document.getElementById("inspectEta");

        if (inspectCode) inspectCode.textContent = `#${order.code || order.id}`;
        if (inspectStatus) inspectStatus.textContent = (order.status_display || '').toUpperCase();
        if (inspectRest) inspectRest.textContent = order.restaurant_name;
        if (inspectCust) inspectCust.textContent = order.customer_name;
        if (inspectPartner) inspectPartner.textContent = order.partner_name;
        if (inspectDist) inspectDist.textContent = order.distance ? `${order.distance} km` : "N/A";
        if (inspectEta) inspectEta.textContent = order.eta_minutes ? `${order.eta_minutes} min` : "N/A";

        // Draw order on map
        map.clearMarkers();
        const bounds = [];

        if (order.restaurant_lat && order.restaurant_lon) {
            map.addMarker("o_rest", "restaurant", order.restaurant_lat, order.restaurant_lon, order.restaurant_name,
                `<strong>Restaurant</strong><br>${order.restaurant_name}`);
            bounds.push({ latitude: order.restaurant_lat, longitude: order.restaurant_lon });
        }

        if (order.delivery_lat && order.delivery_lon) {
            map.addMarker("o_partner", "delivery", order.delivery_lat, order.delivery_lon, order.partner_name,
                `<strong>Delivery Partner</strong><br>${order.partner_name}`);
            bounds.push({ latitude: order.delivery_lat, longitude: order.delivery_lon });
        }

        if (order.customer_lat && order.customer_lon) {
            map.addMarker("o_cust", "customer", order.customer_lat, order.customer_lon, "Customer Destination",
                `<strong>Delivery Address</strong><br>${order.customer_name}`);
            bounds.push({ latitude: order.customer_lat, longitude: order.customer_lon });
        }

        // Draw connecting visual route
        if (bounds.length >= 2) {
            map.drawRoute(bounds);
            map.fitBounds(bounds);
        }
    };

    const refreshBtn = document.getElementById("btnRefresh");
    if (refreshBtn) {
        refreshBtn.addEventListener("click", fetchLiveFeed);
    }

    // Initial fetch and 10-second polling
    fetchLiveFeed();
    setInterval(fetchLiveFeed, 10000);
});

