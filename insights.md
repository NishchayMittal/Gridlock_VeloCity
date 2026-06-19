# Gridlock Hackathon – EDA Findings

## Dataset Overview

### Dataset Statistics

| Metric          | Value      |
| --------------- | ---------- |
| Total Records   | 298,450    |
| Total Features  | 24         |
| Police Stations | 54         |
| Junctions       | 169        |
| Earliest Record | 2023-11-09 |
| Latest Record   | 2024-04-08 |

### Objective

The goal of this exploratory data analysis (EDA) is to identify spatial, temporal, and operational patterns in parking-related traffic violations that can support the development of an AI-driven parking intelligence platform for Bengaluru Traffic Police.

---

# Key Finding 1: Parking Violations Dominate the Dataset

The dataset is overwhelmingly composed of parking-related offences.

### Most Common Violation Types

| Violation Type                       |   Count |
| ------------------------------------ | ------: |
| Wrong Parking                        | 138,764 |
| No Parking                           | 119,576 |
| Parking in Main Road + Wrong Parking |   9,472 |
| Parking in Main Road + No Parking    |   4,818 |

### Insight

The dataset is highly aligned with the hackathon problem statement. Since the majority of recorded offences are parking-related, hotspot detection and enforcement optimization can directly target the primary source of violations.

---

# Key Finding 2: Parking Violations are Highly Concentrated Geographically

A small number of locations account for a disproportionately large number of violations.

### Top Junctions

| Junction                | Violations |
| ----------------------- | ---------: |
| Safina Plaza Junction   |     15,449 |
| KR Market Junction      |     11,538 |
| Elite Junction          |     10,718 |
| Sagar Theatre Junction  |     10,549 |
| Central Street Junction |      5,388 |

### Concentration Analysis

* Total violations across Top 10 Junctions: 75,132
* Total violations across all identified junctions: 150,565
* Top 10 Junction Share: **49.9%**

### Insight

Nearly half of all junction-level violations originate from only ten junctions. This suggests that targeted enforcement at a limited number of high-risk locations could significantly improve operational efficiency compared to uniform city-wide patrols.

---

# Key Finding 3: Enforcement Burden is Concentrated

Violation workload is unevenly distributed across police stations.

### Top Police Stations

| Police Station  | Violations |
| --------------- | ---------: |
| Upparpet        |     34,468 |
| Shivajinagar    |     28,044 |
| Malleshwaram    |     22,200 |
| HAL Old Airport |     20,819 |
| City Market     |     17,646 |

### Concentration Analysis

* Total violations handled by Top 10 Police Stations: 175,037
* Total violations in dataset: 298,445
* Top 10 Station Share: **58.65%**

### Insight

More than half of all violations are handled by only ten police stations, indicating that enforcement resources are already concentrated in a limited number of operational zones.

---

# Key Finding 4: Violations Follow Strong Time-Based Patterns

Timestamps were converted from UTC to IST before analysis.

### Peak Hours

| Hour (IST) | Violations |
| ---------- | ---------: |
| 10 AM      |     32,580 |
| 11 AM      |     32,176 |
| 9 AM       |     26,996 |
| 8 AM       |     25,790 |

### Insight

Parking violations peak during commercial and business activity hours, suggesting that congestion pressure is closely associated with daytime urban activity rather than late-night traffic.

### Operational Recommendation

Prioritize enforcement deployment during morning and late-morning periods when violation activity is highest.

---

# Key Finding 5: Strong Weekly Patterns Exist

Violation activity varies significantly across the week.

### Violations by Day

| Day       | Violations |
| --------- | ---------: |
| Sunday    |     50,162 |
| Saturday  |     44,523 |
| Thursday  |     43,547 |
| Tuesday   |     42,697 |
| Wednesday |     41,977 |
| Friday    |     40,864 |
| Monday    |     34,680 |

### Insight

Weekend activity contributes heavily to parking violations. Sundays record the highest violation volume in the dataset, indicating increased pressure around shopping, market, entertainment, and public gathering locations.

### Operational Recommendation

Increase patrol coverage and enforcement activity during weekends, particularly Sundays.

---

# Key Finding 6: Two-Wheelers and Cars Dominate Violations

### Top Vehicle Types

| Vehicle Type   | Violations |
| -------------- | ---------: |
| Scooter        |     94,856 |
| Car            |     88,870 |
| Motorcycle     |     40,811 |
| Passenger Auto |     37,813 |

### Insight

Two-wheelers and cars account for the overwhelming majority of parking violations. Parking management strategies and enforcement campaigns should primarily target these vehicle categories.

---

# Overall Conclusions

The analysis reveals several important characteristics of parking violations across Bengaluru:

1. Parking violations are the dominant offence category in the dataset.
2. Violations are highly concentrated geographically.
3. Enforcement workload is concentrated among a relatively small number of police stations.
4. Strong temporal patterns exist throughout the day.
5. Weekends experience significantly elevated violation activity.
6. Two-wheelers and cars account for the majority of recorded violations.

These findings support the development of a hotspot-driven parking intelligence system capable of:

* Detecting high-risk parking zones.
* Prioritizing enforcement deployment.
* Forecasting future hotspot activity.
* Generating AI-assisted patrol recommendations.
* Improving operational efficiency through data-driven decision making.

---

# Relevance to Proposed Solution

The EDA findings validate the core hypothesis behind the proposed system:

**Parking violations are not uniformly distributed across Bengaluru.**

Because violations are concentrated across specific locations, times, and vehicle categories, an AI-driven hotspot detection and risk scoring framework can help traffic authorities proactively allocate resources and address congestion-causing parking behavior before it escalates into larger traffic disruptions.
