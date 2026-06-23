# 🚦 VeloCity — AI-Driven Parking Intelligence

VeloCity is a next-generation traffic enforcement Command Center designed to solve the problem of parking-induced congestion. It shifts traffic enforcement from a *reactive patrol* model to a *proactive, intelligence-driven* model.

## 🌐 Live Demo
* **Application**: [https://gridlock-velocity.vercel.app](https://gridlock-velocity.vercel.app)
* **Command Center**: [https://gridlock-velocity.vercel.app/dashboard.html](https://gridlock-velocity.vercel.app/dashboard.html)

---

## ⚠️ The Problem
On-street illegal parking and spillover parking near commercial areas, metro stations, and events choke carriageways and intersections. Today, enforcement is patrol-based and blind—there is no real-time visibility or heatmap of parking violations versus their actual impact on congestion, making it impossible to prioritize enforcement zones effectively.

## 🚀 The Solution
VeloCity leverages machine learning and spatial clustering to process raw violation data, detect illegal parking hotspots, and quantify their impact on traffic flow via a proprietary **Congestion Risk Score (CRS)**. 

### Core Modules & Pages
1. **The VeloCity Homepage (`index.html`)**
   - **Live Impact Simulator**: Real-time "Before vs After" simulation showing the immediate reduction in CRS if enforcement gaps are closed.
   - **3D City Canvas**: An immersive Three.js animated background depicting a living, breathing city grid.

2. **The Command Center (`dashboard.html`)**
   - **Interactive 3D Hotspot Map**: A glassmorphic, state-of-the-art dashboard featuring a live, glowing thermal map (powered by Deck.gl) of the city's highest-risk parking zones.
   - **Voice-Command AI**: Integrated Web Speech API allows operators to voice-command the map (e.g., "Find hotspots in Electronic City").
   - **Optimized Patrol Routing**: Automatically plots and animates a highly strategic enforcement route connecting the top hotspots directly on the 3D map.
   - **SCITA Revenue Recovery**: Identifies violations never reported to the central SCITA system and quantifies the resulting phantom revenue leakage, enabling recovery of lost fines.

3. **AI Patrol Operations (`patrol.html`)**
   - **Predictive AI Modeling**: LightGBM-powered forecasting that predicts *tomorrow's* highest-risk intersections before they happen.
   - **LLM Patrol Briefs**: Generative AI (Llama 3 via Groq) automatically synthesizes daily intelligence into actionable, localized patrol briefs for field officers.

---

## 🎨 Advanced UI/UX
The VeloCity frontend was built from the ground up to feel like a true, high-tech "Mission Control" interface:
* **Glassmorphism & HUD Aesthetics**: Deep blacks, glowing cyan/magenta accents, monospace system fonts, and blurred frosted-glass panels.
* **VeloCity Core Loader**: A mathematically precise, pure-CSS 3D orbital loading animation with spinning X/Y axis rings and simulated floating data nodes.
* **Micro-interactions**: Glowing hover states, active pulsing indicators, and real-time scanning radar animations.

---

## 🛠️ Tech Stack
* **Frontend**: Vanilla JS, HTML, Tailwind CSS, Deck.gl, MapLibre GL JS, Chart.js, Three.js
* **Backend**: FastAPI (Python), Uvicorn
* **Data Intelligence**: Pandas, Scikit-learn (DBSCAN Clustering), LightGBM
* **LLM Integration**: Groq API (Llama-3-8b-instant)
* **Deployment**: Vercel (Frontend), Render/Local (Backend)

---

## 💻 How to Run Locally

### 1. Installation
Ensure you have Python installed.
```bash
# Clone the repository
git clone https://github.com/Amogh017/Gridlock.git
cd Gridlock

# Install dependencies
pip install -r requirements.txt
```

### 2. Environment Variables
Create a `.env` file in the root directory and add your Groq API key (required for AI Patrol Briefs):
```env
GROQ_API_KEY=your_api_key_here
```

### 3. Start the Backend API
The FastAPI server handles data processing, ML inference, and LLM generation.
```bash
# Run the FastAPI server on port 8001
uvicorn api:app --port 8001 --reload
```

### 4. Start the Frontend Dashboard
Open a new terminal window in the root directory.
```bash
# Start a simple HTTP server on port 3000
python -m http.server 3000
```

### 5. Access the Command Center
Open your web browser and navigate to:
[http://localhost:3000](http://localhost:3000)
