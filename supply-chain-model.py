# ---------------------------------------------------------------------------------------------
# Importing required libraries and packages
# ---------------------------------------------------------------------------------------------

from statistics import NormalDist

import numpy as np
import math 

# ---------------------------------------------------------------------------------------------
# Function inputs
# ---------------------------------------------------------------------------------------------



# ---------------------------------------------------------------------------------------------
# list of public functions to be called and accessed from this file
# ---------------------------------------------------------------------------------------------

__all__ = [
    # Variables
    "eoq",
    "orders_per_year",
    "annual_ordering_cost",
    "annual_holding_cost",
    "total_annual_cost",
    "daily_demand",
    "reorder_point",
    "safety_stock",

    "z_score",
    "demand_std_dev",
    "lead_time_demand_std_dev",
    "calculate_safety_stock",
    "reorder_point",

    # Calculations
    "calculate_eoq",
    "calculate_carton_breakdown",
    "calculate_courier_shipping_cost",
    "check_stock_reservation",

    # Inventory tracking (uses Calculations 1 and 3 together)
    "inventory_level",
]

# ===========================================================================
# MODEL PARAMETERS/ASSUMPTIONS
SKU = "FM-2026-CN"
ANNUAL_DEMAND = 6000
SETUP_COST = 350.00
HOLDING_COST = 45.00
WORKING_DAYS_PER_YEAR = 250
LEAD_TIME_DAYS = 5
SAFETY_STOCK = 50
# ===========================================================================

# ===========================================================================
# PACKAGING/CARTON and SAFETY STOCK PARAMETERS
# Size of one boxed FinMaster game/unit in cm (length, width, height).
# Only used to document the carton-fit check; billing uses carton size.
UNIT_DIMENSIONS_CM = (38, 28, 6)
 
# Mass of one boxed game in kg. 
UNIT_WEIGHT_KG = 1.2
 
# Size of the master shipping carton in cm (length, width, height).
CARTON_DIMENSIONS_CM = (40, 30, 26)
 
# Tare weight: the mass of the empty carton and packing material in kg.
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

# - SAFETY STOCK PARAMETERS
DEMAND_STD_DEV_PER_DAY = 10
LEAD_TIME_DAYS = 5
SERVICE_LEVEL = 0.95

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

def annual_holding_cost(order_quantity: float, holding_cost: float) -> float:
    """
    Annual holding cost.

    Parameters:
        order_quantity (float): The order quantity (EOQ).
        holding_cost (float): The holding cost per unit per year.

    Returns:
        float: The annual holding cost.
    """
    return (order_quantity / 2) * holding_cost

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
    return NormalDist().inv_cdf(SERVICE_LEVEL)

def calculate_safety_stock(
    demand_std_dev_per_day: float = DEMAND_STD_DEV_PER_DAY,
    lead_time_days: float = LEAD_TIME_DAYS,
    service_level: float = SERVICE_LEVEL,
    *,
    demand_per_day: float | None = None,
    lead_time_std_dev_days: float = LEAD_TIME_STD_DEV_DAYS,
) -> int:
    """Calculate safety stock based on demand and lead time variability.

    Parameters:
        demand_std_dev_per_day (float): Standard deviation of daily demand.
        lead_time_days (float): Lead time in days.
        service_level (float): Desired service level (between 0 and 1).
        demand_per_day (float | None): Optional average daily demand.
        lead_time_std_dev_days (float): Standard deviation of lead time in days.

    Returns:
        int: Calculated safety stock.
    """
    z = z_score(service_level)
    safety_stock = z * math.sqrt(
        (demand_std_dev_per_day ** 2 * lead_time_days) +
        (demand_per_day ** 2 * lead_time_std_dev_days ** 2)
    )
    return int(round(safety_stock))

# ===========================================================================

