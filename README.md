# FinFlow — Packing and Order Fulfilment Web Solution for Fintr (Group 28)

**Course:** BFB 321 — Supply Chain Technologies  
**Group:** Group 28  

## Project Description

**FinFlow** is a supply chain web application designed for **Fintr** to streamline order intake, carton packing, stock reservation, and courier tariff calculation for the **FinMaster** financial education board game (`FM-2026-CN`) as monthly fulfilment scales from 32 to over 500 units.

This Semester Project submission comprises:
1. **Step 1 — Frontend Implementation (`templates/`, `css/`, `js/`):** A responsive 3-page web interface consisting of a landing hub (`index.html`), a supply chain dashboard displaying EOQ metrics and outbound order shipping costs (`dashboard.html`), and an interactive 7-stage Takealot order fulfilment tracker (`sales_flow.html`).
2. **Step 2 — Standalone Supply Chain Model (`models/`, `tests/`):** A framework-independent Python module (`models/supply_chain.py`) implementing Economic Order Quantity (EOQ), Reorder Point (ROP), safety stock calculations, master-carton volumetric vs. actual billable weight breakdown, Courier Guy road-freight tariff calculation, and stock reservation validation, verified by unit tests (`tests/test_supply_chain.py`).

---

## Group Members

| Student Name | Student Number |
| :--- | :--- |
| Zaid Varachia | u24590772 |
| Mulanga Dau | u22678884 |
| Nicolas Mthombeni | u22683552 |

---

## Repository Structure

```text
BFB-Group-28-Project/
├── templates/                  # Step 1: Frontend HTML pages
│   ├── index.html              # Main landing hub & warehouse summary
│   ├── dashboard.html          # EOQ KPI cards & outbound order shipping table
│   └── sales_flow.html         # 7-step Takealot order fulfilment tracker
├── css/
│   └── style.css               # Responsive layout & component styling
├── js/
│   └── sales_flow.js           # Client-side order stage progression logic
├── models/                     # Step 2: Standalone Python supply chain module
│   ├── __init__.py
│   └── supply_chain.py         # EOQ, ROP, safety stock, carton & courier cost formulas
└── tests/                      # Step 2: Unit test suite
    ├── __init__.py
    └── test_supply_chain.py    # Pytest unit tests verifying supply chain calculations
```

---

## Installation & Setup Instructions

### 1. Viewing the Web Application (Step 1: Frontend)
1. Clone this repository and open the project folder in **Visual Studio Code**:
   ```bash
   git clone https://github.com/u24590772/BFB-Group-28-Project.git
   cd BFB-Group-28-Project
   ```
2. Open the [`templates/`](templates/) directory and locate [`index.html`](templates/index.html) (available on `main` and the `feature/frontend-ui` branch).
3. Right-click [`templates/index.html`](templates/index.html) and select **Open with Live Server** (or open `templates/index.html` directly in any web browser) to view and navigate between **Home**, **Dashboard**, and **Sales Flow**.

### 2. Running the Supply Chain Model & Unit Tests (Step 2: Python Module)
1. Ensure **Python 3.8+** is installed.
2. Install `pytest`:
   ```bash
   pip install pytest
   ```
3. Run the unit test suite from the root of the repository:
   ```bash
   pytest -v
   ```
