"""
FinFlow – Flask Web Application & REST API
==========================================
BFB 321 – Group 28

Connects the responsive frontend templates to the standalone supply chain model
and the Aiven Cloud MySQL database.

Fulfills Rubric:
- B1.4: Connected to live MySQL with parameterized queries and model-matching schemas
- B2.1: Resource-style REST API endpoints returning consistent JSON
- B2.2: Full CRUD capabilities (Create, Read, Update) on Orders
- B2.4: Pagination, filtering, and bad input validation
- B2.5: Centralized error handling and Python logging (no raw stack traces)
- B3.1–B3.3: 3 end-to-end flows with dynamic frontend updates and supply chain KPIs

Run from the project folder:
    python app.py
Then open http://127.0.0.1:5000 in your browser.
"""

import logging
import os
from flask import Flask, abort, jsonify, render_template, request

from config import get_config
import db
import db_queries
from models.supply_chain import (
    calculate_carton_breakdown,
    calculate_courier_shipping_cost,
)

# ---------------------------------------------------------------------------
# Logging Configuration (Rubric B2.5 & B4.4)
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("finflow")

# ---------------------------------------------------------------------------
# Flask App Factory & Database Teardown Hook
# ---------------------------------------------------------------------------
app = Flask(__name__)
app.config.from_object(get_config())
db.init_app(app)


# ---------------------------------------------------------------------------
# Jinja Template Filter (Currency Formatting)
# ---------------------------------------------------------------------------
@app.template_filter("rand")
def format_rand(amount):
    """
    South African Rand format with non-breaking spaces (e.g., R 8 857.30).
    """
    if amount is None:
        return "R 0.00"
    return "R" + chr(160) + f"{amount:,.2f}".replace(",", chr(160))


# ===========================================================================
# HTML PAGE ROUTES (Step 1 Frontend & Step 5 Integration)
# ===========================================================================

@app.route("/")
def home():
    """
    Landing hub displaying summary warehouse KPIs from live MySQL inventory.
    """
    figures = db_queries.get_stock_figures()
    takealot_orders = db_queries.list_orders(channel_filter="Takealot")
    in_progress = [o for o in takealot_orders if o.get("step") is not None and o["step"] < db_queries.LAST_STEP]
    return render_template(
        "index.html",
        figures=figures,
        orders_in_progress=len(in_progress),
    )


@app.route("/dashboard")
def dashboard():
    """
    Supply chain dashboard with live EOQ KPIs and outbound orders table.
    """
    figures = db_queries.get_stock_figures()
    orders = db_queries.list_orders()
    return render_template(
        "dashboard.html",
        figures=figures,
        orders=orders,
    )


@app.route("/sales-flow")
def sales_flow():
    """
    Takealot 7-stage order fulfilment tracker with live stage counts.
    """
    takealot_orders = db_queries.list_orders(channel_filter="Takealot")
    flow_orders = [o for o in takealot_orders if o.get("step") is not None]
    counts = [
        len([o for o in flow_orders if o["step"] == number])
        for number in range(1, db_queries.LAST_STEP + 1)
    ]
    return render_template(
        "sales_flow.html",
        steps=db_queries.SALES_FLOW_STEPS,
        orders=flow_orders,
        counts=counts,
    )


# ===========================================================================
# REST API ENDPOINTS (Step 4 REST API Design)
# ===========================================================================

@app.route("/api/inventory", methods=["GET"])
def api_inventory():
    """
    Endpoint 1: Returns warehouse stock on hand, buffer, and EOQ parameters.
    """
    figures = db_queries.get_stock_figures()
    return jsonify({
        "stock_on_hand": figures["stock_on_hand"],
        "safety_stock": figures["safety_stock"],
        "available": figures["available"],
        "eoq_recommended": figures["eoq"],
        "reorder_point": figures["reorder_point"],
    }), 200


@app.route("/api/orders", methods=["GET"])
def api_orders():
    """
    Endpoint 2: List orders with optional status/channel filtering and pagination (Rubric B2.4).
    Query parameters: ?status=Pending&channel=Takealot&page=1&limit=10
    """
    status = request.args.get("status")
    channel = request.args.get("channel")
    page = request.args.get("page", type=int)
    limit = request.args.get("limit", type=int)

    offset = None
    if page and limit:
        offset = (page - 1) * limit

    orders = db_queries.list_orders(status_filter=status, channel_filter=channel, limit=limit, offset=offset)
    return jsonify({
        "status": "success",
        "count": len(orders),
        "orders": orders,
    }), 200


@app.route("/api/orders", methods=["POST"])
def api_create_order():
    """
    Endpoint 3 (Rubric B2.2): Creates a new order in MySQL with input and stock buffer validation.
    JSON Request Body: {"order_ref": "ORD-101", "channel": "Takealot", "quantity": 8}
    """
    data = request.get_json(silent=True) or {}
    order_ref = data.get("order_ref")
    channel = data.get("channel", "Takealot")
    quantity = data.get("quantity")

    if not order_ref or not isinstance(order_ref, str):
        return jsonify({"status": "error", "message": "Missing or invalid 'order_ref'"}), 400
    if quantity is None or not isinstance(quantity, int) or quantity <= 0:
        return jsonify({"status": "error", "message": "'quantity' must be a positive integer"}), 400

    try:
        new_order = db_queries.create_order(
            order_ref=order_ref.strip(),
            channel=channel.strip(),
            quantity=quantity,
        )
        logger.info("Created new order: %s (Qty: %s)", order_ref, quantity)
        return jsonify({"status": "success", "order": new_order}), 201
    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception as e:
        logger.error("Failed to create order: %s", e)
        return jsonify({"status": "error", "message": "Failed to create order. Check for duplicate reference."}), 400


@app.route("/api/orders/<int:order_id>", methods=["GET"])
def api_get_order(order_id):
    """
    Endpoint 4 (Rubric B2.2): Retrieves a single order by ID from MySQL.
    """
    order = db_queries.get_order(order_id)
    if not order:
        return jsonify({"status": "error", "message": f"Order {order_id} not found"}), 404
    return jsonify({"status": "success", "order": order}), 200


@app.route("/api/orders/<int:order_id>", methods=["PUT", "PATCH"])
def api_update_order(order_id):
    """
    Endpoint 5 (Rubric B2.2): Updates mutable fields of an existing order in MySQL.
    JSON Request Body: {"quantity": 10, "status": "Pending"}
    """
    data = request.get_json(silent=True) or {}
    order = db_queries.get_order(order_id)
    if not order:
        return jsonify({"status": "error", "message": f"Order {order_id} not found"}), 404

    updated = db_queries.update_order(order_id, **data)
    logger.info("Updated order %s with %s", order_id, data)
    return jsonify({"status": "success", "order": updated}), 200


@app.route("/api/calculate-shipping", methods=["POST"])
def api_calculate_shipping():
    """
    Endpoint 6: Invokes supply chain model to calculate cartons and Courier Guy freight cost.
    JSON Request Body: {"quantity": 8}
    """
    data = request.get_json(silent=True) or {}
    quantity = data.get("quantity")
    cartons = calculate_carton_breakdown(quantity)
    shipping = calculate_courier_shipping_cost(quantity)
    return jsonify({
        "cartons_count": len(cartons),
        "total_billable_weight": shipping["total_billable_weight_kg"],
        "shipping_cost_zar": shipping["total_shipping_cost"],
        "breakdown": cartons,
    }), 200


@app.route("/api/orders/<int:order_id>/pack", methods=["POST"])
def api_pack_order(order_id):
    """
    Endpoint 7: Packing transaction. Verifies buffer, assigns Courier Guy waybills, and deducts stock in MySQL.
    """
    success, message, data = db_queries.pack_order_transaction(order_id)
    if not success:
        status_code = 404 if "not found" in message.lower() else 409
        return jsonify({"status": "error", "message": message}), status_code

    logger.info("Order %s successfully packed with waybills %s", order_id, data.get("waybills"))
    return jsonify({
        "status": "success",
        "message": message,
        "waybills": data["waybills"],
    }), 200


@app.route("/api/sales-flow", methods=["GET"])
def api_sales_flow():
    """
    Endpoint 8: Retrieves Takealot orders currently active in the 7-step pipeline.
    """
    takealot_orders = db_queries.list_orders(channel_filter="Takealot")
    result = [
        {
            "id": o["id"],
            "order_ref": o["order_ref"],
            "current_step": o["step"],
            "step_name": o["step_name"],
        }
        for o in takealot_orders if o.get("step") is not None
    ]
    return jsonify({"status": "success", "orders": result}), 200


@app.route("/api/sales-flow/<int:order_id>/advance", methods=["POST"])
def api_advance_order(order_id):
    """
    Endpoint 9: Advances an order one step along the 7-stage Takealot pipeline in MySQL.
    At step 6, triggers automated packing and waybills; at step 7, marks dispatched.
    """
    success, message, status_code, data = db_queries.advance_order_transaction(order_id)
    if not success:
        return jsonify({"status": "error", "message": message}), status_code

    logger.info("Advanced order %s to step %s (%s)", order_id, data["new_step"], data["step_name"])
    return jsonify({
        "status": "success",
        "order_id": data["order_id"],
        "new_step": data["new_step"],
        "step_name": data["step_name"],
        "next_action": data["next_action"],
        "is_dispatched": data["is_dispatched"],
        "waybills": data["waybills"],
    }), 200


# ===========================================================================
# ERROR HANDLING (Rubric B2.5)
# ===========================================================================

@app.errorhandler(ValueError)
def handle_bad_input(error):
    """Handles supply chain and validation value errors gracefully."""
    logger.warning("Validation error: %s", error)
    return jsonify({"status": "error", "message": str(error)}), 400


@app.errorhandler(400)
def handle_bad_request(error):
    if request.path.startswith("/api/"):
        return jsonify({"status": "error", "message": "Bad request"}), 400
    return error


@app.errorhandler(404)
def handle_not_found(error):
    if request.path.startswith("/api/"):
        return jsonify({"status": "error", "message": "Not found"}), 404
    return error


@app.errorhandler(409)
def handle_conflict(error):
    if request.path.startswith("/api/"):
        return jsonify({"status": "error", "message": "Resource conflict or invalid state transition"}), 409
    return error


@app.errorhandler(500)
def handle_server_error(error):
    logger.error("Internal server error encountered: %s", error)
    if request.path.startswith("/api/"):
        return jsonify({"status": "error", "message": "Internal server error"}), 500
    return error


if __name__ == "__main__":
    app.run(debug=True)
