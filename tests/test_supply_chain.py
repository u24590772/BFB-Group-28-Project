"""
Unit tests for models/supply_chain.py
=====================================

BFB 321 - Group 28 - Member 1

Checks every calculation against the hand-calculated answers in the
Implementation Guide (section 4.1). Each test compares the function's result
with the hand calculation in the comment above it, so a wrong answer makes
pytest fail instead of only printing a number.

Run from the project folder (the one that contains models/ and tests/):
    python -m pytest -v
"""

import math
from fractions import Fraction

import pytest

from models.supply_chain import (
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

def test_eoq():
    # EOQ = sqrt(2 x 6000 x 350 / 45) = 305.5 -> 306 units
    # SS = 50 units, ROP = 24 x 5 + 50 = 170 units
    result = calculate_eoq(6000, 350, 45)
    assert result["EOQ"] == 306
    assert result["Safety Stock"] == 50
    assert result["Reorder Point"] == 170


def test_orders_and_annual_costs():
    # Orders per year at Q = 306: 6000 / 306 = 19.61
    assert orders_per_year(6000, 306) == pytest.approx(19.61, abs=0.01)
    # Ordering cost: (6000 / 306) x 350 = R 6 862.75
    assert annual_ordering_cost(6000, 306, 350) == pytest.approx(6862.75, abs=0.01)
    # Holding cost with 50 units of safety stock: (306 / 2 + 50) x 45 = R 9 135.00
    assert annual_holding_cost(306, 45, 50) == pytest.approx(9135.00, abs=0.01)
    # Total cost: R 13 747.75 without safety stock, R 15 997.75 with it
    assert total_annual_cost(6000, 306, 350, 45) == pytest.approx(13747.75, abs=0.01)
    assert total_annual_cost(6000, 306, 350, 45, 50) == pytest.approx(15997.75, abs=0.01)


def test_z_score_uses_the_service_level_given():
    # z-table: 95 % -> 1.645, 99 % -> 2.326
    assert z_score(0.95) == pytest.approx(1.645, abs=0.001)
    assert z_score(0.99) == pytest.approx(2.326, abs=0.001)


def test_safety_stock():
    # 95 %: 1.645 x 13.5 x sqrt(5) = 49.65 -> 50 units
    assert calculate_safety_stock(13.5, 5, 0.95) == 50
    # 99 %: 2.326 x 13.5 x sqrt(5) = 70.2 -> 70 units
    assert calculate_safety_stock(13.5, 5, 0.99) == 70


def test_reorder_point():
    # 24 x 5 + 50 = 170 units
    assert reorder_point(24, 5, 50) == 170


# ==============================================================================
# CALCULATION 2 - CARTONS AND COURIER GUY SHIPPING COST
# ==============================================================================

def test_carton_breakdown():
    # 8 units: 2 cartons of 4; each 5.2 kg actual, 7.8 kg volumetric, 7.8 kg billable
    cartons = calculate_carton_breakdown(8)
    assert [c["units"] for c in cartons] == [4, 4]
    for carton in cartons:
        assert carton["actual_gross_weight_kg"] == pytest.approx(5.2)
        assert carton["volumetric_weight_kg"] == pytest.approx(7.8)
        assert carton["billable_weight_kg"] == pytest.approx(7.8)
    # 10 units: full cartons first, the remainder last -> 4 + 4 + 2
    assert [c["units"] for c in calculate_carton_breakdown(10)] == [4, 4, 2]


def test_courier_shipping_cost():
    # 8 units: 15.6 kg billable; (120 + (15.6 - 5) x 8.50) x 1.15 = R 241.62
    result = calculate_courier_shipping_cost(8)
    assert result["total_billable_weight_kg"] == 15.6
    assert result["total_shipping_cost"] == 241.62


# The demo orders shown on the frontend dashboard (templates/dashboard.html)
@pytest.mark.parametrize(
    "quantity, cartons, billable_kg, cost",
    [
        (1, 1, 7.8, 165.37),
        (2, 1, 7.8, 165.37),
        (4, 1, 7.8, 165.37),
        (6, 2, 15.6, 241.62),
        (8, 2, 15.6, 241.62),
        (10, 3, 23.4, 317.86),
        (12, 3, 23.4, 317.86),
        (460, 115, 897.0, 8857.30),
    ],
)
def test_dashboard_demo_orders(quantity, cartons, billable_kg, cost):
    assert len(calculate_carton_breakdown(quantity)) == cartons
    result = calculate_courier_shipping_cost(quantity)
    assert result["total_billable_weight_kg"] == billable_kg
    assert result["total_shipping_cost"] == cost


def test_shipping_cost_is_right_to_the_cent_for_every_order_size():
    # Works out the exact answer with fractions (no float rounding at all) and
    # rounds half cents up. With plain floats, 444 of these 1000 order sizes
    # came out 1 cent low.
    for quantity in range(1, 1001):
        billable_kg = Fraction(78, 10) * math.ceil(quantity / 4)
        exact = (120 + max(0, billable_kg - 5) * Fraction(85, 10)) * Fraction(115, 100)
        cents = math.floor(exact * 100 + Fraction(1, 2))  # round half up
        assert calculate_courier_shipping_cost(quantity)["total_shipping_cost"] == cents / 100, quantity


# ==============================================================================
# CALCULATION 3 - STOCK RESERVATION AGAINST THE 50-UNIT SAFETY BUFFER
# Each result is a pair: (approved True/False, message)
# ==============================================================================

def test_stock_reservation():
    # 8 units requested, 500 on hand: available = 500 - 50 = 450 -> approved
    approved, message = check_stock_reservation(8, 500, 50)
    assert approved is True
    # Exactly 450 is still allowed: the buffer stays untouched
    assert check_stock_reservation(450, 500, 50)[0] is True
    # 451 units: 451 > 450 -> rejected, shortage of 1 unit
    approved, message = check_stock_reservation(451, 500, 50)
    assert approved is False
    assert "Shortage of 1" in message
    # 460 units (DEMO-ORD-008 on the dashboard) -> rejected
    assert check_stock_reservation(460, 500, 50)[0] is False


def test_invalid_inputs_raise_value_error():
    with pytest.raises(ValueError):
        calculate_carton_breakdown(0)
    with pytest.raises(ValueError):
        check_stock_reservation(-5, 500, 50)
    with pytest.raises(ValueError):
        track_inventory_level(500, [8], expected_order_size=0)


# ==============================================================================
# INVENTORY TRACKING
# ==============================================================================

def test_track_inventory_healthy():
    # 500 on hand, orders of 8, 1, 10 and 4: stock 500 -> 477; status "Healthy"
    # orders until reorder = (477 - 170) / 5.75 = 53.39 -> rounded up = 54
    result = track_inventory_level(500, [8, 1, 10, 4])
    assert result["current_stock"] == 477
    assert result["stock_status"] == "Healthy"
    assert result["orders_until_reorder"] == 54
    assert result["recommended_reorder_qty"] == 0


def test_track_inventory_reorder_now():
    # 200 on hand, orders of 10, 10, 10 and 8: stock 200 -> 162; order 3 takes
    # stock to 170 (the ROP); status "Reorder Now"; reorder the EOQ = 306 units
    result = track_inventory_level(200, [10, 10, 10, 8])
    assert result["current_stock"] == 162
    assert result["reorder_triggered_at_order"] == 3
    assert result["stock_status"] == "Reorder Now"
    assert result["recommended_reorder_qty"] == 306


def test_track_inventory_optional_arguments():
    # Passing these used to crash: _require_int and _require_positive_number were missing.
    # Buffer 60 -> ROP = 24 x 5 + 60 = 180; one order of 8 leaves 492;
    # orders until reorder = (492 - 180) / 8 = 39
    result = track_inventory_level(500, [8], expected_order_size=8, safety_buffer=60)
    assert result["safety_stock"] == 60
    assert result["reorder_point"] == 180
    assert result["orders_until_reorder"] == 39


def test_every_name_in_all_exists():
    # "from models.supply_chain import *" crashes if __all__ names something missing
    import models.supply_chain as supply_chain
    for name in supply_chain.__all__:
        assert hasattr(supply_chain, name), name
