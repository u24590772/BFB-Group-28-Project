import os
import math
import random
from flask import Flask, render_template, request, jsonify, send_from_directory

# ============================================================================
# MEMBER 1 INTEGRATION CONTRACT (Strict Dependency - No Fallbacks)
# ============================================================================
# This application strictly depends on Member 1's pure Python supply chain logic.
# It will NOT run and will immediately fail if Member 1's module has not been
# implemented and supplied.
try:
    from models.supply_chain import (
        calculate_eoq,
        calculate_courier_shipping_cost,
        check_stock_reservation
    )
except ImportError:
    from sc_logic import (
        calculate_eoq,
        calculate_courier_shipping_cost,
        check_stock_reservation
    )

# ============================================================================
# FLASK APPLICATION SETUP & ASSET PATH RESOLUTION
# ============================================================================
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, 'templates'),
    static_folder=BASE_DIR,
    static_url_path=''
)

# ============================================================================
# DATA STORE (Aligned with Member 3's UI & Slide 19 Pattern)
# ============================================================================
inventory = {
    "item_code": "FM-2026-CN",
    "item_name": "FinMaster Financial Education Board Game",
    "stock_on_hand": 500,
    "safety_stock": 50,
    "available": 450,
    "reorder_point": 170
}
SALES_FLOW_STAGES = {
    1: {
        "name": "Takealot PO Created",
        "next_action": "Confirm PO on Takealot Websupplier",
        "platform": "Websupplier"
    },
    2: {
        "name": "Fintr Confirms on Websupplier",
        "next_action": "Create Sales Order on ERPNext",
        "platform": "Websupplier"
    },
    3: {
        "name": "Sales Order on ERPNext",
        "next_action": "Create Delivery Note on ERPNext",
        "platform": "ERPNext"
    },
    4: {
        "name": "Delivery Note on ERPNext",
        "next_action": "Create Shipment on Websupplier",
        "platform": "ERPNext"
    },
    5: {
        "name": "Shipment on Websupplier",
        "next_action": "Book Shipment on Courier Guy",
        "platform": "Websupplier"
    },
    6: {
        "name": "Shipment on Courier Guy",
        "next_action": "Hand cartons to the courier",
        "platform": "Courier Guy"
    },
    7: {
        "name": "Dispatched",
        "next_action": "None – order complete",
        "platform": "Done"
    }
}

# Synthetic demo orders queue
orders = [
    {
        "id": 1,
        "order_number": "DEMO-ORD-001",
        "channel": "Takealot",
        "quantity": 1,
        "status": "Pending",
        "current_step": 1,
        "step_name": SALES_FLOW_STAGES[1]["name"],
        "next_action": SALES_FLOW_STAGES[1]["next_action"],
        "platform": SALES_FLOW_STAGES[1]["platform"],
        "waybills": []
    },
    {
        "id": 2,
        "order_number": "DEMO-ORD-002",
        "channel": "Takealot",
        "quantity": 8,
        "status": "Pending",
        "current_step": 3,
        "step_name": SALES_FLOW_STAGES[3]["name"],
        "next_action": SALES_FLOW_STAGES[3]["next_action"],
        "platform": SALES_FLOW_STAGES[3]["platform"],
        "waybills": []
    },
    {
        "id": 3,
        "order_number": "DEMO-ORD-003",
        "channel": "Shopify",
        "quantity": 2,
        "status": "Pending",
        "current_step": 1,
        "step_name": SALES_FLOW_STAGES[1]["name"],
        "next_action": SALES_FLOW_STAGES[1]["next_action"],
        "platform": SALES_FLOW_STAGES[1]["platform"],
        "waybills": []
    },
    {
        "id": 4,
        "order_number": "DEMO-ORD-004",
        "channel": "Takealot",
        "quantity": 4,
        "status": "Pending",
        "current_step": 5,
        "step_name": SALES_FLOW_STAGES[5]["name"],
        "next_action": SALES_FLOW_STAGES[5]["next_action"],
        "platform": SALES_FLOW_STAGES[5]["platform"],
        "waybills": []
    },
    {
        "id": 5,
        "order_number": "DEMO-ORD-005",
        "channel": "Direct email",
        "quantity": 10,
        "status": "Pending",
        "current_step": 1,
        "step_name": SALES_FLOW_STAGES[1]["name"],
        "next_action": SALES_FLOW_STAGES[1]["next_action"],
        "platform": SALES_FLOW_STAGES[1]["platform"],
        "waybills": []
    },
    {
        "id": 6,
        "order_number": "DEMO-ORD-006",
        "channel": "Takealot",
        "quantity": 6,
        "status": "Pending",
        "current_step": 2,
        "step_name": SALES_FLOW_STAGES[2]["name"],
        "next_action": SALES_FLOW_STAGES[2]["next_action"],
        "platform": SALES_FLOW_STAGES[2]["platform"],
        "waybills": []
    },
    {
        "id": 7,
        "order_number": "DEMO-ORD-007",
        "channel": "Takealot",
        "quantity": 12,
        "status": "Dispatched",
        "current_step": 7,
        "step_name": SALES_FLOW_STAGES[7]["name"],
        "next_action": SALES_FLOW_STAGES[7]["next_action"],
        "platform": SALES_FLOW_STAGES[7]["platform"],
        "waybills": ["TCG-ZA-0007-1-4829", "TCG-ZA-0007-2-7291", "TCG-ZA-0007-3-3158"]
    },
    {
        "id": 8,
        "order_number": "DEMO-ORD-008",
        "channel": "Direct email",
        "quantity": 460,
        "status": "Buffer Breach",
        "current_step": 1,
        "step_name": SALES_FLOW_STAGES[1]["name"],
        "next_action": "Stock replenishment required (Breaches 50-unit safety buffer)",
        "platform": "Warehouse",
        "waybills": []
    }
]

# Helper to locate an order by numeric ID or order_number string
def _find_order(identifier):
    ident_str = str(identifier).strip().lower()
    for o in orders:
        if str(o["id"]) == ident_str or o["order_number"].lower() == ident_str:
            return o
    return None

# INTERNAL COURIER WAYBILL GENERATOR (Section 4.2 Specification)
def generate_waybill(order_id, carton_num):
    """
    Simulates a standard Courier Guy domestic tracking number locally.
    Format: TCG-ZA-{order_id:04d}-{carton_num}-{rand_seq}
    Example: TCG-ZA-0001-1-4829
    """
    rand_seq = f"{random.randint(1000, 9999)}"
    return f"TCG-ZA-{int(order_id):04d}-{int(carton_num)}-{rand_seq}"

# STATIC ASSETS SERVING (Aligns with Member 3's CSS & JS references)
@app.route('/css/<path:filename>')
def serve_css(filename):
    return send_from_directory(os.path.join(BASE_DIR, 'css'), filename)

@app.route('/js/<path:filename>')
def serve_js(filename):
    return send_from_directory(os.path.join(BASE_DIR, 'js'), filename)

# PAGE VIEW ROUTES
@app.route('/')
@app.route('/index.html')
def home():
    return render_template('index.html', inventory=inventory)

@app.route('/dashboard')
@app.route('/dashboard.html')
def dashboard():
    return render_template('dashboard.html', inventory=inventory, orders=orders)

@app.route('/sales-flow')
@app.route('/sales_flow.html')
def sales_flow():
    return render_template('sales_flow.html', orders=orders, stages=SALES_FLOW_STAGES)

# REST API ENDPOINTS

# Endpoint 1: GET /api/inventory
# Retrieves warehouse stock on hand, safety stock buffer, and EOQ parameters
@app.route('/api/inventory', methods=['GET'])
def get_inventory():
    eoq_calc = calculate_eoq(annual_demand=6000, setup_cost=350.0, holding_cost=45.0)
    return jsonify({
        "status": "success",
        "item_code": inventory["item_code"],
        "item_name": inventory["item_name"],
        "stock_on_hand": inventory["stock_on_hand"],
        "safety_stock": inventory["safety_stock"],
        "available": inventory["stock_on_hand"] - inventory["safety_stock"],
        "reorder_point": eoq_calc.get("reorder_point", 170),
        "eoq_recommended": eoq_calc.get("eoq", 306),
        "orders_per_year": eoq_calc.get("orders_per_year", 19.6),
        "total_annual_cost_zar": eoq_calc.get("total_cost", 13748)
    }), 200

# Endpoint 2: GET /api/orders
# Retrieves fulfillment queue with optional query filtering
@app.route('/api/orders', methods=['GET'])
def get_orders():
    status_filter = request.args.get('status')
    channel_filter = request.args.get('channel')
    
    result = orders
    if status_filter:
        result = [o for o in result if o["status"].lower() == status_filter.lower()]
    if channel_filter:
        result = [o for o in result if o["channel"].lower() == channel_filter.lower()]

    return jsonify({
        "status": "success",
        "count": len(result),
        "orders": result
    }), 200

# Endpoint 3: POST /api/calculate-shipping
# Calls supply chain Member 1's logic to calculate carton split & Courier Guy road freight cost
@app.route('/api/calculate-shipping', methods=['POST'])
def calculate_shipping():
    data = request.get_json(silent=True) or {}
    quantity = data.get("quantity")

    # Input validation (Slide 28)
    if quantity is None or not isinstance(quantity, int) or quantity <= 0:
        return jsonify({
            "status": "error",
            "message": "Invalid quantity. Must be a positive integer."
        }), 400

    cost_data = calculate_courier_shipping_cost(quantity)
    return jsonify({
        "status": "success",
        "data": cost_data
    }), 200

# Endpoint 4: POST /api/orders/<identifier>/pack
# Confirms packing, checks stock buffer via Member 1, generates waybills, marks as 'Packed'
@app.route('/api/orders/<identifier>/pack', methods=['POST'])
def pack_order(identifier):
    order = _find_order(identifier)
    if not order:
        return jsonify({
            "status": "error",
            "message": f"Order '{identifier}' not found."
        }), 404

    # Verify stock reservation using function
    approved, message = check_stock_reservation(
        requested_qty=order["quantity"],
        stock_on_hand=inventory["stock_on_hand"],
        safety_buffer=inventory["safety_stock"]
    )
    if not approved:
        return jsonify({
            "status": "error",
            "message": f"Stock reservation rejected: {message}"
        }), 400

    # Calculate cartons needed (4 units per master carton)
    cartons_count = math.ceil(order["quantity"] / 4)
    waybills = [generate_waybill(order["id"], i + 1) for i in range(cartons_count)]
    order["waybills"] = waybills
    order["status"] = "Packed"
    
    # Advance to step 6 (Shipment on Courier Guy) if currently before it
    if order["current_step"] < 6:
        order["current_step"] = 6
        step_info = SALES_FLOW_STAGES[6]
        order["step_name"] = step_info["name"]
        order["next_action"] = step_info["next_action"]
        order["platform"] = step_info["platform"]

    return jsonify({
        "status": "success",
        "message": f"Order {order['order_number']} packed successfully",
        "order_id": order["id"],
        "order_number": order["order_number"],
        "status": order["status"],
        "cartons_packed": cartons_count,
        "waybills": waybills
    }), 200

# Endpoint 5: GET /api/sales-flow
# Retrieves all Takealot orders currently in the 7-stage fulfillment pipeline
@app.route('/api/sales-flow', methods=['GET'])
def get_sales_flow():
    takealot_orders = [o for o in orders if o["channel"] == "Takealot"]
    pipeline = [
        {
            "id": o["id"],
            "order_number": o["order_number"],
            "channel": o["channel"],
            "quantity": o["quantity"],
            "current_step": o["current_step"],
            "step_name": o["step_name"],
            "next_action": o["next_action"],
            "platform": o["platform"]
        }
        for o in takealot_orders
    ]
    return jsonify({
        "status": "success",
        "total_takealot_orders": len(pipeline),
        "stages": SALES_FLOW_STAGES,
        "orders": pipeline
    }), 200

# Endpoint 6: POST /api/sales-flow/<identifier>/advance
# Advances an order to the next step in the sales flow pipeline
@app.route('/api/sales-flow/<identifier>/advance', methods=['POST'])
def advance_sales_flow(identifier):
    order = _find_order(identifier)
    if not order:
        return jsonify({
            "status": "error",
            "message": f"Order '{identifier}' not found."
        }), 404

    # Check if already completed (Step 7: Dispatched)
    if order["current_step"] >= 7:
        return jsonify({
            "status": "notice",
            "message": f"Order {order['order_number']} has already completed the sales flow (Dispatched).",
            "order_id": order["id"],
            "order_number": order["order_number"],
            "current_step": 7,
            "step_name": SALES_FLOW_STAGES[7]["name"]
        }), 200

    # Advance to next step
    order["current_step"] += 1
    new_step = order["current_step"]
    step_info = SALES_FLOW_STAGES[new_step]
    order["step_name"] = step_info["name"]
    order["next_action"] = step_info["next_action"]
    order["platform"] = step_info["platform"]

    # If reaching final step, mark status as Dispatched
    if new_step == 7:
        order["status"] = "Dispatched"

    return jsonify({
        "status": "success",
        "order_id": order["id"],
        "order_number": order["order_number"],
        "new_step": new_step,
        "step_name": order["step_name"],
        "next_action": order["next_action"],
        "platform": order["platform"],
        "order_status": order["status"]
    }), 200

if __name__ == '__main__':
    app.run(debug=True, port=5000)
