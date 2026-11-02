document.addEventListener("DOMContentLoaded", () => {
    const dashboard = document.getElementById("deliveryDashboard");
    const form = document.querySelector('form[action$="/delivery/availability/"]');
    const statusText = document.getElementById("deliveryGpsStatus");
    if (!dashboard || !form || !statusText) return;

    const gps = new GPSLocationManager({
        minIntervalMs: 10000,
        minDistanceMeters: 20,
    });

    function showGpsError(message) {
        statusText.textContent = message;
        statusText.classList.add("text-danger");
    }

    function transmit(position) {
        statusText.textContent = `GPS active: ${position.coords.latitude.toFixed(5)}, ${position.coords.longitude.toFixed(5)}`;
        statusText.classList.remove("text-danger");
        gps.sendDeliveryLocation(position).catch((error) => showGpsError(error.message));
    }

    if (dashboard.dataset.online === "true") {
        gps.startTracking(transmit, showGpsError);
    }

    form.addEventListener("submit", (event) => {
        const switchingOnline = form.querySelector('[name="is_online"]').value === "true";
        if (!switchingOnline) return;

        event.preventDefault();
        statusText.textContent = "Requesting GPS before going online...";
        statusText.classList.remove("text-danger");
        gps.getCurrentLocation(async (position) => {
            try {
                await gps.sendDeliveryLocation(position);
                form.submit();
            } catch (error) {
                showGpsError(`Could not go online: ${error.message}`);
            }
        }, (message) => showGpsError(`Could not go online: ${message}`));
    });

    const requestFeed = document.getElementById("deliveryRequestFeed");
    const requestList = document.getElementById("deliveryRequestList");
    const requestError = document.getElementById("deliveryRequestError");
    if (!requestFeed || !requestList || !requestError) return;

    const csrfToken = form.querySelector('[name="csrfmiddlewaretoken"]').value;
    const requestPath = requestFeed.dataset.requestsUrl;
    const acceptPath = requestFeed.dataset.acceptUrl;
    const rejectPath = requestFeed.dataset.rejectUrl;

    function addActionForm(container, actionUrl, buttonText, cssClass) {
        const action = document.createElement("form");
        action.method = "post";
        action.action = actionUrl;
        action.className = "d-inline";
        const token = document.createElement("input");
        token.type = "hidden";
        token.name = "csrfmiddlewaretoken";
        token.value = csrfToken;
        const button = document.createElement("button");
        button.type = "submit";
        button.className = cssClass;
        button.textContent = buttonText;
        action.append(token, button);
        container.append(action);
    }

    async function refreshRequests() {
        try {
            const response = await fetch(requestPath, { credentials: "same-origin" });
            if (!response.ok) {
                throw new Error(`Could not check delivery requests (HTTP ${response.status}).`);
            }
            const requests = await response.json();
            requestList.replaceChildren();
            if (!requests.length) {
                const empty = document.createElement("p");
                empty.className = "small text-muted";
                empty.textContent = "No new delivery requests right now.";
                requestList.append(empty);
            }
            requests.forEach((delivery) => {
                const card = document.createElement("article");
                card.className = "border rounded p-3 mb-2";
                const heading = document.createElement("h4");
                heading.className = "h6";
                heading.textContent = `Order ${delivery.order_code} · ${delivery.restaurant}`;
                const pickup = document.createElement("p");
                pickup.className = "small mb-1";
                pickup.textContent = `Pickup: ${delivery.pickup_address}`;
                const restaurantContact = document.createElement("p");
                restaurantContact.className = "small mb-1";
                restaurantContact.textContent = delivery.restaurant_phone
                    ? `Restaurant phone: ${delivery.restaurant_phone}`
                    : "Restaurant phone: not provided";
                const dropoff = document.createElement("p");
                dropoff.className = "small mb-1";
                dropoff.textContent = `Customer: ${delivery.customer_name}`;
                const deliveryAddress = document.createElement("p");
                deliveryAddress.className = "small mb-1";
                deliveryAddress.textContent = `Drop-off: ${delivery.delivery_address}`;
                const customerContact = document.createElement("p");
                customerContact.className = "small mb-2";
                customerContact.textContent = delivery.customer_phone
                    ? `Customer phone: ${delivery.customer_phone}`
                    : "Customer phone: not provided";
                card.append(
                    heading,
                    pickup,
                    restaurantContact,
                    dropoff,
                    deliveryAddress,
                    customerContact,
                );
                addActionForm(
                    card,
                    acceptPath.replace(/0(?=\/accept\/)/, String(delivery.id)),
                    "Accept",
                    "btn btn-success btn-sm me-2",
                );
                addActionForm(
                    card,
                    rejectPath.replace(/0(?=\/reject\/)/, String(delivery.id)),
                    "Reject",
                    "btn btn-outline-danger btn-sm",
                );
                requestList.append(card);
            });
            requestError.textContent = "";
        } catch (error) {
            requestError.textContent = error.message;
        }
    }

    refreshRequests();
    window.setInterval(refreshRequests, 10000);
});
