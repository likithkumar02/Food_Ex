(() => {
    const tracker = document.getElementById("orderTracking");
    if (!tracker) return;

    const labels = {
        pending: "Order placed",
        confirmed: "Restaurant accepted",
        preparing: "Preparing your food",
        ready_for_pickup: "Ready for pickup",
        picked_up: "Picked up",
        out_for_delivery: "Out for delivery",
        delivered: "Delivered",
        cancelled: "Cancelled",
    };
    const statusText = document.getElementById("currentOrderStatus");
    const partnerText = document.getElementById("deliveryPartnerName");
    const locationText = document.getElementById("deliveryLocation");
    const timelineItems = [...document.querySelectorAll("[data-order-state]")];
    const token = sessionStorage.getItem("food_ex_access");

    async function refreshStatus() {
        const headers = token ? { Authorization: `Bearer ${token}` } : {};
        try {
            const response = await fetch(tracker.dataset.statusUrl, {
                credentials: "same-origin",
                headers,
            });
            if (!response.ok) return;
            const data = await response.json();
            statusText.textContent = labels[data.status] || data.status;
            timelineItems.forEach((item) => {
                const state = data.timeline.find((entry) => entry.status === item.dataset.orderState);
                item.classList.toggle("is-complete", Boolean(state?.complete));
                item.classList.toggle("is-current", Boolean(state?.current));
                if (state?.current) item.setAttribute("aria-current", "step");
                else item.removeAttribute("aria-current");
            });
            partnerText.textContent = data.delivery_partner
                ? `Delivery partner: ${data.delivery_partner}`
                : "";
            locationText.textContent = data.delivery_location
                ? `Latest location: ${data.delivery_location.latitude}, ${data.delivery_location.longitude}`
                : "";
            if (["delivered", "cancelled"].includes(data.status)) window.clearInterval(polling);
        } catch {
            locationText.textContent = "Tracking will update when a connection is available.";
        }
    }

    refreshStatus();
    const polling = window.setInterval(refreshStatus, 5000);
})();