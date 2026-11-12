(() => {
    const dataElement = document.getElementById("admin-chart-data");
    const canvas = document.getElementById("admin-activity-chart");
    const errorMessage = document.getElementById("admin-chart-error");

    if (!dataElement || !canvas) {
        return;
    }

    if (typeof Chart === "undefined") {
        if (errorMessage) {
            errorMessage.hidden = false;
        }
        return;
    }

    const data = JSON.parse(dataElement.textContent);
    new Chart(canvas, {
        data: {
            labels: data.labels,
            datasets: [
                {
                    type: "bar",
                    label: "Platform revenue",
                    data: data.platform_revenue,
                    yAxisID: "revenue",
                    backgroundColor: "rgba(232, 93, 4, 0.16)",
                    borderColor: "#e85d04",
                    borderWidth: 1,
                    borderRadius: 5,
                    maxBarThickness: 26,
                },
                {
                    type: "line",
                    label: "Orders",
                    data: data.orders,
                    yAxisID: "orders",
                    borderColor: "#3157a4",
                    backgroundColor: "#3157a4",
                    borderWidth: 2,
                    pointRadius: data.labels.length > 30 ? 0 : 2,
                    pointHoverRadius: 5,
                    tension: 0.32,
                },
                {
                    type: "line",
                    label: "Delivered",
                    data: data.delivered,
                    yAxisID: "orders",
                    borderColor: "#16834a",
                    backgroundColor: "#16834a",
                    borderWidth: 2,
                    pointRadius: data.labels.length > 30 ? 0 : 2,
                    pointHoverRadius: 5,
                    tension: 0.32,
                },
            ],
        },
        options: {
            maintainAspectRatio: false,
            interaction: {
                intersect: false,
                mode: "index",
            },
            plugins: {
                legend: {
                    position: "bottom",
                    labels: {
                        usePointStyle: true,
                        boxWidth: 8,
                        padding: 18,
                        color: "#748094",
                    },
                },
                tooltip: {
                    callbacks: {
                        label(context) {
                            const value = context.parsed.y || 0;
                            if (context.dataset.yAxisID === "revenue") {
                                return `${context.dataset.label}: ₹${value.toFixed(2)}`;
                            }
                            return `${context.dataset.label}: ${value}`;
                        },
                    },
                },
            },
            scales: {
                x: {
                    grid: { display: false },
                    ticks: {
                        color: "#748094",
                        maxTicksLimit: 10,
                    },
                },
                orders: {
                    beginAtZero: true,
                    position: "left",
                    grid: { color: "rgba(116, 128, 148, 0.12)" },
                    ticks: {
                        precision: 0,
                        color: "#748094",
                    },
                },
                revenue: {
                    beginAtZero: true,
                    position: "right",
                    grid: { drawOnChartArea: false },
                    ticks: {
                        color: "#748094",
                        callback(value) {
                            return `₹${value}`;
                        },
                    },
                },
            },
        },
    });
})();
