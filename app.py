"""
FinFlow – Flask back-end
BFB 321 – Group 28

Connects the three pages in templates/, the supply chain model in
models/supply_chain.py and the order data.

For now the data lives in the inventory and orders variables below, the same
way the lecturer's example keeps products in a list. In Milestone 2 those two
variables move into the MySQL database.

Run it from the project folder:
    python app.py
then open http://127.0.0.1:5000 in your browser.
"""

import random
import time

from flask import Flask, abort, jsonify, render_template, request

from models.supply_chain import (
    ANNUAL_DEMAND,
    HOLDING_COST,
    SETUP_COST,
    calculate_carton_breakdown,
    calculate_courier_shipping_cost,
    calculate_eoq,
    check_stock_reservation,
    orders_per_year,
    total_annual_cost,
)

app = Flask(__name__)


# ===========================================================================
# 1. DATA – this will come from the MySQL database in Milestone 2
# ===========================================================================

# Stock record for the one SKU (the FinMaster board game)
inventory = {"item_code": "FM-2026-CN", "stock_on_hand": 500, "safety_stock": 50}

# Synthetic demo orders. "step" is the order's place in the 7-step Takealot
# sales flow. Shopify and direct-email orders are not in that flow (None).
orders = [
    {"id": 1, "order_ref": "DEMO-ORD-001", "channel": "Takealot",     "quantity": 1,   "step": 1},
    {"id": 2, "order_ref": "DEMO-ORD-002", "channel": "Takealot",     "quantity": 8,   "step": 3},
    {"id": 3, "order_ref": "DEMO-ORD-003", "channel": "Shopify",      "quantity": 2,   "step": None},
    {"id": 4, "order_ref": "DEMO-ORD-004", "channel": "Takealot",     "quantity": 4,   "step": 5},
    {"id": 5, "order_ref": "DEMO-ORD-005", "channel": "Direct email", "quantity": 10,  "step": None},
    {"id": 6, "order_ref": "DEMO-ORD-006", "channel": "Takealot",     "quantity": 6,   "step": 2},
    {"id": 7, "order_ref": "DEMO-ORD-007", "channel": "Takealot",     "quantity": 12,  "step": 7},
    {"id": 8, "order_ref": "DEMO-ORD-008", "channel": "Direct email", "quantity": 460, "step": None},
]

# The 7 steps of the Takealot sales flow (Sales Flow.png).
# "system" picks the colour on the board, "label" is that system's name on
# screen, and "next" is the job that moves an order on to the following step.
SALES_FLOW_STEPS = [
    {"name": "Takealot PO Created",           "system": "websupplier", "label": "Websupplier", "next": "Confirm PO on Takealot Websupplier"},
    {"name": "Fintr Confirms on Websupplier", "system": "websupplier", "label": "Websupplier", "next": "Create Sales Order on ERPNext"},
    {"name": "Sales Order on ERPNext",        "system": "erp",         "label": "ERPNext",     "next": "Create Delivery Note on ERPNext"},
    {"name": "Delivery Note on ERPNext",      "system": "erp",         "label": "ERPNext",     "next": "Create Shipment on Websupplier"},
    {"name": "Shipment on Websupplier",       "system": "websupplier", "label": "Websupplier", "next": "Book Shipment on Courier Guy"},
    {"name": "Shipment on Courier Guy",       "system": "courier",     "label": "Courier Guy", "next": "Hand cartons to the courier"},
    {"name": "Dispatched",                    "system": "done",        "label": "Done",        "next": "None – order complete"},
]
LAST_STEP = len(SALES_FLOW_STEPS)  # 7
PACKING_STEP = 6  # "Shipment on Courier Guy": the cartons are packed and waybills made


# ===========================================================================
# 2. HELPERS – combine the data with the supply chain model
# ===========================================================================

def get_order(order_id):
    """Return the order with this id, or stop with a 404 Not Found error."""
    for order in orders:
        if order["id"] == order_id:
            return order
    abort(404)


def takealot_orders():
    """The orders that are in the 7-step Takealot sales flow."""
    return [order for order in orders if order["step"] is not None]


def stock_figures():
    """Calculation 1: EOQ, reorder point and stock status."""
    eoq_result = calculate_eoq()  # D = 6000, S = R350, H = R45 -> EOQ 306, ROP 170
    eoq = eoq_result["EOQ"]
    reorder_point = eoq_result["Reorder Point"]
    stock = inventory["stock_on_hand"]
    buffer = inventory["safety_stock"]

    if stock < buffer:
        status = "Below Safety Stock"
    elif stock <= reorder_point:
        status = "Reorder Now"
    else:
        status = "Healthy"

    return {
        "eoq": eoq,
        "reorder_point": reorder_point,
        "stock_on_hand": stock,
        "safety_stock": buffer,
        "available": stock - buffer,
        "orders_per_year": orders_per_year(ANNUAL_DEMAND, eoq),
        "yearly_cost": total_annual_cost(ANNUAL_DEMAND, eoq, SETUP_COST, HOLDING_COST),
        "stock_status": status,
    }


def order_with_shipping(order):
    """Calculations 2 and 3 for one order: cartons, courier cost and stock check."""
    quantity = order["quantity"]
    shipping = calculate_courier_shipping_cost(quantity)
    approved, message = check_stock_reservation(
        quantity, inventory["stock_on_hand"], inventory["safety_stock"]
    )

    if not approved:
        status = "Rejected"
    elif order["step"] == LAST_STEP:
        status = "Dispatched"
    else:
        status = "Pending"

    # A copy of the order with the model's results added to it
    return {
        **order,
        "cartons": len(calculate_carton_breakdown(quantity)),
        "billable_kg": shipping["total_billable_weight_kg"],
        "shipping_cost": shipping["total_shipping_cost"],
        "approved": approved,
        "stock_message": message,
        "status": status,
    }


def order_with_stage(order):
    """Add the name and next action of the order's sales flow step."""
    step = SALES_FLOW_STEPS[order["step"] - 1]
    return {
        **order,
        "step_name": step["name"],
        "next_action": step["next"],
        "is_dispatched": order["step"] == LAST_STEP,
    }


def make_waybills(order):
    """Internal Courier Guy simulation: one waybill per carton, in the group
    plan's format TCG-ZA-{order id}-{carton}-{timestamp hash}{random digit}."""
    timestamp_hash = format(int(time.time()) % 4096, "03X")  # 3 hex characters from the clock
    return [
        f"TCG-ZA-{order['id']:04d}-{carton['carton_number']}-{timestamp_hash}{random.randint(0, 9)}"
        for carton in calculate_carton_breakdown(order["quantity"])
    ]


def pack_order(order):
    """Calculation 3, then pack: check the stock above the safety buffer, take
    the games off the shelf and make the waybills. Returns (packed, message)."""
    approved, message = check_stock_reservation(
        order["quantity"], inventory["stock_on_hand"], inventory["safety_stock"]
    )
    if not approved:
        return False, message
    inventory["stock_on_hand"] -= order["quantity"]
    order["waybills"] = make_waybills(order)
    return True, "Order packed"


# ===========================================================================
# 3. JINJA FILTER – money in the South African format
# ===========================================================================

@app.template_filter("rand")
def format_rand(amount):
    """{{ 8857.3|rand }} shows R 8 857.30. chr(160) is a non-breaking space,
    so an amount never splits across two lines."""
    return "R" + chr(160) + f"{amount:,.2f}".replace(",", chr(160))


# ===========================================================================
# 4. PAGES – render_template fills the HTML with the data
# ===========================================================================

@app.route("/")
def home():
    in_progress = [order for order in takealot_orders() if order["step"] < LAST_STEP]
    return render_template(
        "index.html",
        figures=stock_figures(),
        orders_in_progress=len(in_progress),
    )


@app.route("/dashboard")
def dashboard():
    return render_template(
        "dashboard.html",
        figures=stock_figures(),
        orders=[order_with_shipping(order) for order in orders],
    )


@app.route("/sales-flow")
def sales_flow():
    flow_orders = [order_with_stage(order) for order in takealot_orders()]
    # How many orders sit on each of the 7 steps (shown on the board)
    counts = [
        len([order for order in flow_orders if order["step"] == number])
        for number in range(1, LAST_STEP + 1)
    ]
    return render_template(
        "sales_flow.html",
        steps=SALES_FLOW_STEPS,
        orders=flow_orders,
        counts=counts,
    )


# ===========================================================================
# 5. JSON API – the endpoints in the group plan (section 4.2)
# ===========================================================================

@app.route("/api/inventory")
def api_inventory():
    figures = stock_figures()
    return jsonify({
        "stock_on_hand": figures["stock_on_hand"],
        "safety_stock": figures["safety_stock"],
        "available": figures["available"],
        "eoq_recommended": figures["eoq"],
        "reorder_point": figures["reorder_point"],
    })


@app.route("/api/orders")
def api_orders():
    result = [order_with_shipping(order) for order in orders]
    status = request.args.get("status")  # e.g. /api/orders?status=Pending
    if status:
        result = [order for order in result if order["status"] == status]
    return jsonify({"status": "success", "count": len(result), "orders": result})


@app.route("/api/calculate-shipping", methods=["POST"])
def api_calculate_shipping():
    data = request.get_json(silent=True) or {}
    quantity = data.get("quantity")
    cartons = calculate_carton_breakdown(quantity)  # bad quantity -> ValueError -> 400
    shipping = calculate_courier_shipping_cost(quantity)
    return jsonify({
        "cartons_count": len(cartons),
        "total_billable_weight": shipping["total_billable_weight_kg"],
        "shipping_cost_zar": shipping["total_shipping_cost"],
        "breakdown": cartons,
    })


@app.route("/api/orders/<int:order_id>/pack", methods=["POST"])
def api_pack_order(order_id):
    order = get_order(order_id)
    if order.get("waybills"):
        return jsonify({"status": "error", "message": f"{order['order_ref']} is already packed"}), 409

    packed, message = pack_order(order)
    if not packed:
        return jsonify({"status": "error", "message": message}), 409
    return jsonify({"status": "success", "message": message, "waybills": order["waybills"]})


@app.route("/api/sales-flow")
def api_sales_flow():
    result = []
    for order in takealot_orders():
        staged = order_with_stage(order)
        result.append({
            "id": staged["id"],
            "order_ref": staged["order_ref"],
            "current_step": staged["step"],
            "step_name": staged["step_name"],
        })
    return jsonify({"status": "success", "orders": result})


@app.route("/api/sales-flow/<int:order_id>/advance", methods=["POST"])
def api_advance_order(order_id):
    order = get_order(order_id)
    if order["step"] is None:
        return jsonify({"status": "error", "message": f"{order['order_ref']} is not in the Takealot sales flow"}), 400
    if order["step"] == LAST_STEP:
        return jsonify({"status": "error", "message": f"{order['order_ref']} is already dispatched"}), 409

    new_step = order["step"] + 1
    waybills = []
    if new_step == PACKING_STEP:
        # Booking the courier means packing: stock check, stock out, waybills
        packed, message = pack_order(order)
        if not packed:
            return jsonify({"status": "error", "message": message}), 409
        waybills = order["waybills"]

    order["step"] = new_step
    step = SALES_FLOW_STEPS[new_step - 1]
    return jsonify({
        "status": "success",
        "order_id": order["id"],
        "new_step": new_step,
        "step_name": step["name"],
        "next_action": step["next"],
        "is_dispatched": new_step == LAST_STEP,
        "waybills": waybills,
    })


# ===========================================================================
# 6. ERROR HANDLING – one place for every route
# ===========================================================================

@app.errorhandler(ValueError)
def handle_bad_input(error):
    """The supply chain model raises ValueError for bad input, such as 0 units."""
    return jsonify({"status": "error", "message": str(error)}), 400


@app.errorhandler(404)
def handle_not_found(error):
    """API calls get a JSON answer; pages keep Flask's normal 404 page."""
    if request.path.startswith("/api/"):
        return jsonify({"status": "error", "message": "Not found"}), 404
    return error


if __name__ == "__main__":
    app.run(debug=True)

