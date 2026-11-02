(() => {
    const ACCESS_KEY = "food_ex_access";
    const REFRESH_KEY = "food_ex_refresh";
    const body = document.body;
    const urls = body.dataset;

    function clearTokens() {
        sessionStorage.removeItem(ACCESS_KEY);
        sessionStorage.removeItem(REFRESH_KEY);
    }

    async function refreshAccessToken() {
        const refresh = sessionStorage.getItem(REFRESH_KEY);
        if (!refresh) return false;

        try {
            const response = await fetch(urls.authRefreshUrl, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ refresh }),
            });
            if (!response.ok) {
                clearTokens();
                return false;
            }
            const tokens = await response.json();
            sessionStorage.setItem(ACCESS_KEY, tokens.access);
            if (tokens.refresh) sessionStorage.setItem(REFRESH_KEY, tokens.refresh);
            return true;
        } catch {
            return false;
        }
    }

    async function authenticatedFetch(url, options = {}) {
        let access = sessionStorage.getItem(ACCESS_KEY);
        if (!access) throw new Error("Please log in to continue.");

        const send = (token) => {
            const headers = new Headers(options.headers || {});
            headers.set("Authorization", `Bearer ${token}`);
            return fetch(url, { ...options, headers, credentials: "same-origin" });
        };

        let response = await send(access);
        if (response.status === 401 && await refreshAccessToken()) {
            access = sessionStorage.getItem(ACCESS_KEY);
            response = await send(access);
        }
        return response;
    }

    function displayMessage(element, message, kind = "error") {
        if (!element) return;
        element.textContent = message;
        element.className = `form-message is-${kind}`;
        element.hidden = !message;
    }

    async function responseData(response) {
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
            const errors = data.errors || data;
            const message = typeof errors === "string"
                ? errors
                : Object.values(errors).flat().join(" ") || "Something went wrong. Please try again.";
            throw new Error(message);
        }
        return data;
    }

    function createLink(label, href, className = "dropdown-item") {
        const link = document.createElement("a");
        link.className = className;
        link.href = href;
        link.textContent = label;
        return link;
    }

    function renderGuestNav() {
        const slot = document.getElementById("authNavSlot");
        if (!slot) return;
        slot.className = "nav-item ms-lg-3";
        slot.replaceChildren();
        const actions = document.createElement("div");
        actions.className = "auth-nav-actions";
        actions.append(
            createLink("Login", urls.loginUrl, "btn btn-outline-danger"),
            createLink("Register", urls.registerUrl, "btn btn-danger"),
        );
        slot.append(actions);
    }

    function renderUserNav(user) {
        const slot = document.getElementById("authNavSlot");
        if (!slot) return;
        slot.className = "nav-item dropdown ms-lg-3";
        slot.replaceChildren();

        const button = document.createElement("button");
        button.className = "btn btn-outline-secondary dropdown-toggle account-toggle";
        button.type = "button";
        button.dataset.bsToggle = "dropdown";
        button.setAttribute("aria-expanded", "false");
        button.textContent = user.name || "Profile";

        const menu = document.createElement("ul");
        menu.className = "dropdown-menu dropdown-menu-end";
        const items = [
            ["My Profile", urls.profileUrl],
            ["My Orders", urls.ordersUrl],
            ["My Addresses", `${urls.profileUrl}#address`],
            ["Favorites", `${urls.homeUrl}#favorites`],
            ["Settings", urls.settingsUrl],
        ];
        items.forEach(([label, href]) => {
            const item = document.createElement("li");
            item.append(createLink(label, href));
            menu.append(item);
        });

        const divider = document.createElement("li");
        divider.innerHTML = '<hr class="dropdown-divider">';
        menu.append(divider);

        const logoutItem = document.createElement("li");
        const logoutButton = document.createElement("button");
        logoutButton.className = "dropdown-item text-danger";
        logoutButton.type = "button";
        logoutButton.textContent = "Logout";
        logoutButton.addEventListener("click", logout);
        logoutItem.append(logoutButton);
        menu.append(logoutItem);

        slot.append(button, menu);
        if (window.bootstrap) window.bootstrap.Dropdown.getOrCreateInstance(button);
    }

    async function logout() {
        const refresh = sessionStorage.getItem(REFRESH_KEY);
        try {
            await authenticatedFetch(urls.authLogoutUrl, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ refresh }),
            });
        } catch {
            const fallback = document.getElementById("logoutFallbackForm");
            if (fallback) fallback.requestSubmit();
        }
        clearTokens();
        window.location.href = urls.homeUrl;
    }

    function showFormError(form, message) {
        const prefix = form.id === "registerForm" ? "register" : "login";
        displayMessage(document.getElementById(`${prefix}Message`), message);
    }

    function getCsrfToken(form) {
        return form?.querySelector?.("[name=csrfmiddlewaretoken]")?.value
            || document.querySelector("[name=csrfmiddlewaretoken]")?.value
            || (document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/)?.[1] || "");
    }

    function bindRegistrationForm() {
        const form = document.getElementById("registerForm");
        if (!form) return;
        const password = form.elements.password;
        const confirmation = form.elements.confirm_password;
        confirmation.addEventListener("input", () => confirmation.setCustomValidity(""));

        form.addEventListener("submit", async (event) => {
            event.preventDefault();
            form.classList.add("was-validated");
            confirmation.setCustomValidity(
                password.value === confirmation.value ? "" : "Passwords do not match.",
            );
            if (!form.reportValidity()) return;

            const button = form.querySelector("button[type=submit]");
            button.disabled = true;
            displayMessage(document.getElementById("registerMessage"), "Creating your account…", "info");

            const csrfToken = getCsrfToken(form);
            const headers = { "Content-Type": "application/json" };
            if (csrfToken) headers["X-CSRFToken"] = csrfToken;

            try {
                await responseData(await fetch(urls.authRegisterUrl, {
                    method: "POST",
                    headers,
                    body: JSON.stringify(Object.fromEntries(new FormData(form))),
                }));
                window.location.href = `${urls.loginUrl}?registered=1`;
            } catch (error) {
                showFormError(form, error.message);
                button.disabled = false;
            }
        });
    }

    function bindLoginForm() {
        const form = document.getElementById("loginForm");
        if (!form) return;
        if (new URLSearchParams(window.location.search).has("registered")) {
            displayMessage(document.getElementById("loginMessage"), "Account created. Log in to continue.", "success");
        }

        form.addEventListener("submit", async (event) => {
            event.preventDefault();
            form.classList.add("was-validated");
            if (!form.reportValidity()) return;

            const button = form.querySelector("button[type=submit]");
            button.disabled = true;

            const csrfToken = getCsrfToken(form);
            const headers = { "Content-Type": "application/json" };
            if (csrfToken) headers["X-CSRFToken"] = csrfToken;

            try {
                const result = await responseData(await fetch(urls.authLoginUrl, {
                    method: "POST",
                    headers,
                    body: JSON.stringify(Object.fromEntries(new FormData(form))),
                    credentials: "same-origin",
                }));
                sessionStorage.setItem(ACCESS_KEY, result.access);
                sessionStorage.setItem(REFRESH_KEY, result.refresh);
                window.location.href = "/";
            } catch (error) {
                showFormError(form, error.message);
                button.disabled = false;
            }
        });
    }

    function bindProfileForm() {
        const form = document.getElementById("profileForm");
        if (!form) return;

        const fields = document.getElementById("profileFields");
        const editButton = document.getElementById("editProfileButton");
        const saveButton = document.getElementById("saveProfileButton");
        const cancelButton = document.getElementById("cancelProfileButton");
        const imageInput = document.getElementById("profileImageInput");
        let currentProfile = null;

        function setEditing(editing) {
            fields.disabled = !editing;
            editButton.hidden = editing;
            saveButton.hidden = !editing;
            cancelButton.hidden = !editing;
        }

        function populate(profile) {
            currentProfile = profile;
            form.elements.name.value = profile.name || "";
            form.elements.phone.value = profile.phone || "";
            form.elements.address.value = profile.address || "";
            document.getElementById("profileEmail").value = profile.email || "";
            document.getElementById("profileDisplayName").textContent = profile.name || "";
            document.getElementById("profileDisplayEmail").textContent = profile.email || "";
            document.querySelector(".profile-role").textContent = profile.role || "customer";
            const image = document.getElementById("profileAvatar");
            const fallback = document.getElementById("profileAvatarFallback");
            image.hidden = !profile.profile_image;
            fallback.hidden = Boolean(profile.profile_image);
            if (profile.profile_image) image.src = profile.profile_image;
            imageInput.value = "";
        }

        editButton.addEventListener("click", () => setEditing(true));
        cancelButton.addEventListener("click", () => {
            if (currentProfile) populate(currentProfile);
            setEditing(false);
        });

        imageInput.addEventListener("change", () => {
            const file = imageInput.files[0];
            if (!file) return;
            const image = document.getElementById("profileAvatar");
            image.src = URL.createObjectURL(file);
            image.hidden = false;
            document.getElementById("profileAvatarFallback").hidden = true;
        });

        form.addEventListener("submit", async (event) => {
            event.preventDefault();
            if (!form.reportValidity()) return;
            const payload = new FormData();
            ["name", "phone", "address"].forEach((field) => payload.append(field, form.elements[field].value));
            if (imageInput.files[0]) payload.append("profile_image", imageInput.files[0]);

            saveButton.disabled = true;
            try {
                const response = await authenticatedFetch("/api/auth/profile/", {
                    method: "PUT",
                    body: payload,
                });
                const updated = await responseData(response);
                populate(updated);
                setEditing(false);
                displayMessage(document.getElementById("profileMessage"), "Profile updated successfully.", "success");
            } catch (error) {
                displayMessage(document.getElementById("profileMessage"), error.message);
            } finally {
                saveButton.disabled = false;
            }
        });

        authenticatedFetch("/api/auth/profile/")
            .then(responseData)
            .then(populate)
            .catch(() => {
                clearTokens();
                window.location.href = urls.loginUrl;
            });
    }

    document.addEventListener("DOMContentLoaded", () => {
        bindRegistrationForm();
        bindLoginForm();
        bindProfileForm();

        const isDeliveryPortal = window.location.pathname.startsWith("/delivery/")
            || window.location.pathname.startsWith("/dashboard/delivery/")
            || Boolean(document.querySelector(".portal-delivery"));

        if (!isDeliveryPortal && sessionStorage.getItem(ACCESS_KEY)) {
            authenticatedFetch("/api/auth/profile/")
                .then(responseData)
                .then(renderUserNav)
                .catch(() => {
                    clearTokens();
                    renderGuestNav();
                });
        }
    });

    window.foodExAuth = { authenticatedFetch, clearTokens };
})();
