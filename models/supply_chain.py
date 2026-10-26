# ---------------------------------------------------------------------------------------------
# Importing required libraries and packages
# ---------------------------------------------------------------------------------------------

from __future__ import annotations  # lets the "int | None" type hints run on Python 3.7+

from decimal import Decimal, ROUND_HALF_UP
from statistics import NormalDist

import math

# ---------------------------------------------------------------------------------------------
# list of public functions to be called and accessed from this file
# ---------------------------------------------------------------------------------------------

__all__ = [
    # Calculation 1 - EOQ, safety stock and reorder point
    "eoq",
    "orders_per_year",
    "annual_ordering_cost",
    "annual_holding_cost",
    "total_annual_cost",
    "z_score",
    "calculate_safety_stock",
    "reorder_point",
    "calculate_eoq",

    # Calculation 2 - cartons and Courier Guy shipping cost
    "calculate_carton_breakdown",
    "calculate_courier_shipping_cost",

    # Calculation 3 - stock reservation
    "check_stock_reservation",

    # Inventory tracking (uses Calculations 1 and 3 together)
    "track_inventory_level",
]

# ===========================================================================
# MODEL PARAMETERS/ASSUMPTIONS
# 1 carton = 1 box
SKU = "FM-2026-CN"
ANNUAL_DEMAND = 6000 #  units/year
SETUP_COST = 350.00 # run / purchase order
HOLDING_COST = 45.00 # unit/year
DAILY_DEMAND = 24 # units/day
WORKING_DAYS_PER_YEAR = 250 # days/year
LEAD_TIME_DAYS = 5 # days

SERVICE_LEVEL = 0.95 # 95 % service level
SAFETY_STOCK = 50 # units
DEMAND_STD_DEV_PER_DAY = 13.5 # units/day
# ===========================================================================

# ===========================================================================
# PACKAGING/CARTON and SAFETY STOCK PARAMETERS
# Size of one boxed FinMaster game/unit in cm (length, width, height).
# Only used to document the carton-fit check; billing uses carton size.
UNIT_DIMENSIONS_CM = (38, 28, 6)
 
# Assumed mass of one boxed game in kg. 
UNIT_WEIGHT_KG = 1.2
 
# Assumed size of the master shipping carton/box in cm (length, width, height).
CARTON_DIMENSIONS_CM = (40, 30, 26)
 
# Tare weight: the mass of the empty carton/box and packing material in kg.
CARTON_TARE_KG = 0.4
 
# Maximum number of games that fit in one master carton.
UNITS_PER_CARTON = 4
 
# Road-freight volumetric divisor in cm^3 per kg. Couriers bill bulky, light parcels as if they weighed (L x W x H) / 4000 kg.
VOLUMETRIC_DIVISOR = 4000
 
# Flat base charge per consignment (Rand); it covers the first 5.0 kg.
BASE_FREIGHT_CHARGE = 120.00
 
# Billable weight (kg) included in the base charge before excess applies.
BASE_WEIGHT_ALLOWANCE_KG = 5.0
 
# Charge per kg of billable weight above the 5.0 kg allowance (Rand/kg).
EXCESS_RATE_PER_KG = 8.50
 
# 15 % uplift on the freight subtotal. The guide labels this line "Fuel Surcharge / VAT"; South African VAT is 15 %.
VAT_RATE = 0.15

# ===========================================================================

# ===========================================================================
# INPUT CHECKS
# Stop bad inputs early with a clear message, so the Flask API can turn
# them into a 400 error instead of returning a wrong answer.
# ===========================================================================

def _require_int(name: str, value, minimum: int = 0) -> int:
    """Return value if it is a whole number >= minimum, otherwise raise ValueError."""
    # bool counts as an int in Python (True == 1), so rule it out explicitly.
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be a whole number, got {value!r}")
    if value < minimum:
        raise ValueError(f"{name} must be {minimum} or more, got {value}")
    return value


def _require_positive_number(name: str, value) -> float:
    """Return value as a float if it is a number above 0, otherwise raise ValueError."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number, got {value!r}")
    if value <= 0:
        raise ValueError(f"{name} must be more than 0, got {value}")
    return float(value)

# ===========================================================================

# ===========================================================================
# CALCULATION 1 - ECONOMIC ORDER QUANTITY & REORDER POINT
#
# Classic EOQ assumptions applied to this model:
#   * Demand is known and constant through the year (no seasonality).
#   * Ordering cost S is fixed per order, whatever the batch size.
#   * Holding cost H is charged on average inventory, which is Q / 2 because stock falls steadily from Q to 0 between deliveries.
#   * Lead time L is known and constant.
#   * Instananeous replenishment
#   * One item only (FM-2026-CN); no planned stock-outs/backorders

def eoq(
    annual_demand: float,
    setup_cost: float,
    holding_cost: float,
) -> float:
    """
    *float data type is used to represent decimal values*

    Calculate EOQ.

    Parameters:
        annual_demand (float): The annual demand for the SKU.
        setup_cost (float): The fixed cost per order.
        holding_cost (float): The holding cost per unit per year.
    Returns:
        float: The optimal order quantity (EOQ).
    """
    return math.sqrt((2 * annual_demand * setup_cost) / holding_cost)

def orders_per_year(annual_demand: float, order_quantity: float) -> float:
    """
    Calculate the number of orders per year.

    Parameters:
        annual_demand (float): The annual demand for the SKU.
        order_quantity (float): The order quantity (EOQ).

    Returns:
        float: The number of orders per year.
    """
    return annual_demand / order_quantity

def annual_ordering_cost(
    annual_demand: float,
    order_quantity: float,
    setup_cost: float,
) -> float:
    """
    Calculate the annual ordering cost.

    Parameters:
        annual_demand (float): The annual demand for the SKU.
        order_quantity (float): The order quantity (EOQ).
        setup_cost (float): The fixed cost per order.

    Returns:
        float: The annual ordering cost.
    """
    return orders_per_year(annual_demand, order_quantity) * setup_cost

def annual_holding_cost(
    order_quantity: float,
    holding_cost: float,
    safety_stock: int = 0,
) -> float:
    """
    Annual holding cost with optional safety stock.

    Parameters:
        order_quantity (float): The order quantity (EOQ).
        holding_cost (float): The holding cost per unit per year.
        safety_stock (int): The safety stock level.

    Returns:
        float: The annual holding cost.
    """
    return ((order_quantity / 2) + safety_stock) * holding_cost

def total_annual_cost(
    annual_demand: float,
    order_quantity: float,
    setup_cost: float,
    holding_cost: float,
    safety_stock: int = 0,
) -> float:
    """Total annual inventory cost for a chosen order quantity.
 
    Formula:
        TC = (D / Q) * S  +  (Q / 2 + SS) * H
             (ordering)      (holding: cycle + safety stock)
 
    With safety_stock = 0 (the default) this is the guide's formula
    TC = (D/Q) x S + (Q/2) x H. Pass the safety stock (50) to include
    the cost of holding the buffer as well.
 
    The SS x H part is the same for every Q, so it raises the whole cost
    curve without moving its lowest point; the EOQ is unchanged.
 
    The purchase price of the games is left out because it is the same
    whatever batch size is chosen, so it does not affect the best Q.
 
    Inputs:
        annual_demand  : D, units per year (> 0)
        order_quantity : Q, units per order (> 0)
        setup_cost     : S, Rand per order (> 0)
        holding_cost   : H, Rand per unit per year (> 0)
        safety_stock   : SS, units (whole number >= 0, default 0)
 
    Output:
        TC in Rand (unrounded float).
 
    Examples:
        >>> round(total_annual_cost(6000, 306, 350, 45), 2)        # guide TC
        13747.75
        >>> round(total_annual_cost(6000, 306, 350, 45, 50), 2)    # incl. SS
        15997.75
    """
    # Add the two cost components; each helper validates its own inputs.
    return (annual_ordering_cost(annual_demand, order_quantity, setup_cost)
            + annual_holding_cost(order_quantity, holding_cost, safety_stock))

# - safety stock calculation
def z_score(service_level: float = SERVICE_LEVEL) -> float:
    """Safety factor z for a chosen cycle service level.
 
    Formula:
        z = the value on the standard normal curve with
            P(Z <= z) = service level        (read from a z-table)
 
    Common values:
        90 %  -> 1.282      95 % -> 1.645
        97.5 % -> 1.960     99 % -> 2.326
    """
    return NormalDist().inv_cdf(service_level)

def calculate_safety_stock(
    demand_std_dev_per_day: float = DEMAND_STD_DEV_PER_DAY,
    lead_time_days: float = LEAD_TIME_DAYS,
    service_level: float = SERVICE_LEVEL,
) -> int:
    """Calculate safety stock based on demand variability over the lead time.

    Formula:
        SS = z x sigma_d x sqrt(L)

    Parameters:
        demand_std_dev_per_day (float): Standard deviation of daily demand.
        lead_time_days (float): Lead time in days.
        service_level (float): Desired service level (between 0 and 1).

    Returns:
        int: Calculated safety stock (95 %: 1.645 x 13.5 x sqrt(5) = 49.65 -> 50).
    """
    z = z_score(service_level)
    safety_stock = z * demand_std_dev_per_day * math.sqrt(lead_time_days)

    return int(round(safety_stock))

def reorder_point(
    demand_per_day: float,
    lead_time_days: float = LEAD_TIME_DAYS,
    safety_stock: int | None = None,
) -> int:
    """Calculate the reorder point (ROP) for inventory management.

    Parameters:
        demand_per_day (float): Average daily demand.
        lead_time_days (float): Lead time in days.
        safety_stock (int | None): Optional safety stock level.

    Returns:
        int: Calculated reorder point.
    """
    if safety_stock is None:
        safety_stock = SAFETY_STOCK  # Use default if not provided

    rop = (demand_per_day * lead_time_days) + safety_stock
    return int(round(rop))

def calculate_eoq(
    annual_demand: float = ANNUAL_DEMAND,
    setup_cost: float = SETUP_COST,
    holding_cost: float = HOLDING_COST,
    *,
    lead_time_days: float = LEAD_TIME_DAYS,
    service_level: float = SERVICE_LEVEL,
    safety_stock: int | None = None,
    daily_demand: float = DAILY_DEMAND,
    demand_std_dev_per_day: float = DEMAND_STD_DEV_PER_DAY,
) -> dict:
    """Calculate EOQ, safety stock, and reorder point.

    Parameters:
        annual_demand (float): Annual demand for the SKU.
        setup_cost (float): Fixed cost per order.
        holding_cost (float): Holding cost per unit per year.
        lead_time_days (float): Lead time in days.
        service_level (float): Desired service level (between 0 and 1).
        safety_stock (int | None): Safety stock to use. None (default)
            calculates it from the service level (50 units at 95 %).
        daily_demand (float): Average daily demand.
        demand_std_dev_per_day (float): Standard deviation of daily demand.

    Returns:
        dict: EOQ rounded to whole units (305.5 -> 306), safety stock and
        reorder point.
    """
    eoq_value = eoq(annual_demand, setup_cost, holding_cost)

    # Use the safety stock given, or calculate it from the service level,
    # and use that SAME value for the reorder point.
    if safety_stock is None:
        safety_stock = calculate_safety_stock(
            demand_std_dev_per_day,
            lead_time_days,
            service_level
        )
    rop_value = reorder_point(
        daily_demand,
        lead_time_days,
        safety_stock
    )

    return {
        "EOQ": round(eoq_value),  # whole games: 305.5 -> 306
        "Safety Stock": safety_stock,
        "Reorder Point": rop_value
    }

# ===========================================================================
# CALCULATION 2 - CARTON ALLOCATION & COURIER GUY SHIPPING COST
# ===========================================================================
 
def calculate_carton_breakdown(quantity_ordered: int) -> list[dict]:
    """Split an order into master cartons and work out each carton's weights.
 
    Formulas:
        Cartons required      = ceil( quantity / 4 ) to get the number of boxes/cartons needed. If not perfectly divisible by 4, the last carton will contain the remainder.
        Units_i               = min( 4, remaining units ) is the number of units in carton i, which is either 4 or whatever is left. This is related to the line above and is important for the inomplete boxes
        Actual gross weight_i = Units_i * 1.2 kg + 0.4 kg (carton tare weight) is the real mass of the carton, which is always less than the volumetric weight.
        Volumetric weight_i   = (40 * 30 * 26) / 4000 = 7.80  is the fixed volumetric mass of the carton, which is always more than the actual weight.
        Billable weight_i     = max( actual gross weight_i, volumetric weight_i )
 
    Assumptions:
        * Every shipment, even a single game, goes out in the standard 40 x 30 x 26 cm master carton; the model has no smaller box.
        * Carton fill order: full cartons of 4 first, the remainder in the last carton (e.g. 10 units -> 4 + 4 + 2).
        * Fit check: four 38 x 28 x 6 cm games stack to 38 x 28 x 24 cm, which fits inside 40 x 30 x 26 cm with about 1 cm of padding space on each side.
        * Road-freight volumetric divisor = 4000 cm^3/kg, so each carton has a fixed volumetric weight of 7.80 kg.
        * Result: a full carton weighs at most 4 x 1.2 + 0.4 = 5.20 kg, always below 7.80 kg. 
            Billable weight is therefore always the volumetric weight, so shipping cost depends on the number of cartons (volume), not on how heavy the games are.
 
    Input:
        quantity_ordered : number of games in the order (whole number >= 1)
 
    Output (list of dicts, one per carton):
        carton_number, units, dimensions_cm (length/width/height),
        actual_gross_weight_kg, volumetric_weight_kg, billable_weight_kg
 
    Example:
        >>> [c["units"] for c in calculate_carton_breakdown(10)]
        [4, 4, 2]
    """
    # The order quantity must be a whole number of 1 or more.
    quantity_ordered = _require_int("quantity_ordered", quantity_ordered, minimum=1)

    # Unpack the carton size tuple (40, 30, 26) into three named variables.
    length, width, height = CARTON_DIMENSIONS_CM

    # Volumetric weight = carton volume / divisor = 31 200 / 4000 = 7.80 kg.
    # It is the same for every carton, so it is worked out once before the loop.
    volumetric = float(length * width * height) / float(VOLUMETRIC_DIVISOR)
 
    # Number of cartons = quantity / 4, rounded up (5 games still need 2 boxes).
    cartons_required = math.ceil(quantity_ordered / UNITS_PER_CARTON)
 
    # Games still waiting to be packed; this counts down inside the loop.
    remaining = quantity_ordered
 
    # Empty list that will collect one dictionary per carton.
    breakdown = []
 
    # Loop once per carton, numbering them 1, 2, 3, ... (range stops before
    # its end value, hence the + 1).
    for carton_number in range(1, cartons_required + 1):
        # Put up to 4 games in this carton; the last carton takes what is left.
        units = min(UNITS_PER_CARTON, remaining)
 
        # Those games are now packed, so take them off the remaining count.
        remaining -= units
 
        # Actual gross weight = games inside x 1.2 kg + 0.4 kg empty carton.
        actual = units * UNIT_WEIGHT_KG + CARTON_TARE_KG
 
        # The courier bills whichever is larger: real mass or volumetric mass.
        billable = max(actual, volumetric)
 
        # Record this carton's details, rounding weights to 2 decimal places.
        breakdown.append({
            "carton_number": carton_number,
            "units": units,
            "dimensions_cm": {"length": length, "width": width, "height": height},
            "actual_gross_weight_kg":  float (actual),
            "volumetric_weight_kg": float (volumetric),
            "billable_weight_kg": float (billable),
        })
 
    # Return the full list of cartons for this order.
    return breakdown

def calculate_courier_shipping_cost(quantity_ordered: int) -> dict:
    """Calculate the courier shipping cost for a given order quantity.

    Parameters:
        quantity_ordered (int): The number of units in the order.

    Returns:
        dict: A dictionary containing the total billable weight and the total shipping cost.

    Why Decimal:
        Floats can't store most decimals exactly. With floats, 8 units works
        out as R 241.61499999..., which rounds DOWN to R 241.61 instead of
        R 241.62 (about 4 in 10 order sizes came out 1 cent low). Decimal
        keeps the money maths exact, and ROUND_HALF_UP rounds half cents up.
    """
    # Get the carton breakdown for the given quantity
    cartons = calculate_carton_breakdown(quantity_ordered)

    # Calculate total billable weight (rounded to 2 decimals to drop float noise)
    total_billable_weight = round(sum(carton["billable_weight_kg"] for carton in cartons), 2)

    # Do the money maths in Decimal (str() keeps the exact decimal digits)
    weight = Decimal(str(total_billable_weight))
    allowance = Decimal(str(BASE_WEIGHT_ALLOWANCE_KG))
    base_charge = Decimal(str(BASE_FREIGHT_CHARGE))
    excess_rate = Decimal(str(EXCESS_RATE_PER_KG))

    # Calculate shipping cost
    if weight <= allowance:
        shipping_cost = base_charge
    else:
        excess_weight = weight - allowance
        shipping_cost = base_charge + (excess_weight * excess_rate)

    # Apply VAT
    shipping_cost *= (1 + Decimal(str(VAT_RATE)))

    # Round to cents, half cents up, then hand back a normal float for the API
    shipping_cost = shipping_cost.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    return {
        "total_billable_weight_kg": total_billable_weight,
        "total_shipping_cost": float(shipping_cost)
    }

# ===========================================================================
# CALCULATION 3 - STOCK RESERVATION & BUFFER VERIFICATION
# ===========================================================================
 
def check_stock_reservation(
    requested_qty: int,
    stock_on_hand: int,
    safety_buffer: int | None = None,
) -> tuple[bool, str]:
    """Check if the requested quantity can be reserved against the stock on hand.

    Parameters:
        requested_qty (int): The quantity requested for reservation.
        stock_on_hand (int): The current stock available.
        safety_buffer (int | None): Optional safety buffer to maintain.

    Returns:
        tuple: A tuple containing a boolean indicating approval and a message.

    Raises:
        ValueError: if requested_qty is not a whole number of 1 or more, or
        stock_on_hand / safety_buffer is not a whole number of 0 or more.
    """
    if safety_buffer is None:
        safety_buffer = SAFETY_STOCK  # Use default if not provided

    # Check the inputs before using them.
    requested_qty = _require_int("requested_qty", requested_qty, minimum=1)
    stock_on_hand = _require_int("stock_on_hand", stock_on_hand, minimum=0)
    safety_buffer = _require_int("safety_buffer", safety_buffer, minimum=0)

    available_stock = stock_on_hand - safety_buffer

    if requested_qty <= available_stock:
        return True, f"Approved: {requested_qty} units can be reserved."
    else:
        shortage = requested_qty - available_stock
        return False, f"Rejected: Shortage of {shortage} units; only {available_stock} units available after safety stock buffer."

# ===========================================================================
# INVENTORY TRACKING - CURRENT STOCK LEVEL & ORDERS UNTIL REORDER
# Links Calculation 3 (each order must pass the safety-buffer check) with
# Calculation 1 (safety stock sets the buffer and the reorder point, and
# the EOQ says how much to reorder).
# ===========================================================================

def track_inventory_level(
    starting_stock: int,
    order_quantities: list[int],
    *,
    reorder_level: int | None = None,
    expected_order_size: float | None = None,
    daily_demand: float = DAILY_DEMAND,
    safety_buffer: int | None = None,
) -> dict:
    """Track the stock level through a run of orders and count orders until reorder.
 
    What it does, step by step:
        1. Work out the safety buffer (the calculated safety stock unless
           one is given) and the reorder point that goes with it
           (ROP = d x L + buffer).
        2. Start from ``starting_stock`` (the physical count of FM-2026-CN).
        3. Take each customer order in sequence. Check it with
           check_stock_reservation(); if approved, subtract it from stock;
           if rejected (it would eat into the safety buffer), log it and
           leave stock unchanged.
        4. Note the first order after which stock fell to or below the
           ROP, i.e. the moment a reorder had to be placed.
        5. From the final stock level, work out how many more orders of a
           typical size can be filled before stock reaches the ROP, and
           give the stock a status for the dashboard.
 
    Formulas:
        Safety buffer        = calculated SS (50 units by default)
        Reorder point        = d x L + Safety buffer = 24 x 5 + 50 = 170
        Stock after order i  = Stock before order i - quantity_i   (if approved)
        Available to sell    = max( 0, Current stock - Safety buffer )
        Units until reorder  = max( 0, Current stock - ROP )
        Typical order size   = expected_order_size, or else the average
                               size of the approved orders in this run
        Orders until reorder = ceil( Units until reorder / Typical order size )
        Reorder triggered    = Current stock <= ROP
        Reorder quantity     = EOQ (306 units) when triggered, otherwise 0
 
    Stock status (for the dashboard's status badge):
        "Healthy"            - stock is above the reorder point
        "Reorder Now"        - stock is at or below the ROP but the safety
                               stock is still intact
        "Below Safety Stock" - stock has fallen under the safety buffer;
                               the next delivery is urgent and every new
                               order will be rejected until it arrives
 
    Meaning of "orders until reorder":
        It is the order number (counting from now) at which stock will first
        fall to or below the ROP, so that order is the one that triggers a
        reorder. Example: 307 units above ROP and orders of 8 units ->
        307 / 8 = 38.4 -> 39. After 38 orders, 173 units remain (still above
        170); the 39th order brings stock to 165 and triggers the reorder.
        A result of 0 means stock is already at or below the ROP: reorder now.
 
    Assumptions:
        * The buffer defaults to calculate_safety_stock() (50 units at 95 %).
          If a different buffer is passed and no reorder_level is given,
          the ROP is recalculated with that buffer so the two always agree.
        * Future orders are assumed to be about the same size as the
          typical order size (steady demand, as in the EOQ model).
        * Orders are filled in the sequence given; each is filled in full
          or rejected in full (no partial shipments).
        * Only outgoing orders are tracked here; replenishment deliveries
          are not added. Once a reorder is placed, the new batch arrives
          after the 5-day lead time and is recorded separately.
        * The function is pure: it does not save anything. In Milestone 2
          the Flask API reads stock_on_hand from the MySQL inventory table,
          passes it in, and writes current_stock back.
 
    Inputs:
        starting_stock      : units on hand before these orders (whole number >= 0)
        order_quantities    : list or tuple of order sizes in sequence
                              (each a whole number >= 1); may be empty
        reorder_level       : keyword-only; ROP in units (whole number >= 0).
                              None (default) = d x L + safety buffer.
        expected_order_size : keyword-only; typical future order size (> 0).
                              None (default) uses the average approved order.
        safety_buffer       : keyword-only; units that must never be sold
                              (whole number >= 0). None (default) = calculated SS.
 
    Output (dict):
        starting_stock             - units at the start
        current_stock              - units left after all approved orders
        safety_stock               - safety buffer used
        available_to_sell          - units above the safety buffer
        reorder_point              - ROP used
        units_until_reorder        - units still above the ROP
        expected_order_size        - order size used for the forecast, 2 dp
        orders_until_reorder       - orders until stock hits the ROP (0 = now)
        reorder_triggered          - True if stock is at or below the ROP
        reorder_triggered_at_order - number of the order that first took
                                     stock to/below ROP; 0 if it was already
                                     there before any orders; None if not yet
        below_safety_stock         - True if stock is under the safety buffer
        stock_status               - "Healthy", "Reorder Now" or
                                     "Below Safety Stock"
        recommended_reorder_qty    - EOQ if a reorder is due, otherwise 0
        orders_processed           - approved orders in this run
        orders_rejected            - orders rejected by the buffer check
        history                    - one dict per order: order_number,
                                     quantity, approved, stock_before,
                                     stock_after, message
 
    Raises:
        ValueError if an input is invalid, or if there are no approved
        orders to average and no expected_order_size was given.
 
    Example:
        >>> r = track_inventory_level(500, [8, 1, 10, 4])
        >>> r["current_stock"], r["safety_stock"], r["orders_until_reorder"]
        (477, 50, 54)
    """
 
    # The starting stock must be a whole number of 0 or more.
    starting_stock = _require_int("starting_stock", starting_stock, minimum=0)

    # The orders must arrive as a list or tuple (an ordered sequence).
    # Each individual quantity is validated later by check_stock_reservation().
    if not isinstance(order_quantities, (list, tuple)):
        raise ValueError(
            f"order_quantities must be a list or tuple, got {order_quantities!r}"
        )
 
    # Work out the safety buffer: the caller's value if given, otherwise
    # the calculated safety stock (50 units with the default inputs).
    if safety_buffer is None:
        buffer = calculate_safety_stock()
    else:
        # A supplied buffer must be a whole number of 0 or more.
        buffer = _require_int("safety_buffer", safety_buffer, minimum=0)
 
    # Work out the reorder point: the caller's value if given, otherwise
    # ROP = d x L + buffer, so the trigger always matches the buffer in use.
    if reorder_level is None:
        rop = reorder_point(
            daily_demand,
            LEAD_TIME_DAYS,
            buffer,
        )
    else:
        # A supplied ROP must be a whole number of 0 or more.
        rop = _require_int("reorder_level", reorder_level, minimum=0)
 
    # If a typical order size was supplied, check that it is a positive number.
    if expected_order_size is not None:
        _require_positive_number("expected_order_size", expected_order_size)
 
    # --- Process the orders one by one -----------------------------------
 
    # The running stock level starts at the starting stock.
    current = starting_stock
 
    # Collect one record per order so the UI can show an audit trail.
    history = []
 
    # Units in all approved orders (used for the average order size).
    approved_units = 0
 
    # Count of approved orders.
    approved_count = 0
 
    # Count of orders rejected by the safety-buffer check.
    rejected_count = 0
 
    # Order number at which stock first fell to/below the ROP.
    # If stock is already at or below the ROP before any order, that
    # happened "at order 0"; otherwise it has not happened yet (None).
    triggered_at = 0 if current <= rop else None
 
    # enumerate(..., start=1) gives each order a number 1, 2, 3, ... along
    # with its quantity.
    for order_number, quantity in enumerate(order_quantities, start=1):
        # Remember the stock level before this order, for the audit trail.
        stock_before = current
 
        # Calculation 3: is there enough stock above the safety buffer?
        # This also validates the quantity (whole number >= 1).
        approved, message = check_stock_reservation(quantity, current, buffer)
 
        # If approved, the order leaves the warehouse.
        if approved:
            # Take the shipped units off the running stock level.
            current -= quantity
            # Add to the totals used for the average order size.
            approved_units += quantity
            approved_count += 1
        else:
            # Rejected: stock stays the same, but count the rejection.
            rejected_count += 1
 
        # If this is the first time stock has fallen to or below the ROP,
        # record which order caused it.
        if triggered_at is None and current <= rop:
            triggered_at = order_number
 
        # Save this order's line in the history.
        history.append({
            "order_number": order_number,
            "quantity": quantity,
            "approved": approved,
            "stock_before": stock_before,
            "stock_after": current,
            "message": message,
        })
 
    # --- Work out how far we are from the reorder point ------------------
 
    # Units that can still be sold without touching the safety buffer.
    available_to_sell = max(0, current - buffer)
 
    # Units still above the ROP; max(0, ...) gives 0 once at or below it.
    units_until_reorder = max(0, current - rop)
 
    # Choose the order size used for the forecast.
    if expected_order_size is not None:
        # The caller told us the typical order size; use it.
        order_size = float(expected_order_size)
    elif approved_count > 0:
        # Otherwise use the average size of the orders approved in this run.
        order_size = approved_units / approved_count
    else:
        # No supplied size and no approved orders: there is nothing to base
        # a forecast on, so stop with a clear message.
        raise ValueError(
            "expected_order_size is required when there are no approved "
            "orders to average"
        )
 
    # Orders until reorder = units above ROP / order size, rounded UP,
    # because the order that crosses the line is the one that triggers it.
    orders_until_reorder = math.ceil(units_until_reorder / order_size)
 
    # A reorder is due once stock is at or below the ROP.
    reorder_triggered = current <= rop
 
    # Stock has fallen into the safety buffer (only possible if it started
    # there, because the reservation check stops orders from causing it).
    below_safety_stock = current < buffer
 
    # Pick the dashboard status: the most serious condition wins.
    if below_safety_stock:
        stock_status = "Below Safety Stock"
    elif reorder_triggered:
        stock_status = "Reorder Now"
    else:
        stock_status = "Healthy"
 
    # If a reorder is due, recommend ordering the EOQ batch; otherwise 0.
    recommended_qty = calculate_eoq()["EOQ"] if reorder_triggered else 0
 
    # --- Package the results ---------------------------------------------
    return {
        "starting_stock": starting_stock,
        "current_stock": current,
        "safety_stock": buffer,
        "available_to_sell": available_to_sell,
        "reorder_point": rop,
        "units_until_reorder": units_until_reorder,
        "expected_order_size": float (order_size),
        "orders_until_reorder": orders_until_reorder,
        "reorder_triggered": reorder_triggered,
        "reorder_triggered_at_order": triggered_at,
        "below_safety_stock": below_safety_stock,
        "stock_status": stock_status,
        "recommended_reorder_qty": recommended_qty,
        "orders_processed": approved_count,
        "orders_rejected": rejected_count,
        "history": history,
    }
 