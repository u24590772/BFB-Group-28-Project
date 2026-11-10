import os
import random
import time
import db
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
# Takealot 7-Stage Sales Flow Configuration
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
PACKING_STEP = 6                   # Booking the courier triggers packing and waybills


def make_waybills(order_id, quantity):
    """
    Generates Courier Guy waybill tracking numbers in the required format:
    TCG-ZA-{order_id:04d}-{carton}-{timestamp hash}{random digit}
    """
    timestamp_hash = format(int(time.time()) % 4096, "03X")
    cartons = calculate_carton_breakdown(quantity)
    return [
        f"TCG-ZA-{int(order_id):04d}-{carton['carton_number']}-{timestamp_hash}{random.randint(0, 9)}"
        for carton in cartons
    ]

# Inventory Queries & KPI Calculations

def get_inventory():
    """
    Fetches the inventory row for FinMaster (FM-2026-CN) from MySQL.
    """
    row = db.query_one("SELECT * FROM inventory WHERE item_code = %s LIMIT 1", ("FM-2026-CN",))
    if not row:
        return {
            "item_code": "FM-2026-CN",
            "item_name": "FinMaster Financial Education Board Game",
            "stock_on_hand": 500,
            "safety_stock": 50,
            "reorder_point": 170,
        }
    return row


def get_stock_figures():
    """
    Calculates supply chain KPIs from live MySQL inventory data:
    EOQ, Reorder Point, available buffer, and annual holding/ordering costs.
    """
    inv = get_inventory()
    eoq_result = calculate_eoq()
    eoq_val = eoq_result["EOQ"]
    rop_val = eoq_result["Reorder Point"]
    stock = inv["stock_on_hand"]
    buffer = inv["safety_stock"]

    if stock < buffer:
        status = "Below Safety Stock"
    elif stock <= rop_val:
        status = "Reorder Now"
    else:
        status = "Healthy"

    return {
        "item_code": inv["item_code"],
        "item_name": inv.get("item_name", "FinMaster Board Game"),
        "eoq": eoq_val,
        "reorder_point": rop_val,
        "stock_on_hand": stock,
        "safety_stock": buffer,
        "available": stock - buffer,
        "orders_per_year": orders_per_year(ANNUAL_DEMAND, eoq_val),
        "yearly_cost": total_annual_cost(ANNUAL_DEMAND, eoq_val, SETUP_COST, HOLDING_COST),
        "stock_status": status,
    }

# Order Retrieval & Enrichment

def enrich_order_with_shipping(order, current_stock=None, current_safety=None):
    """
    Enriches an order dictionary with carton breakdown, Courier Guy freight costs,
    and stock buffer approval status.
    """
    if current_stock is None or current_safety is None:
        inv = get_inventory()
        current_stock = inv["stock_on_hand"]
        current_safety = inv["safety_stock"]

    quantity = order["quantity"]
    cartons = calculate_carton_breakdown(quantity)
    shipping = calculate_courier_shipping_cost(quantity)
    approved, message = check_stock_reservation(quantity, current_stock, current_safety)

    if not approved:
        status = "Rejected"
    elif order.get("step") == LAST_STEP:
        status = "Dispatched"
    else:
        status = order.get("status", "Pending")

    return {
        **order,
        "cartons": len(cartons),
        "billable_kg": shipping["total_billable_weight_kg"],
        "shipping_cost": shipping["total_shipping_cost"],
        "approved": approved,
        "stock_message": message,
        "status": status,
    }


def enrich_order_with_stage(order):
    """
    Enriches an order with Takealot pipeline metadata (step name and next action).
    """
    step = order.get("step")
    if step and 1 <= step <= LAST_STEP:
        stage_info = SALES_FLOW_STEPS[step - 1]
        step_name = stage_info["name"]
        next_action = stage_info["next"]
        system = stage_info["system"]
        label = stage_info["label"]
    else:
        step_name = "Not in flow"
        next_action = "N/A"
        system = "none"
        label = "N/A"

    return {
        **order,
        "step_name": step_name,
        "next_action": next_action,
        "system": system,
        "label": label,
        "is_dispatched": step == LAST_STEP,
    }


def list_orders(status_filter=None, channel_filter=None, limit=None, offset=None):
    """
    Retrieves orders from MySQL with optional filtering and pagination.
    Joins with cartons table to attach generated Courier Guy waybills.
    """
    sql = "SELECT * FROM orders WHERE 1=1"
    params = []

    if channel_filter:
        sql += " AND LOWER(channel) = LOWER(%s)"
        params.append(channel_filter)

    if status_filter and status_filter.lower() not in ["rejected", "buffer breach"]:
        sql += " AND LOWER(status) = LOWER(%s)"
        params.append(status_filter)

    sql += " ORDER BY id ASC"

    if limit is not None:
        sql += " LIMIT %s"
        params.append(int(limit))
        if offset is not None:
            sql += " OFFSET %s"
            params.append(int(offset))

    orders = db.query_all(sql, params)

    # Attach waybills from cartons table
    cartons = db.query_all("SELECT order_id, waybill_number FROM cartons ORDER BY carton_number ASC")
    waybill_map = {}
    for c in cartons:
        waybill_map.setdefault(c["order_id"], []).append(c["waybill_number"])

    inv = get_inventory()
    stock_on_hand = inv["stock_on_hand"]
    safety_stock = inv["safety_stock"]

    result = []
    for o in orders:
        o["waybills"] = waybill_map.get(o["id"], [])
        enriched = enrich_order_with_shipping(o, stock_on_hand, safety_stock)
        staged = enrich_order_with_stage(enriched)
        if status_filter:
            sf = status_filter.lower()
            if staged["status"].lower() == sf or (sf == "rejected" and not staged["approved"]):
                result.append(staged)
        else:
            result.append(staged)

    return result


def get_order(order_identifier):
    """
    Retrieves a single order by integer ID or string order_ref.
    """
    ident_str = str(order_identifier).strip()
    if ident_str.isdigit():
        sql = "SELECT * FROM orders WHERE id = %s OR order_ref = %s LIMIT 1"
        params = (int(ident_str), ident_str)
    else:
        sql = "SELECT * FROM orders WHERE LOWER(order_ref) = LOWER(%s) LIMIT 1"
        params = (ident_str,)

    order = db.query_one(sql, params)
    if not order:
        return None

    cartons = db.query_all(
        "SELECT waybill_number FROM cartons WHERE order_id = %s ORDER BY carton_number ASC",
        (order["id"],),
    )
    order["waybills"] = [c["waybill_number"] for c in cartons]

    inv = get_inventory()
    enriched = enrich_order_with_shipping(order, inv["stock_on_hand"], inv["safety_stock"])
    return enrich_order_with_stage(enriched)


# Order CRUD Operations

def create_order(order_ref, channel, quantity, item_code="FM-2026-CN", step=None):
    inv = get_inventory()
    approved, message = check_stock_reservation(quantity, inv["stock_on_hand"], inv["safety_stock"])
    if not approved:
        raise ValueError(f"Stock reservation rejected: {message}")

    if step is None and channel.lower() == "takealot":
        step = 1

    sql = """
        INSERT INTO orders (order_ref, channel, item_code, quantity, step, status)
        VALUES (%s, %s, %s, %s, %s, %s)
    """
    new_id = db.execute(sql, (order_ref, channel, item_code, quantity, step, "Pending"))
    return get_order(new_id)


def update_order(order_identifier, **fields):
    """
    Updates mutable fields of an order in MySQL.
    Supported fields: quantity, channel, status, step.
    """
    order = get_order(order_identifier)
    if not order:
        return None

    allowed_fields = ["quantity", "channel", "status", "step"]
    updates = []
    params = []

    for k, v in fields.items():
        if k in allowed_fields:
            updates.append(f"{k} = %s")
            params.append(v)

    if not updates:
        return order

    params.append(order["id"])
    sql = f"UPDATE orders SET {', '.join(updates)} WHERE id = %s"
    db.execute(sql, params)
    return get_order(order["id"])


# ---------------------------------------------------------------------------
# Business Transactions: Pack & Advance (Rubric B1.4, B2.5, B3.1)
# ---------------------------------------------------------------------------

def pack_order_transaction(order_identifier):
    """
    Atomic packing transaction:
    1. Lock and read order and inventory rows with FOR UPDATE.
    2. Check stock against safety stock buffer.
    3. Calculate carton breakdown and insert carton rows with Courier Guy waybills.
    4. Deduct packed quantity from inventory stock_on_hand.
    5. Update order status to 'Packed'.
    6. Commit transaction (or rollback on error).
    """
    conn = db.get_db()
    try:
        with conn.cursor() as cur:
            ident_str = str(order_identifier).strip()
            if ident_str.isdigit():
                cur.execute(
                    "SELECT * FROM orders WHERE id = %s OR order_ref = %s FOR UPDATE",
                    (int(ident_str), ident_str),
                )
            else:
                cur.execute(
                    "SELECT * FROM orders WHERE LOWER(order_ref) = LOWER(%s) FOR UPDATE",
                    (ident_str,),
                )
            order = cur.fetchone()
            if not order:
                conn.rollback()
                return False, f"Order '{order_identifier}' not found.", None

            # Check if order already has waybills
            cur.execute("SELECT waybill_number FROM cartons WHERE order_id = %s", (order["id"],))
            existing_waybills = [row["waybill_number"] for row in cur.fetchall()]
            if existing_waybills:
                conn.rollback()
                return False, f"{order['order_ref']} is already packed", None

            # Lock inventory row
            cur.execute("SELECT * FROM inventory WHERE item_code = %s FOR UPDATE", (order["item_code"],))
            inv = cur.fetchone()
            if not inv:
                conn.rollback()
                return False, f"Item {order['item_code']} not found in inventory.", None

            # Stock reservation check
            approved, message = check_stock_reservation(
                order["quantity"], inv["stock_on_hand"], inv["safety_stock"]
            )
            if not approved:
                conn.rollback()
                return False, message, None

            # Generate cartons and waybills
            cartons = calculate_carton_breakdown(order["quantity"])
            waybills = make_waybills(order["id"], order["quantity"])

            for carton, wb in zip(cartons, waybills):
                cur.execute(
                    """
                    INSERT INTO cartons 
                    (order_id, carton_number, units_packed, actual_weight_kg, 
                     volumetric_weight_kg, billable_weight_kg, waybill_number)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        order["id"],
                        carton["carton_number"],
                        carton["units"],
                        carton["actual_gross_weight_kg"],
                        carton["volumetric_weight_kg"],
                        carton["billable_weight_kg"],
                        wb,
                    ),
                )

            # Deduct stock
            cur.execute(
                "UPDATE inventory SET stock_on_hand = stock_on_hand - %s WHERE item_code = %s",
                (order["quantity"], order["item_code"]),
            )

            # Update order status
            cur.execute(
                "UPDATE orders SET status = 'Packed' WHERE id = %s",
                (order["id"],),
            )

        conn.commit()
        return True, "Order packed", {"order_id": order["id"], "waybills": waybills}

    except Exception as e:
        conn.rollback()
        raise e


def advance_order_transaction(order_identifier):
    """
    Advances a Takealot order to the next step in the 7-stage sales flow.
    When reaching PACKING_STEP (Step 6), automatically triggers the packing transaction.
    When reaching LAST_STEP (Step 7), marks order as 'Dispatched'.
    """
    conn = db.get_db()
    try:
        with conn.cursor() as cur:
            ident_str = str(order_identifier).strip()
            if ident_str.isdigit():
                cur.execute(
                    "SELECT * FROM orders WHERE id = %s OR order_ref = %s FOR UPDATE",
                    (int(ident_str), ident_str),
                )
            else:
                cur.execute(
                    "SELECT * FROM orders WHERE LOWER(order_ref) = LOWER(%s) FOR UPDATE",
                    (ident_str,),
                )
            order = cur.fetchone()
            if not order:
                conn.rollback()
                return False, f"Order '{order_identifier}' not found.", 404, None

            if order["step"] is None:
                conn.rollback()
                return False, f"{order['order_ref']} is not in the Takealot sales flow", 400, None

            if order["step"] >= LAST_STEP:
                conn.rollback()
                return False, f"{order['order_ref']} is already dispatched", 409, None

            new_step = order["step"] + 1
            waybills = []

            # Step 6: Booking Courier Guy means packing, stock deduction, and waybill generation
            if new_step == PACKING_STEP:
                # Check if already packed
                cur.execute("SELECT waybill_number FROM cartons WHERE order_id = %s", (order["id"],))
                existing = [r["waybill_number"] for r in cur.fetchall()]
                if existing:
                    waybills = existing
                else:
                    cur.execute("SELECT * FROM inventory WHERE item_code = %s FOR UPDATE", (order["item_code"],))
                    inv = cur.fetchone()
                    approved, message = check_stock_reservation(
                        order["quantity"], inv["stock_on_hand"], inv["safety_stock"]
                    )
                    if not approved:
                        conn.rollback()
                        return False, message, 409, None

                    cartons = calculate_carton_breakdown(order["quantity"])
                    waybills = make_waybills(order["id"], order["quantity"])

                    for carton, wb in zip(cartons, waybills):
                        cur.execute(
                            """
                            INSERT INTO cartons 
                            (order_id, carton_number, units_packed, actual_weight_kg, 
                             volumetric_weight_kg, billable_weight_kg, waybill_number)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                            """,
                            (
                                order["id"],
                                carton["carton_number"],
                                carton["units"],
                                carton["actual_gross_weight_kg"],
                                carton["volumetric_weight_kg"],
                                carton["billable_weight_kg"],
                                wb,
                            ),
                        )

                    cur.execute(
                        "UPDATE inventory SET stock_on_hand = stock_on_hand - %s WHERE item_code = %s",
                        (order["quantity"], order["item_code"]),
                    )

            new_status = "Dispatched" if new_step == LAST_STEP else order["status"]
            cur.execute(
                "UPDATE orders SET step = %s, status = %s WHERE id = %s",
                (new_step, new_status, order["id"]),
            )

        conn.commit()

        step_meta = SALES_FLOW_STEPS[new_step - 1]
        return True, "Order advanced successfully", 200, {
            "order_id": order["id"],
            "new_step": new_step,
            "step_name": step_meta["name"],
            "next_action": step_meta["next"],
            "is_dispatched": new_step == LAST_STEP,
            "waybills": waybills,
        }

    except Exception as e:
        conn.rollback()
        raise e
