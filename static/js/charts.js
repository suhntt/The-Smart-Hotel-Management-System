// Admin Analytics Dashboard Charts Manager (Chart.js)

document.addEventListener('DOMContentLoaded', function() {
    const revenueCtx = document.getElementById('chart-revenue');
    const occupancyCtx = document.getElementById('chart-occupancy');
    const trendsCtx = document.getElementById('chart-trends');
    const foodCtx = document.getElementById('chart-food');
    
    if (!revenueCtx) return; // Not on the analytics page/admin dashboard
    
    // Fetch data from endpoint
    fetch('/admin/analytics/data')
        .then(response => response.json())
        .then(data => {
            initCharts(data);
        })
        .catch(err => {
            console.error('Error fetching analytics data:', err);
        });

    function initCharts(data) {
        // 1. Monthly Revenue Chart (Bar Chart)
        if (revenueCtx) {
            new Chart(revenueCtx, {
                type: 'bar',
                data: {
                    labels: data.months,
                    datasets: [
                        {
                            label: 'Room Bookings (₹)',
                            data: data.room_sales,
                            backgroundColor: '#2563eb', // Royal Blue
                            borderRadius: 6
                        },
                        {
                            label: 'Food Orders (₹)',
                            data: data.food_sales,
                            backgroundColor: '#10b981', // Emerald
                            borderRadius: 6
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { position: 'top' }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            grid: { color: '#f1f5f9' }
                        },
                        x: {
                            grid: { display: false }
                        }
                    }
                }
            });
        }

        // 2. Room Occupancy Doughnut Chart
        if (occupancyCtx) {
            new Chart(occupancyCtx, {
                type: 'doughnut',
                data: {
                    labels: data.categories,
                    datasets: [{
                        data: data.occupancy,
                        backgroundColor: [
                            '#475569', // Standard - slate
                            '#3b82f6', // Deluxe - blue
                            '#6366f1', // Executive - indigo
                            '#a855f7', // Family - purple
                            '#ec4899'  // Suite - pink
                        ],
                        borderWidth: 2,
                        borderColor: '#ffffff'
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { position: 'right' }
                    },
                    cutout: '65%'
                }
            });
        }

        // 3. Booking Trends Chart (Line Chart)
        if (trendsCtx) {
            new Chart(trendsCtx, {
                type: 'line',
                data: {
                    labels: data.trends_months,
                    datasets: [{
                        label: 'Bookings Volume',
                        data: data.booking_trends,
                        borderColor: '#6366f1',
                        backgroundColor: 'rgba(99, 102, 241, 0.1)',
                        fill: true,
                        tension: 0.4,
                        borderWidth: 3,
                        pointRadius: 4,
                        pointBackgroundColor: '#6366f1'
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            grid: { color: '#f1f5f9' }
                        },
                        x: {
                            grid: { display: false }
                        }
                    }
                }
            });
        }

        // 4. Food Sales polarArea Chart
        if (foodCtx) {
            new Chart(foodCtx, {
                type: 'polarArea',
                data: {
                    labels: data.food_categories,
                    datasets: [{
                        data: data.food_category_sales,
                        backgroundColor: [
                            'rgba(245, 158, 11, 0.7)', // Orange
                            'rgba(16, 185, 129, 0.7)', // Green
                            'rgba(239, 68, 68, 0.7)',  // Red
                            'rgba(59, 130, 246, 0.7)'   // Blue
                        ]
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { position: 'bottom' }
                    }
                }
            });
        }
    }
});
