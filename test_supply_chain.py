"""
Test runs for supply_chain.py
=============================

BFB 321 - Group 28 - Member 1

Calls every function in supply_chain.py with the test parameters from the
Implementation Guide (section 4.1) and stores each result in a variable.
The comment above each call shows the hand-calculated answer, so the stored
result can be compared with it by eye.

This file and supply_chain.py are in the same folder. Run it from that folder:
    python test_supply_chain.py
"""

# Import the functions to test. supply_chain.py is in the same folder as this
# file, so Python finds it directly by its name.
from supply_chain_model import (
    annual_holding_cost,
    annual_ordering_cost,
    calculate_carton_breakdown,
    calculate_courier_shipping_cost,
    calculate_eoq,
    calculate_safety_stock,
    check_stock_reservation,
    orders_per_year,
    reorder_point,
    total_annual_cost,
    track_inventory_level,
    z_score,
)


# ==============================================================================
# CALCULATION 1 - EOQ, SAFETY STOCK AND REORDER POINT
# Test parameters: D = 6000 units/year, S = R350 per order, H = R45/unit/year,
#                  250 working days, L = 5 days, 95 % service level,
#                  sigma_d = 13.5 units/day
# ==============================================================================

# Hand calculation: EOQ = 306 units, SS = 50 units, ROP = 170 units,
#                   total cost = R 15 997.75 (R 13 747.75 without safety stock)
eoq_result = calculate_eoq(6000, 350, 45)

# Orders per year at Q = 306: 6000 / 306 = 19.61
orders_per_year_result = orders_per_year(6000, 306)

# Ordering cost: (6000 / 306) x 350 = R 6 862.75
ordering_cost_result = annual_ordering_cost(6000, 306, 350)

# Holding cost with 50 units of safety stock: (306 / 2 + 50) x 45 = 203 x 45 = R 9 135.00
holding_cost_result = annual_holding_cost(306, 45, 50)

# Total annual cost with safety stock: 6 862.75 + 9 135.00 = R 15 997.75
total_cost_result = total_annual_cost(6000, 306, 350, 45, 50)

# z-score for a 95 % service level (z-table): 1.645
z_score_result = z_score(0.95)

# Safety stock at 95 %: 1.645 x 30.19 = 49.65 -> rounded up = 50 units
safety_stock_result = calculate_safety_stock(13.5, 5, 0.95)

# Reorder point: 24 x 5 + 50 = 170 units
reorder_point_result = reorder_point(24, 5, 50)


# ==============================================================================
# CALCULATION 2 - CARTONS AND COURIER GUY SHIPPING COST
# ==============================================================================

# Carton breakdown for 8 units: 2 cartons of 4 units,
#   each 5.2 kg actual, 7.8 kg volumetric, 7.8 kg billable
cartons_8_result = calculate_carton_breakdown(8)

# Shipping cost for 8 units: 15.6 kg billable;
#   (120 + (15.6 - 5) x 8.50) x 1.15 = 210.10 x 1.15 = R 241.62
shipping_8_result = calculate_courier_shipping_cost(8)

# ==============================================================================
# CALCULATION 3 - STOCK RESERVATION AGAINST THE 50-UNIT SAFETY BUFFER
# Each result is a pair: (approved True/False, message)
# ==============================================================================

# 8 units requested, 500 on hand: available = 500 - 50 = 450 -> approved
reservation_8_result = check_stock_reservation(8, 500, 50)

# 451 units requested, 500 on hand: 451 > 450 -> rejected, shortage of 1 unit
reservation_451_result = check_stock_reservation(451, 500, 50)


# ==============================================================================
# INVENTORY TRACKING
# ==============================================================================

# 500 on hand, orders of 8, 1, 10 and 4 units:
#   stock 500 -> 492 -> 491 -> 481 -> 477; status "Healthy"
#   orders until reorder = (477 - 170) / 5.75 = 53.39 -> rounded up = 54
tracker_result = track_inventory_level(500, [8, 1, 10, 4])

# 200 on hand, orders of 10, 10, 10 and 8 units:
#   stock 200 -> 190 -> 180 -> 170 -> 162; order 3 triggers the reorder;
#   status "Reorder Now"; recommended reorder = EOQ = 306 units
tracker_reorder_result = track_inventory_level(200, [10, 10, 10, 8])


# ==============================================================================
# SHOW THE STORED RESULTS
# ==============================================================================

print("Calculation 1 - EOQ, safety stock and reorder point", "\n")
print("  calculate_eoq:", eoq_result, "\n")
print("  orders_per_year:", orders_per_year_result, "\n")
print("  annual_ordering_cost:", ordering_cost_result, "\n")
print("  annual_holding_cost:", holding_cost_result, "\n")
print("  total_annual_cost:", total_cost_result, "\n")
print("  calculate_safety_stock (95 %):", safety_stock_result, "\n")
print("  reorder_point:", reorder_point_result, "\n\n")

print("Calculation 2 - cartons and Courier Guy shipping cost", "\n")
print("  calculate_carton_breakdown (8 units):", cartons_8_result, "\n")
print("  calculate_courier_shipping_cost (8 units):", shipping_8_result, "\n\n")

print("Calculation 3 - stock reservation", "\n")
print("  check_stock_reservation (8 units):", reservation_8_result, "\n")
print("  check_stock_reservation (451 units):", reservation_451_result, "\n\n")

print("Inventory tracking")
print("  track_inventory_level (500 on hand):", tracker_result)
print("  track_inventory_level (200 on hand):", tracker_reorder_result)