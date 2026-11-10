-- ============================================================================
-- BFB 321: Supply Chain Digital Technologies — Group 28
-- Project: FinFlow — Packing & Order Fulfilment Solution for Fintr
-- Stack: Python Flask + MySQL (Aiven Cloud)
-- Schema DDL: 3NF Normalized Relational Model
-- ============================================================================

-- ----------------------------------------------------------------------------
-- Table 1: inventory
-- Tracks master SKU stock on hand, safety stock buffer, and EOQ parameters
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS inventory (
    item_code VARCHAR(30) PRIMARY KEY,
    item_name VARCHAR(120) NOT NULL,
    stock_on_hand INT NOT NULL DEFAULT 500,
    safety_stock INT NOT NULL DEFAULT 50,
    reorder_point INT NOT NULL DEFAULT 170,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT chk_stock_non_negative CHECK (stock_on_hand >= 0),
    CONSTRAINT chk_safety_stock_non_negative CHECK (safety_stock >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ----------------------------------------------------------------------------
-- Table 2: orders
-- Tracks incoming orders across Takealot, Shopify, and Direct Email channels.
-- 'step' tracks progress across the 7 stages of the Takealot Sales Flow.
-- Non-Takealot orders (e.g. Shopify, Direct email) have step = NULL.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS orders (
    id INT AUTO_INCREMENT PRIMARY KEY,
    order_ref VARCHAR(30) NOT NULL UNIQUE,
    channel VARCHAR(50) NOT NULL,
    item_code VARCHAR(30) NOT NULL,
    quantity INT NOT NULL,
    step INT NULL DEFAULT 1,
    status VARCHAR(30) NOT NULL DEFAULT 'Pending',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_orders_item FOREIGN KEY (item_code) REFERENCES inventory (item_code) ON UPDATE CASCADE,
    CONSTRAINT chk_orders_quantity CHECK (quantity > 0),
    CONSTRAINT chk_orders_step CHECK (step IS NULL OR (step BETWEEN 1 AND 7)),
    INDEX idx_orders_status (status),
    INDEX idx_orders_channel (channel)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ----------------------------------------------------------------------------
-- Table 3: cartons
-- Stores physical master carton packing splits, weights, and Courier Guy waybills
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS cartons (
    id INT AUTO_INCREMENT PRIMARY KEY,
    order_id INT NOT NULL,
    carton_number INT NOT NULL,
    units_packed INT NOT NULL,
    actual_weight_kg DECIMAL(6,2) NOT NULL,
    volumetric_weight_kg DECIMAL(6,2) NOT NULL,
    billable_weight_kg DECIMAL(6,2) NOT NULL,
    waybill_number VARCHAR(50) NOT NULL UNIQUE,
    packed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_cartons_order FOREIGN KEY (order_id) REFERENCES orders (id) ON DELETE CASCADE,
    CONSTRAINT chk_cartons_units CHECK (units_packed > 0 AND units_packed <= 4),
    INDEX idx_cartons_order_id (order_id),
    INDEX idx_cartons_waybill (waybill_number)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
