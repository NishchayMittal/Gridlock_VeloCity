# 🚦 Gridlock — AI-Driven Parking Intelligence

Gridlock is a next-generation traffic enforcement Command Center designed to solve the problem of parking-induced congestion. It shifts traffic enforcement from a *reactive patrol* model to a *proactive, intelligence-driven* model.

## ⚠️ The Problem
On-street illegal parking and spillover parking near commercial areas, metro stations, and events choke carriageways and intersections. Today, enforcement is patrol-based and blind—there is no real-time visibility or heatmap of parking violations versus their actual impact on congestion, making it impossible to prioritize enforcement zones effectively.

## 🚀 The Solution
Gridlock leverages machine learning and spatial clustering to process raw violation data, detect illegal parking hotspots, and quantify their impact on traffic flow via a proprietary **Congestion Risk Score (CRS)**. 

### Key Features
* **Interactive Command Center**: A glassmorphic, state-of-the-art dashboard featuring a live, glowing thermal map (powered by Deck.gl) of the city's highest-risk parking zones.
* **Congestion Risk Score (CRS)**: An algorithmic metric that weights violation density, temporal recurrence, and enforcement delay to determine true congestion impact.
* **Predictive AI Modeling**: LightGBM-powered forecasting that predicts *tomorrow's* highest-risk intersections before they happen.
* **LLM Patrol Briefs**: Generative AI (Llama 3 via Groq) automatically synthesizes daily intelligence into actionable, localized patrol briefs for field officers.

## 🛠️ Tech Stack
* **Frontend**: Vanilla JS, HTML, Tailwind CSS, Deck.gl, MapLibre GL JS, Chart.js
* **Backend**: FastAPI (Python), Uvicorn
* **Data Intelligence**: Pandas, Scikit-learn (DBSCAN Clustering), LightGBM
* **LLM Integration**: Groq API (Llama-3-8b-instant)

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

### 2. Start the Backend API
The FastAPI server handles data processing, ML inference, and LLM generation.
```bash
# Run the FastAPI server on port 8001
uvicorn api:app --port 8001 --reload
```

### 3. Start the Frontend Dashboard
Open a new terminal window in the root directory.
```bash
# Start a simple HTTP server on port 3000
python -m http.server 3000
```

### 4. Access the Command Center
Open your web browser and navigate to:
[http://localhost:3000](http://localhost:3000)