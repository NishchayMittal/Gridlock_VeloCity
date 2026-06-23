// Automatically switch between localhost and production backend
const API_BASE = (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')
    ? "http://127.0.0.1:8001"
    : "https://gridlock-velocity.onrender.com";

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
        const safeSetText = (id, text) => { const el = document.getElementById(id); if(el) el.innerText = text; };
        const safeSetHTML = (id, html) => { const el = document.getElementById(id); if(el) el.innerHTML = html; };

        // 1. Fetch Timeline (for Chart)
        const timelineRes = await fetch(`${API_BASE}/timeline`);
        const timelineData = await timelineRes.json();
        if (document.getElementById('timelineChart')) {
            renderChart(timelineData.daily_timeseries);
        }
        
        // Save for time-lapse
        window.hourlyDistribution = timelineData.hourly_distribution;
        window.maxHourly = Math.max(...Object.values(window.hourlyDistribution || {}));

        // 2. Fetch Gaps (for stats)
        const gapsRes = await fetch(`${API_BASE}/enforcement-gaps?view=overall`);
        const gapsData = await gapsRes.json();
        
        safeSetText("stat-total-violations", gapsData.total_violations.toLocaleString());
        safeSetHTML("stat-scita-gap", `${gapsData.gap_percentage.toFixed(1)} <span class="text-base opacity-75 font-normal">%</span>`);
        
        // Calculate Revenue Leakage (Assuming avg ₹500 fine for wrong parking)
        const lostRevenue = gapsData.not_sent_to_scita * 500;
        
        // Format as Indian Currency (Crores/Lakhs)
        const formatter = new Intl.NumberFormat('en-IN', {
            style: 'currency',
            currency: 'INR',
            maximumFractionDigits: 0
        });
        
        safeSetText("stat-revenue-leakage", formatter.format(lostRevenue));

        // 3. Fetch Hotspots (for stats and map)
        const hotspotsRes = await fetch(`${API_BASE}/hotspots?top_n=150`);
        const hotspotsData = await hotspotsRes.json();
        safeSetText("stat-hotspots", hotspotsData.total_clusters);
        window.allHotspots = hotspotsData.hotspots; // Save for search
        if (document.getElementById('heatmap-container')) {
            renderMap(window.allHotspots);
        }

        // 4. Fetch Predictions (for table)
        const predictRes = await fetch(`${API_BASE}/predict-tomorrow?top_n=15`);
        const predictData = await predictRes.json();
        window.allPredictions = predictData.top_predicted_hotspots; // Save for search
        if (document.getElementById('hotspots-tbody')) {
            renderPredictions(window.allPredictions);
        }

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
    const ctx = document.getElementById('timelineChart');
    if (!ctx) return;
    const canvasContext = ctx.getContext('2d');
    
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

function renderPredictions(predictions) {
    const tbody = document.getElementById("hotspots-tbody");
    if (!tbody) return;
    tbody.innerHTML = "";

    predictions.forEach(h => {
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
let deckgl = null;

function renderMap(hotspots) {
    const container = document.getElementById('heatmap-container');
    if (!container) return;
    
    if (deckgl) {}

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
            <div style="color: #131315; font-family: Inter, sans-serif; min-width: 150px; padding: 2px;">
                <strong style="display: block; font-size: 15px; margin-bottom: 4px; border-bottom: 1px solid #ccc; padding-bottom: 4px;">
                    ${h.top_junction || 'No Junction'}
                </strong>
                <div style="font-size: 13px;">📍 Station: ${h.top_station}</div>
                <div style="font-size: 13px; font-weight: bold; margin-top: 4px;">📊 Violations: ${h.violation_count}</div>
                <div style="font-size: 13px; color: ${hex}; font-weight: bold;">⚠️ CRS: ${h.crs.toFixed(4)}</div>
                
                <div style="margin-top: 6px; padding-top: 6px; border-top: 1px dashed rgba(0,0,0,0.2);">
                    <div style="font-size: 13px; color: #d93025; font-weight: bold;">🚗 Traffic Delay: +${h.live_traffic_delay_mins || 0} mins</div>
                    <div style="font-size: 13px; color: #1a73e8; font-weight: bold;">⏱️ Live Speed: ${h.live_avg_speed_kmh || 0} km/h</div>
                </div>
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

// Live Traffic Polling: Fetches new simulated traffic metrics every 8 seconds
setInterval(async () => {
    try {
        const hotspotsRes = await fetch(`${API_BASE}/hotspots?top_n=150`);
        const hotspotsData = await hotspotsRes.json();
        window.allHotspots = hotspotsData.hotspots;
        
        // Preserve active search filtering
        const searchInput = document.getElementById('search-input');
        const term = searchInput ? searchInput.value.toLowerCase() : '';
        
        if (!window.timeLapseActive) {
            if (term) {
                const filteredMap = window.allHotspots.filter(h => 
                    (h.top_junction && h.top_junction.toLowerCase().includes(term)) ||
                    (h.top_station && h.top_station.toLowerCase().includes(term))
                );
                renderMap(filteredMap);
            } else {
                renderMap(window.allHotspots);
            }
        }
    } catch (e) {
        console.warn("Live traffic sync failed", e);
    }
}, 8000);

// ==========================================
// Time-Lapse Slider Logic
// ==========================================
document.addEventListener("DOMContentLoaded", () => {
    window.timeLapseActive = false;
    const slider = document.getElementById('timelapse-slider');
    const label = document.getElementById('timelapse-label');
    const playBtn = document.getElementById('timelapse-play');
    let playInterval = null;

    if (slider && label) {
        slider.addEventListener('input', (e) => {
            window.timeLapseActive = true;
            const hour = parseInt(e.target.value);
            const hourStr = hour.toString().padStart(2, '0');
            label.innerText = `${hourStr}:00`;
            
            if (window.hourlyDistribution && window.allHotspots) {
                // Calculate intensity ratio based on historical hourly distribution
                const count = window.hourlyDistribution[hourStr] || 0;
                // Minimum 10% intensity so the map doesn't go completely black
                const ratio = Math.max(0.1, count / window.maxHourly);
                
                const simulatedHotspots = window.allHotspots.map(h => {
                    // Add micro-variance so hotspots pulse slightly differently
                    const variance = ((h.cluster_id % 7) / 30); 
                    const multiplier = Math.max(0.1, ratio + variance - 0.1);
                    return {
                        ...h,
                        violation_count: Math.round(h.violation_count * multiplier),
                        crs: h.crs * multiplier,
                        live_traffic_delay_mins: Math.round(h.live_traffic_delay_mins * multiplier),
                        live_avg_speed_kmh: Math.round(40 - ((40 - h.live_avg_speed_kmh) * multiplier))
                    };
                });
                
                renderMap(simulatedHotspots);
            }
        });
    }

    if (playBtn) {
        playBtn.addEventListener('click', () => {
            if (playInterval) {
                // Stop playback and return to LIVE
                clearInterval(playInterval);
                playInterval = null;
                document.getElementById('timelapse-icon').innerText = 'play_arrow';
                label.innerText = 'LIVE';
                window.timeLapseActive = false;
                renderMap(window.allHotspots); 
            } else {
                // Start playback
                document.getElementById('timelapse-icon').innerText = 'stop';
                window.timeLapseActive = true;
                let currentHour = parseInt(slider.value);
                
                playInterval = setInterval(() => {
                    currentHour = (currentHour + 1) % 24;
                    slider.value = currentHour;
                    slider.dispatchEvent(new Event('input'));
                }, 600); // Fast 600ms per hour progression
            }
        });
    }
});


// ==========================================
// Voice Command System (Web Speech API)
// ==========================================
let voiceRecognition = null;
let voiceActive = false;

function toggleVoice() {
    if (voiceActive) { stopVoice(); } else { startVoice(); }
}

function showVoiceOverlay(show) {
    const overlay = document.getElementById('voice-overlay');
    if (!overlay) return;
    if (show) {
        overlay.style.display = 'flex';
        requestAnimationFrame(() => { overlay.style.opacity = '1'; overlay.style.pointerEvents = 'auto'; });
    } else {
        overlay.style.opacity = '0';
        overlay.style.pointerEvents = 'none';
        setTimeout(() => overlay.style.display = 'none', 300);
    }
}

function setVoiceStatus(text, color) {
    const el = document.getElementById('voice-status');
    if (el) { el.innerText = text; el.style.color = color || ''; }
}

function startVoice() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) { alert('Voice commands not supported. Use Chrome.'); return; }

    voiceRecognition = new SpeechRecognition();
    voiceRecognition.lang = 'en-IN';
    voiceRecognition.continuous = false;
    voiceRecognition.interimResults = true;
    voiceActive = true;
    showVoiceOverlay(true);
    setVoiceStatus('Listening...', '#00DAF3');

    const btn = document.getElementById('voice-btn');
    const icon = document.getElementById('voice-icon');
    if (btn) btn.classList.add('bg-primary/20', 'text-primary');
    if (icon) icon.innerText = 'mic';

    voiceRecognition.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        const isFinal = event.results[0].isFinal;
        const transcriptEl = document.getElementById('voice-transcript');
        if (transcriptEl) transcriptEl.innerText = '"' + transcript + '"';
        if (isFinal) processVoiceCommand(transcript.toLowerCase().trim());
    };

    voiceRecognition.onerror = (event) => {
        console.warn('Voice error:', event.error);
        if (event.error === 'no-speech') {
            setVoiceStatus('No speech detected. Try again.', '#FF4E7A');
        } else {
            setVoiceStatus('Error: ' + event.error, '#FF4E7A');
        }
        setTimeout(() => stopVoice(), 1500);
    };

    voiceRecognition.onend = () => {
        if (voiceActive) setTimeout(() => stopVoice(), 2000);
    };

    voiceRecognition.start();
}

function stopVoice() {
    voiceActive = false;
    if (voiceRecognition) {
        try { voiceRecognition.stop(); } catch(e) {}
        voiceRecognition = null;
    }
    showVoiceOverlay(false);
    const btn = document.getElementById('voice-btn');
    const icon = document.getElementById('voice-icon');
    if (btn) btn.classList.remove('bg-primary/20', 'text-primary');
    if (icon) icon.innerText = 'mic';
    const transcriptEl = document.getElementById('voice-transcript');
    if (transcriptEl) transcriptEl.innerText = '';
}

function processVoiceCommand(command) {
    console.log('Voice command:', command);

    // Refresh Data
    if (command.includes('refresh') || command.includes('reload') || command.includes('update data')) {
        setVoiceStatus('Refreshing data...', '#00DAF3');
        fetchData();
        return;
    }

    // Generate Patrol Brief
    if (command.includes('patrol') || command.includes('brief') || command.includes('generate')) {
        setVoiceStatus('Navigating to Patrol Brief...', '#00DAF3');
        setTimeout(() => { window.location.href = 'patrol.html'; }, 800);
        return;
    }

    // Reset / Show All
    if (command.includes('reset') || command.includes('show all') || command.includes('clear')) {
        setVoiceStatus('Resetting map to all hotspots', '#00DAF3');
        const si = document.getElementById('search-input');
        if (si) { si.value = ''; si.dispatchEvent(new Event('input')); }
        if (window.allHotspots) renderMap(window.allHotspots);
        return;
    }

    // Go Home
    if (command.includes('go home') || command.includes('home page') || command.includes('homepage')) {
        setVoiceStatus('Going to homepage...', '#00DAF3');
        setTimeout(() => { window.location.href = 'index.html'; }, 800);
        return;
    }

    // Show/Hide Patrol Route
    if (command.includes('route') || command.includes('patrol route')) {
        setVoiceStatus('Toggling patrol route...', '#00DAF3');
        togglePatrolRoute();
        return;
    }

    // Show [Location] - catch-all search
    const locationKeywords = ['show', 'search', 'find', 'go to', 'navigate', 'zoom', 'where is', 'locate'];
    let searchTerm = command;
    for (const kw of locationKeywords) { searchTerm = searchTerm.replace(kw, '').trim(); }
    searchTerm = searchTerm.replace(/\b(me|the|to|in|at|on|for)\b/g, '').replace(/\s+/g, ' ').trim();

    if (searchTerm.length > 1) {
        setVoiceStatus('Searching: "' + searchTerm + '"', '#00DAF3');
        const si = document.getElementById('search-input');
        if (si) { si.value = searchTerm; si.dispatchEvent(new Event('input')); }

        // Fly map to first matching hotspot
        if (window.allHotspots && mapInstance) {
            const match = window.allHotspots.find(h =>
                (h.top_junction && h.top_junction.toLowerCase().includes(searchTerm)) ||
                (h.top_station && h.top_station.toLowerCase().includes(searchTerm))
            );
            if (match) {
                mapInstance.flyTo({
                    center: [match.centroid_lng, match.centroid_lat],
                    zoom: 15, pitch: 45, duration: 2000
                });
            }
        }
        return;
    }

    setVoiceStatus('Command not recognized. Try again.', '#FF4E7A');
}

// Keyboard shortcut: Press V to toggle voice (when not typing in an input)
document.addEventListener('keydown', (e) => {
    if (e.key === 'v' && document.activeElement.tagName !== 'INPUT' && document.activeElement.tagName !== 'TEXTAREA') {
        e.preventDefault();
        toggleVoice();
    }
});

// ==========================================
// Animated Patrol Route on Map
// ==========================================
let patrolRouteActive = false;
let patrolAnimationFrame = null;
let patrolDotMarker = null;

function togglePatrolRoute() {
    if (patrolRouteActive) {
        removePatrolRoute();
    } else {
        drawPatrolRoute();
    }
}

function drawPatrolRoute() {
    if (!mapInstance || !window.allHotspots || window.allHotspots.length < 2) return;

    patrolRouteActive = true;

    // Update button style
    const btn = document.getElementById('patrol-route-btn');
    if (btn) {
        btn.classList.add('bg-primary/20', 'text-primary', 'border-primary/50');
        btn.classList.remove('bg-surface-variant/50', 'text-on-surface-variant', 'border-white/10');
    }

    // Take top 8 hotspots by CRS (these form the patrol route)
    const routeHotspots = window.allHotspots
        .sort((a, b) => (b.crs || 0) - (a.crs || 0))
        .slice(0, 8);

    // Build coordinate array for the route line
    const coordinates = routeHotspots.map(h => [h.centroid_lng, h.centroid_lat]);
    // Close the loop back to start
    coordinates.push(coordinates[0]);

    // Wait for map style to be loaded
    const addRoute = () => {
        // Remove existing route layers if any
        if (mapInstance.getSource('patrol-route')) {
            mapInstance.removeLayer('patrol-route-glow');
            mapInstance.removeLayer('patrol-route-line');
            mapInstance.removeLayer('patrol-route-arrows');
            mapInstance.removeSource('patrol-route');
        }

        // Add route source
        mapInstance.addSource('patrol-route', {
            type: 'geojson',
            data: {
                type: 'Feature',
                geometry: { type: 'LineString', coordinates: coordinates }
            }
        });

        // Glow layer (wider, transparent)
        mapInstance.addLayer({
            id: 'patrol-route-glow',
            type: 'line',
            source: 'patrol-route',
            paint: {
                'line-color': '#00DAF3',
                'line-width': 12,
                'line-opacity': 0.15,
                'line-blur': 8
            }
        });

        // Main route line (dashed for movement feel)
        mapInstance.addLayer({
            id: 'patrol-route-line',
            type: 'line',
            source: 'patrol-route',
            paint: {
                'line-color': '#00DAF3',
                'line-width': 3,
                'line-opacity': 0.9,
                'line-dasharray': [2, 2]
            }
        });

        // Arrow symbols along the route
        mapInstance.addLayer({
            id: 'patrol-route-arrows',
            type: 'symbol',
            source: 'patrol-route',
            layout: {
                'symbol-placement': 'line',
                'symbol-spacing': 80,
                'text-field': '▶',
                'text-size': 12,
                'text-rotation-alignment': 'map',
                'text-allow-overlap': true,
                'text-ignore-placement': true
            },
            paint: {
                'text-color': '#00DAF3',
                'text-opacity': 0.8
            }
        });

        // Animate the dash offset to create movement
        let dashOffset = 0;
        function animateDash() {
            if (!patrolRouteActive) return;
            dashOffset = (dashOffset + 0.5) % 4;
            mapInstance.setPaintProperty('patrol-route-line', 'line-dasharray', [2, 2]);
            patrolAnimationFrame = requestAnimationFrame(animateDash);
        }
        animateDash();

        // Add the moving patrol dot
        addPatrolDot(coordinates);

        // Add numbered stop markers
        addStopMarkers(routeHotspots);
    };

    if (mapInstance.isStyleLoaded()) {
        addRoute();
    } else {
        mapInstance.on('load', addRoute);
    }
}

function addPatrolDot(coordinates) {
    // Remove existing dot
    if (patrolDotMarker) patrolDotMarker.remove();

    // Create the glowing patrol dot element
    const dotEl = document.createElement('div');
    dotEl.innerHTML = `
        <div style="position:relative; width:24px; height:24px;">
            <div style="position:absolute; inset:0; border-radius:50%; background:rgba(57,255,20,0.3); animation: patrol-ping 1.5s cubic-bezier(0,0,0.2,1) infinite;"></div>
            <div style="position:absolute; inset:4px; border-radius:50%; background:#39FF14; border:2px solid #fff; box-shadow:0 0 15px #39FF14;"></div>
        </div>
    `;

    // Add the ping animation via a style tag if not already added
    if (!document.getElementById('patrol-dot-style')) {
        const style = document.createElement('style');
        style.id = 'patrol-dot-style';
        style.textContent = `
            @keyframes patrol-ping {
                0% { transform: scale(1); opacity: 0.8; }
                75%, 100% { transform: scale(2.5); opacity: 0; }
            }
        `;
        document.head.appendChild(style);
    }

    patrolDotMarker = new maplibregl.Marker({ element: dotEl })
        .setLngLat(coordinates[0])
        .addTo(mapInstance);

    // Animate the dot along the route
    let progress = 0;
    const totalSegments = coordinates.length - 1;
    const speed = 0.003; // Controls animation speed

    function animateDot() {
        if (!patrolRouteActive) return;

        progress += speed;
        if (progress >= totalSegments) progress = 0;

        const segmentIndex = Math.floor(progress);
        const segmentProgress = progress - segmentIndex;

        const start = coordinates[segmentIndex];
        const end = coordinates[Math.min(segmentIndex + 1, coordinates.length - 1)];

        // Interpolate position
        const lng = start[0] + (end[0] - start[0]) * segmentProgress;
        const lat = start[1] + (end[1] - start[1]) * segmentProgress;

        patrolDotMarker.setLngLat([lng, lat]);
        requestAnimationFrame(animateDot);
    }
    requestAnimationFrame(animateDot);
}

// Store stop markers so we can remove them later
window.patrolStopMarkers = [];

function addStopMarkers(hotspots) {
    // Remove old ones
    if (window.patrolStopMarkers) {
        window.patrolStopMarkers.forEach(m => m.remove());
    }
    window.patrolStopMarkers = [];

    hotspots.forEach((h, i) => {
        const el = document.createElement('div');
        el.style.cssText = `
            width: 22px; height: 22px; border-radius: 50%;
            background: linear-gradient(135deg, #00DAF3, #0088cc);
            border: 2px solid #fff; color: #fff;
            display: flex; align-items: center; justify-content: center;
            font-size: 11px; font-weight: 700; font-family: 'Inter', sans-serif;
            box-shadow: 0 0 10px rgba(0,218,243,0.5);
            cursor: pointer;
        `;
        el.innerText = (i + 1).toString();
        el.title = `Stop ${i + 1}: ${h.top_junction || h.top_station || 'Hotspot'}`;

        const popup = new maplibregl.Popup({ offset: 15, closeButton: false }).setHTML(`
            <div style="color: #131315; font-family: Inter, sans-serif; padding: 4px;">
                <strong style="font-size:13px;">Stop ${i + 1}</strong><br>
                <span style="font-size:12px;">${h.top_junction || 'Unknown Junction'}</span><br>
                <span style="font-size:12px; color:#d93025; font-weight:bold;">CRS: ${(h.crs || 0).toFixed(4)}</span>
            </div>
        `);

        const marker = new maplibregl.Marker({ element: el })
            .setLngLat([h.centroid_lng, h.centroid_lat])
            .addTo(mapInstance);

        el.addEventListener('mouseenter', () => popup.setLngLat([h.centroid_lng, h.centroid_lat]).addTo(mapInstance));
        el.addEventListener('mouseleave', () => popup.remove());

        window.patrolStopMarkers.push(marker);
    });
}

function removePatrolRoute() {
    patrolRouteActive = false;

    // Update button style
    const btn = document.getElementById('patrol-route-btn');
    if (btn) {
        btn.classList.remove('bg-primary/20', 'text-primary', 'border-primary/50');
        btn.classList.add('bg-surface-variant/50', 'text-on-surface-variant', 'border-white/10');
    }

    // Cancel animation
    if (patrolAnimationFrame) {
        cancelAnimationFrame(patrolAnimationFrame);
        patrolAnimationFrame = null;
    }

    // Remove dot
    if (patrolDotMarker) {
        patrolDotMarker.remove();
        patrolDotMarker = null;
    }

    // Remove stop markers
    if (window.patrolStopMarkers) {
        window.patrolStopMarkers.forEach(m => m.remove());
        window.patrolStopMarkers = [];
    }

    // Remove map layers and source
    if (mapInstance) {
        try {
            if (mapInstance.getLayer('patrol-route-glow')) mapInstance.removeLayer('patrol-route-glow');
            if (mapInstance.getLayer('patrol-route-line')) mapInstance.removeLayer('patrol-route-line');
            if (mapInstance.getLayer('patrol-route-arrows')) mapInstance.removeLayer('patrol-route-arrows');
            if (mapInstance.getSource('patrol-route')) mapInstance.removeSource('patrol-route');
        } catch (e) { console.warn('Patrol route cleanup:', e); }
    }
}
