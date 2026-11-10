"""
Tests for the Flask back-end (app.py)
=====================================

BFB 321 - Group 28

Uses Flask's test client to request every page and API endpoint without
starting a server, and checks the answers against the supply chain model's
hand-calculated results and the group plan's 3 end-to-end scenarios.

Run from the project folder:
    python -m pytest -v
"""

import copy
import re

import pytest

import app as finflow


@pytest.fixture
def client():
    """A test browser for the app. The demo data is put back after each test,
    so one test's changes (like advancing an order) don't affect the next."""
    saved_orders = copy.deepcopy(finflow.orders)
    saved_inventory = dict(finflow.inventory)
    yield finflow.app.test_client()
    finflow.orders[:] = saved_orders
    finflow.inventory.clear()
    finflow.inventory.update(saved_inventory)


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

def test_pages_load(client):
    for path in ["/", "/dashboard", "/sales-flow"]:
        assert client.get(path).status_code == 200, path


def test_stylesheet_and_script_are_served(client):
    assert client.get("/static/css/style.css").status_code == 200
    assert client.get("/static/js/sales_flow.js").status_code == 200


def test_dashboard_shows_the_model_results(client):
    html = client.get("/dashboard").get_data(as_text=True)
    html = html.replace(chr(160), " ")  # the rand filter uses non-breaking spaces
    assert "306 <small>units</small>" in html  # EOQ
    assert "R 241.62" in html                  # 8 units in 2 cartons
    assert "R 8 857.30" in html                # 460 units in 115 cartons
    assert "Buffer breach" in html             # DEMO-ORD-008 is over the safety buffer


# ---------------------------------------------------------------------------
# JSON API
# ---------------------------------------------------------------------------

def test_api_inventory(client):
    assert client.get("/api/inventory").get_json() == {
        "stock_on_hand": 500,
        "safety_stock": 50,
        "available": 450,
        "eoq_recommended": 306,
        "reorder_point": 170,
    }


def test_api_orders_filter_by_status(client):
    data = client.get("/api/orders?status=Rejected").get_json()
    assert data["count"] == 1
    assert data["orders"][0]["order_ref"] == "DEMO-ORD-008"


def test_api_calculate_shipping(client):
    data = client.post("/api/calculate-shipping", json={"quantity": 8}).get_json()
    assert data["cartons_count"] == 2
    assert data["total_billable_weight"] == 15.6
    assert data["shipping_cost_zar"] == 241.62


def test_api_calculate_shipping_rejects_a_bad_quantity(client):
    response = client.post("/api/calculate-shipping", json={"quantity": 0})
    assert response.status_code == 400
    assert response.get_json()["status"] == "error"


def test_advance_moves_an_order_one_step(client):
    # DEMO-ORD-002 is on step 3 -> step 4, and the change is kept
    data = client.post("/api/sales-flow/2/advance").get_json()
    assert data["new_step"] == 4
    assert data["step_name"] == "Delivery Note on ERPNext"
    flow = client.get("/api/sales-flow").get_json()["orders"]
    assert [order["current_step"] for order in flow if order["id"] == 2] == [4]


def test_advance_refuses_dispatched_and_unknown_orders(client):
    assert client.post("/api/sales-flow/7/advance").status_code == 409  # already dispatched
    assert client.post("/api/sales-flow/3/advance").status_code == 400  # Shopify: not in the flow
    response = client.post("/api/sales-flow/99/advance")                 # no such order
    assert response.status_code == 404
    assert response.get_json()["status"] == "error"


# ---------------------------------------------------------------------------
# The group plan's 3 end-to-end scenarios (section 5.2)
# ---------------------------------------------------------------------------

def test_scenario_1_single_unit_order(client):
    # DEMO-ORD-001 (1 game) goes from step 1 to 7. At step 6 it is packed:
    # 1 carton, 1 waybill, and 1 unit leaves stock.
    for expected_step in range(2, 8):
        data = client.post("/api/sales-flow/1/advance").get_json()
        assert data["new_step"] == expected_step
        if expected_step == 6:
            assert len(data["waybills"]) == 1
            assert re.fullmatch(r"TCG-ZA-0001-1-[0-9A-F]{3}[0-9]", data["waybills"][0])
    assert data["is_dispatched"] is True
    assert client.get("/api/inventory").get_json()["stock_on_hand"] == 499


def test_scenario_2_bulk_order(client):
    # DEMO-ORD-002 (8 games) is split into 2 cartons, so it gets 2 waybills
    for expected_step in [4, 5, 6, 7]:
        data = client.post("/api/sales-flow/2/advance").get_json()
        assert data["new_step"] == expected_step
        if expected_step == 6:
            assert len(data["waybills"]) == 2
    assert client.post("/api/sales-flow/2/advance").status_code == 409
    assert client.get("/api/inventory").get_json()["stock_on_hand"] == 492


def test_scenario_3_safety_buffer_rejection(client):
    # DEMO-ORD-008: 460 units > 450 available above the buffer -> refused,
    # with a clear message, and the stock stays untouched
    response = client.post("/api/orders/8/pack")
    assert response.status_code == 409
    assert "Shortage of 10" in response.get_json()["message"]
    assert client.get("/api/inventory").get_json()["stock_on_hand"] == 500
