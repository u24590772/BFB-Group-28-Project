"""
Tests for the Flask back-end & REST API (app.py)
================================================
BFB 321 - Group 28

Uses Flask's test client to request every page and API endpoint against
Aiven Cloud MySQL, verifying responses against the supply chain model's
hand-calculated results and the 3 end-to-end scenarios.

Run from project folder:
    pytest -v
"""

import re
import pytest

import app as finflow
import db


def reset_db_state():
    """Resets orders, inventory, and cartons back to the initial demo seed state."""
    conn = db.get_db()
    with conn.cursor() as cur:
        # Delete extra cartons and created orders
        cur.execute("DELETE FROM cartons WHERE order_id != 7")
        cur.execute("DELETE FROM orders WHERE id > 8")

        demo_orders = [
            (1, "DEMO-ORD-001", "Takealot",     1,   1,    "Pending"),
            (2, "DEMO-ORD-002", "Takealot",     8,   3,    "Pending"),
            (3, "DEMO-ORD-003", "Shopify",      2,   None, "Pending"),
            (4, "DEMO-ORD-004", "Takealot",     4,   5,    "Pending"),
            (5, "DEMO-ORD-005", "Direct email", 10,  None, "Pending"),
            (6, "DEMO-ORD-006", "Takealot",     6,   2,    "Pending"),
            (7, "DEMO-ORD-007", "Takealot",     12,  7,    "Dispatched"),
            (8, "DEMO-ORD-008", "Direct email", 460, None, "Rejected"),
        ]
        for oid, oref, ch, q, st, stat in demo_orders:
            cur.execute(
                "UPDATE orders SET order_ref=%s, channel=%s, quantity=%s, step=%s, status=%s WHERE id=%s",
                (oref, ch, q, st, stat, oid),
            )
        cur.execute(
            "UPDATE inventory SET stock_on_hand=500, safety_stock=50, reorder_point=170 WHERE item_code='FM-2026-CN'"
        )
    conn.commit()


@pytest.fixture(autouse=True)
def reset_database():
    """Restores database demo data before each test execution."""
    reset_db_state()
    yield
    reset_db_state()


@pytest.fixture
def client():
    """A Flask test client for HTTP requests."""
    return finflow.app.test_client()


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

def test_pages_load(client):
    for path in ["/", "/dashboard", "/sales-flow"]:
        assert client.get(path).status_code == 200, path


def test_stylesheet_and_script_are_served(client):
    assert client.get("/static/css/style.css").status_code == 200
    assert client.get("/static/js/sales_flow.js").status_code == 200
    assert client.get("/static/js/dashboard.js").status_code == 200


def test_dashboard_shows_the_model_results(client):
    html = client.get("/dashboard").get_data(as_text=True)
    html = html.replace(chr(160), " ")  # the rand filter uses non-breaking spaces
    assert "306 <small>units</small>" in html  # EOQ
    assert "R 241.62" in html                  # 8 units in 2 cartons
    assert "R 8 857.30" in html                # 460 units in 115 cartons
    assert "Buffer breach" in html             # DEMO-ORD-008 is over the safety buffer
    # Verify interactive tools are rendered on screen (Rubric B3.1)
    assert 'id="order-form"' in html
    assert 'id="calc-form"' in html


# ---------------------------------------------------------------------------
# JSON API & CRUD (Rubric B2.1, B2.2, B2.4)
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


def test_api_orders_pagination_and_filtering(client):
    # Rubric B2.4: filtering and pagination
    data = client.get("/api/orders?channel=Takealot&page=1&limit=2").get_json()
    assert data["status"] == "success"
    assert data["count"] == 2
    assert data["orders"][0]["channel"] == "Takealot"


def test_api_create_and_read_order(client):
    # Rubric B2.2: POST creates order, GET returns it
    create_resp = client.post("/api/orders", json={
        "order_ref": "TEST-NEW-099",
        "channel": "Takealot",
        "quantity": 4,
    })
    assert create_resp.status_code == 201
    created_id = create_resp.get_json()["order"]["id"]

    get_resp = client.get(f"/api/orders/{created_id}")
    assert get_resp.status_code == 200
    assert get_resp.get_json()["order"]["order_ref"] == "TEST-NEW-099"
    assert get_resp.get_json()["order"]["quantity"] == 4


def test_api_update_order(client):
    # Rubric B2.2: PUT updates order in MySQL
    update_resp = client.put("/api/orders/1", json={"quantity": 5})
    assert update_resp.status_code == 200
    assert update_resp.get_json()["order"]["quantity"] == 5

    # Check persistence
    assert client.get("/api/orders/1").get_json()["order"]["quantity"] == 5


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
    # DEMO-ORD-002 is on step 3 -> step 4 in MySQL
    data = client.post("/api/sales-flow/2/advance").get_json()
    assert data["new_step"] == 4
    assert data["step_name"] == "Delivery Note on ERPNext"
    flow = client.get("/api/sales-flow").get_json()["orders"]
    assert [order["current_step"] for order in flow if order["id"] == 2] == [4]


def test_advance_refuses_dispatched_and_unknown_orders(client):
    assert client.post("/api/sales-flow/7/advance").status_code == 409  # already dispatched
    assert client.post("/api/sales-flow/3/advance").status_code == 400  # Shopify: not in flow
    response = client.post("/api/sales-flow/99/advance")                 # no such order
    assert response.status_code == 404
    assert response.get_json()["status"] == "error"


# ---------------------------------------------------------------------------
# The group plan's 3 end-to-end scenarios (section 5.2 / Rubric B3.1)
# ---------------------------------------------------------------------------

def test_scenario_1_single_unit_order(client):
    # DEMO-ORD-001 (1 game) goes from step 1 to 7. At step 6 it is packed:
    # 1 carton, 1 waybill, and 1 unit leaves stock in MySQL.
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
