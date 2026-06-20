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

        // 3. Fetch Hotspots (for stats and map)
        const hotspotsRes = await fetch(`${API_BASE}/hotspots?top_n=150`);
        const hotspotsData = await hotspotsRes.json();
        document.getElementById("stat-hotspots").innerText = hotspotsData.total_clusters;
        window.allHotspots = hotspotsData.hotspots; // Save for search
        renderMap(window.allHotspots);

        // 4. Fetch Predictions (for table)
        const predictRes = await fetch(`${API_BASE}/predict-tomorrow?top_n=5`);
        const predictData = await predictRes.json();
        window.allPredictions = predictData.top_predicted_hotspots; // Save for search
        renderPredictions(window.allPredictions);

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

let mapInstance = null;
let deckOverlay = null;

function renderMap(hotspots) {
    // Map CRS to RGB color for DeckGL Heatmap
    const getColor = (crs) => {
        if (crs > 0.3) return [255, 42, 127, 255];   
        if (crs > 0.15) return [251, 188, 4, 255];   
        return [0, 218, 243, 255];                   
    };
    
    // Map CRS to hex color for CSS Markers
    const getHexColor = (crs) => {
        if (crs > 0.3) return '#ff2a7f';
        if (crs > 0.15) return '#fbbc04';
        return '#00daf3';
    };

    if (!mapInstance) {
        mapInstance = new maplibregl.Map({
            container: 'heatmap-container',
            style: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
            center: [77.5946, 12.9716],
            zoom: 11.5,
            pitch: 30,
            bearing: 0
        });
        
        // Add Deck.gl Overlay for the Heatmap
        deckOverlay = new deck.MapboxOverlay({
            layers: []
        });
        mapInstance.addControl(deckOverlay);
    }

    // Clear old markers if we refresh
    if (window.currentMarkers) {
        window.currentMarkers.forEach(m => m.remove());
    }
    window.currentMarkers = [];

    // Create Sleek Heatmap Layer
    const heatmapLayer = new deck.HeatmapLayer({
        id: 'hotspot-heatmap',
        data: hotspots,
        getPosition: d => [d.centroid_lng, d.centroid_lat],
        getWeight: d => d.violation_count,
        radiusPixels: 70,
        intensity: 1.2,
        threshold: 0.05,
        colorRange: [
            [0, 218, 243, 40],   
            [0, 218, 243, 120],  
            [251, 188, 4, 180],  
            [255, 42, 127, 220], 
            [255, 0, 50, 255]    
        ]
    });

    deckOverlay.setProps({
        layers: [heatmapLayer]
    });

    // Add Native CSS Pulsating Markers (No flickering!)
    hotspots.forEach(h => {
        const hex = getHexColor(h.crs);
        const el = document.createElement('div');
        el.className = 'cursor-pointer group';
        
        // The pulsing dot using Tailwind's native animate-pulse
        el.innerHTML = `
            <div style="background-color: ${hex}; box-shadow: 0 0 12px ${hex};" 
                 class="w-4 h-4 rounded-full border-[1.5px] border-white/80 animate-pulse">
            </div>
        `;
        
        // Popup
        const popup = new maplibregl.Popup({ offset: 12, closeButton: false }).setHTML(`
            <div style="color: #131315; font-family: Inter, sans-serif; min-width: 140px; padding: 2px;">
                <strong style="display: block; font-size: 15px; margin-bottom: 4px; border-bottom: 1px solid #ccc; padding-bottom: 4px;">
                    ${h.top_junction || 'No Junction'}
                </strong>
                <div style="font-size: 13px;">📍 Station: ${h.top_station}</div>
                <div style="font-size: 13px; font-weight: bold; margin-top: 4px;">📊 Violations: ${h.violation_count}</div>
                <div style="font-size: 13px; color: ${hex}; font-weight: bold;">⚠️ CRS: ${h.crs.toFixed(4)}</div>
            </div>
        `);

        const marker = new maplibregl.Marker({ element: el })
            .setLngLat([h.centroid_lng, h.centroid_lat])
            .addTo(mapInstance);
            
        // Show info on hover
        el.addEventListener('mouseenter', () => {
            popup.setLngLat([h.centroid_lng, h.centroid_lat]).addTo(mapInstance);
        });
        el.addEventListener('mouseleave', () => {
            popup.remove();
        });
            
        window.currentMarkers.push(marker);
    });
}

// Global Search Functionality
document.addEventListener("DOMContentLoaded", () => {
    const searchInput = document.getElementById('search-input');
    if (searchInput) {
        searchInput.addEventListener('input', (e) => {
            const term = e.target.value.toLowerCase();
            
            // Filter map hotspots
            if (window.allHotspots) {
                const filteredMap = window.allHotspots.filter(h => 
                    (h.top_junction && h.top_junction.toLowerCase().includes(term)) ||
                    (h.top_station && h.top_station.toLowerCase().includes(term))
                );
                renderMap(filteredMap);
            }
            
            // Filter predictions table
            if (window.allPredictions) {
                const filteredTable = window.allPredictions.filter(h => 
                    (h.top_junction && h.top_junction.toLowerCase().includes(term)) ||
                    (h.top_station && h.top_station.toLowerCase().includes(term))
                );
                renderPredictions(filteredTable);
            }
        });
    }
});

