document.addEventListener("DOMContentLoaded", () => {
    const button = document.getElementById("customerGpsButton");
    const feedback = document.getElementById("customerGpsFeedback");
    const csrfToken = document.querySelector(
        "#customerGpsForm [name=csrfmiddlewaretoken]"
    )?.value;

    if (!button || !feedback) return;

    const setFeedback = (message, isError = false) => {
        feedback.textContent = message;
        feedback.classList.toggle("text-danger", isError);
        feedback.classList.toggle("text-muted", !isError);
    };

    button.addEventListener("click", () => {
        if (!csrfToken) {
            setFeedback("Could not verify this request. Refresh the page and try again.", true);
            return;
        }

        button.disabled = true;
        setFeedback("Requesting your location permission...");

        const gps = new GPSLocationManager();
        gps.getCurrentLocation(async (position) => {
            setFeedback("Looking up your state and finding restaurants...");
            try {
                const response = await fetch(button.dataset.updateUrl, {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "X-CSRFToken": csrfToken,
                    },
                    body: JSON.stringify({
                        latitude: position.coords.latitude,
                        longitude: position.coords.longitude,
                        accuracy: position.coords.accuracy,
                        reverse_geocode: true,
                    }),
                });
                const data = await response.json();
                if (!response.ok || !data.success) {
                    throw new Error(data.message || "Unable to save your location.");
                }
                if (!data.state) {
                    setFeedback(
                        "Your GPS location was saved, but its state could not be identified. Please try again or choose a location manually.",
                        true
                    );
                    return;
                }

                setFeedback(`Location found in ${data.state}. Loading restaurants...`);
                const dashboardUrl = new URL(
                    button.dataset.dashboardUrl,
                    window.location.origin
                );
                dashboardUrl.searchParams.set("state", data.state);
                window.location.assign(dashboardUrl.toString());
            } catch (error) {
                setFeedback(error.message || "Unable to update your location.", true);
            } finally {
                button.disabled = false;
            }
        }, (errorMessage) => {
            setFeedback(errorMessage, true);
            button.disabled = false;
        });
    });
});
