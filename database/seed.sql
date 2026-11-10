-- ============================================================================
-- BFB 321: Supply Chain Digital Technologies — Group 28
-- Project: FinFlow — Packing & Order Fulfilment Solution for Fintr
-- Sample Seed Data (seed.sql)
-- Aligns with Class Requirements and Frontend Views
-- ============================================================================

-- 1. Initial Inventory Record for FinMaster board game SKU
INSERT INTO inventory (item_code, item_name, stock_on_hand, safety_stock, reorder_point)
VALUES ('FM-2026-CN', 'FinMaster Financial Education Board Game', 500, 50, 170)
ON DUPLICATE KEY UPDATE 
    stock_on_hand = VALUES(stock_on_hand),
    safety_stock = VALUES(safety_stock),
    reorder_point = VALUES(reorder_point);

-- 2. Initial Outbound Orders Queue (Realistic synthetic demo records)
-- Takealot orders have step 1..7; Shopify & Direct email orders have step NULL.
INSERT INTO orders (id, order_ref, channel, item_code, quantity, step, status) VALUES
(1, 'DEMO-ORD-001', 'Takealot',     'FM-2026-CN', 1,   1,    'Pending'),
(2, 'DEMO-ORD-002', 'Takealot',     'FM-2026-CN', 8,   3,    'Pending'),
(3, 'DEMO-ORD-003', 'Shopify',      'FM-2026-CN', 2,   NULL, 'Pending'),
(4, 'DEMO-ORD-004', 'Takealot',     'FM-2026-CN', 4,   5,    'Pending'),
(5, 'DEMO-ORD-005', 'Direct email', 'FM-2026-CN', 10,  NULL, 'Pending'),
(6, 'DEMO-ORD-006', 'Takealot',     'FM-2026-CN', 6,   2,    'Pending'),
(7, 'DEMO-ORD-007', 'Takealot',     'FM-2026-CN', 12,  7,    'Dispatched'),
(8, 'DEMO-ORD-008', 'Direct email', 'FM-2026-CN', 460, NULL, 'Rejected')
ON DUPLICATE KEY UPDATE 
    status = VALUES(status),
    step = VALUES(step);

-- 3. Initial Packed Cartons for Order 7 (Dispatched order: 12 units = 3 master cartons of 4 units)
INSERT INTO cartons (order_id, carton_number, units_packed, actual_weight_kg, volumetric_weight_kg, billable_weight_kg, waybill_number) VALUES
(7, 1, 4, 5.20, 7.80, 7.80, 'TCG-ZA-0007-1-4829'),
(7, 2, 4, 5.20, 7.80, 7.80, 'TCG-ZA-0007-2-7291'),
(7, 3, 4, 5.20, 7.80, 7.80, 'TCG-ZA-0007-3-3158')
ON DUPLICATE KEY UPDATE 
    waybill_number = VALUES(waybill_number);
