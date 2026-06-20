const API_BASE = "http://127.0.0.1:8001";

let chartInstance = null;

async function fetchData() {
    // Show overlay
    const overlay = document.getElementById('loading-overlay');
    if (overlay) {
        overlay.style.display = 'flex';
        overlay.style.opacity = '1';
    }

    try {
        console.log("Fetching data from API...");
        // 1. Fetch Timeline (for Chart)
        const timelineRes = await fetch(`${API_BASE}/timeline`);
        const timelineData = await timelineRes.json();
        renderChart(timelineData.daily_timeseries);

        // 2. Fetch Gaps (for stats)
        const gapsRes = await fetch(`${API_BASE}/enforcement-gaps?view=overall`);
        const gapsData = await gapsRes.json();
        
        document.getElementById("stat-total-violations").innerText = gapsData.total_violations.toLocaleString();
        document.getElementById("stat-scita-gap").innerHTML = `${gapsData.gap_percentage.toFixed(1)} <span class="text-base opacity-75 font-normal">%</span>`;
        const scitaLag = gapsData.avg_scita_lag_hrs;
        document.getElementById("stat-response-delay").innerHTML = scitaLag !== undefined && scitaLag !== null
            ? `${scitaLag.toFixed(1)} <span class="text-base opacity-75 font-normal">hours</span>`
            : `N/A`;

        // 3. Fetch Hotspots (for stats)
        const hotspotsRes = await fetch(`${API_BASE}/hotspots?top_n=100`);
        const hotspotsData = await hotspotsRes.json();
        document.getElementById("stat-hotspots").innerText = hotspotsData.total_clusters;

        // 4. Fetch Predictions (for table)
        const predictRes = await fetch(`${API_BASE}/predict-tomorrow?top_n=5`);
        const predictData = await predictRes.json();
        renderPredictions(predictData.top_predicted_hotspots);

        // Hide overlay on success
        if (overlay) {
            overlay.style.opacity = '0';
            setTimeout(() => overlay.style.display = 'none', 500);
        }

    } catch (e) {
        console.error("Error fetching data:", e);
        if (overlay) {
            overlay.innerHTML = `
                <span class="material-symbols-outlined text-[64px] text-error mb-6">error</span>
                <h2 class="font-headline-md text-headline-md text-error font-bold tracking-widest uppercase mb-2">Connection Failed</h2>
                <p class="font-code-md text-code-md text-on-surface-variant">Could not connect to API on port 8001. Is it running?</p>
            `;
        } else {
            alert("Could not connect to API. Is it running on http://127.0.0.1:8001?");
        }
    }
}

function renderChart(dailyData) {
    const ctx = document.getElementById('timelineChart').getContext('2d');
    
    // Sort chronologically (dailyData is an array of {date: string, count: number})
    const sorted = dailyData.sort((a, b) => new Date(a.date) - new Date(b.date));

    const labels = sorted.map(d => d.date);
    const data = sorted.map(d => d.count);

    if (chartInstance) {
        chartInstance.destroy();
    }

    Chart.defaults.color = '#bac9cc';
    Chart.defaults.font.family = 'Inter';

    chartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Violations',
                data: data,
                borderColor: '#00daf3',
                backgroundColor: 'rgba(0, 218, 243, 0.1)',
                borderWidth: 2,
                fill: true,
                tension: 0.4,
                pointRadius: 0,
                pointHitRadius: 10,
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
                    grid: { color: 'rgba(255, 255, 255, 0.05)' }
                },
                x: {
                    grid: { display: false },
                    ticks: { maxTicksLimit: 10 }
                }
            }
        }
    });
}

function renderPredictions(hotspots) {
    const tbody = document.getElementById("hotspots-tbody");
    tbody.innerHTML = "";

    hotspots.forEach(h => {
        let intensityColor = "text-primary";
        let bgWidth = (h.predicted_violations_24h / 1000) * 100;
        if (bgWidth > 100) bgWidth = 100;

        if (h.crs > 0.3) intensityColor = "text-error";
        else if (h.crs > 0.15) intensityColor = "text-surface-tint";

        const row = `
        <tr class="border-b border-white/5 hover:bg-white/5 transition-colors group relative">
            <td class="p-4 relative">
                <div class="absolute left-0 top-0 bottom-0 w-0.5 bg-primary opacity-0 group-hover:opacity-100 transition-opacity"></div>
                <span class="font-code-md text-code-md text-on-surface-variant">${h.top_junction || 'No Junction'}</span>
            </td>
            <td class="p-4">${h.top_station}</td>
            <td class="p-4 font-bold ${intensityColor}">${h.predicted_violations_24h.toFixed(0)}</td>
            <td class="p-4">${h.peak_hour}:00</td>
            <td class="p-4 font-code-md">${h.crs.toFixed(4)}</td>
        </tr>`;
        tbody.innerHTML += row;
    });
}

async function generateBrief() {
    const briefContainer = document.getElementById("ai-brief-content");
    const btn = document.getElementById("btn-generate-brief");
    
    btn.disabled = true;
    btn.innerText = "Generating (takes 5-10s)...";
    briefContainer.innerHTML = '<p class="text-surface-tint animate-pulse">&gt; Contacting Groq LLM...</p>';

    try {
        const res = await fetch(`${API_BASE}/patrol-brief`, {
            method: "POST"
        });
        
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || "Unknown error");
        }
        
        const data = await res.json();
        
        // Format markdown to simple HTML
        let htmlContent = data.patrol_brief
            .replace(/\*\*(.*?)\*\*/g, '<span class="font-bold text-primary">$1</span>')
            .replace(/\n/g, '<br/>')
            .replace(/\* (.*?)(?=<br\/>)|\* (.*?$)/gm, '<li class="ml-4 mb-2">$1$2</li>');

        briefContainer.innerHTML = `<div class="text-on-background">${htmlContent}</div>`;
        btn.innerText = "Brief Generated";

    } catch (e) {
        console.error(e);
        briefContainer.innerHTML = `<p class="text-error">&gt; Error: ${e.message}</p>`;
        btn.innerText = "Try Again";
        btn.disabled = false;
    }
}

// Initial fetch
document.addEventListener("DOMContentLoaded", fetchData);
