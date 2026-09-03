-- =============================================================================
-- Mockup 履约中心 · 分仓补录单
-- 表前缀 mock_ 与 YL 业务表区分；可与 YL 同库（Neon）存放
-- =============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS mock_branch_replenishment_order (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    transfer_order_no VARCHAR(64) NOT NULL UNIQUE,
    product_code VARCHAR(32) NOT NULL,
    sku_code VARCHAR(32),
    product_name VARCHAR(255) NOT NULL,
    unit VARCHAR(8) NOT NULL DEFAULT 'EA',
    business_unit VARCHAR(64) NOT NULL,
    ecommerce_barcode VARCHAR(32),
    merchant_order_no VARCHAR(64),
    source_order_no VARCHAR(64),
    status VARCHAR(16) NOT NULL DEFAULT '草稿',
    transfer_gen_status VARCHAR(16) NOT NULL DEFAULT '未生成',
    transfer_qty NUMERIC(15, 3) NOT NULL,
    gross_weight_per_ton NUMERIC(15, 6),
    total_gross_weight_ton NUMERIC(15, 3),
    net_weight_per_ton NUMERIC(15, 6),
    total_net_weight_ton NUMERIC(15, 3),
    volume_m3 NUMERIC(15, 6),
    total_volume_m3 NUMERIC(15, 3),
    temp_zone VARCHAR(16) DEFAULT '常温',
    initial_ship_warehouse VARCHAR(128),
    outbound_logic_warehouse VARCHAR(128),
    transit_warehouse VARCHAR(128) DEFAULT '-',
    inbound_logic_warehouse VARCHAR(128),
    planned_ship_at TIMESTAMPTZ,
    expected_arrival_at TIMESTAMPTZ,
    shipping_remark TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    upstream_created_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_mock_bro_status ON mock_branch_replenishment_order(status);
CREATE INDEX IF NOT EXISTS idx_mock_bro_transfer_gen ON mock_branch_replenishment_order(transfer_gen_status);
CREATE INDEX IF NOT EXISTS idx_mock_bro_inbound ON mock_branch_replenishment_order(inbound_logic_warehouse);
CREATE INDEX IF NOT EXISTS idx_mock_bro_created ON mock_branch_replenishment_order(created_at);

COMMENT ON TABLE mock_branch_replenishment_order IS 'Mockup履约中心-分仓补录单';

-- 幂等 seed：按 transfer_order_no 删除后插入
DELETE FROM mock_branch_replenishment_order
WHERE transfer_order_no LIKE 'TS29072181234567890123456789012345678901234567890123456789%'
   OR transfer_order_no LIKE 'BR-OIP-%';

INSERT INTO mock_branch_replenishment_order (
    transfer_order_no, product_code, sku_code, product_name, unit, business_unit,
    ecommerce_barcode, merchant_order_no, source_order_no, status, transfer_gen_status,
    transfer_qty, gross_weight_per_ton, total_gross_weight_ton, net_weight_per_ton,
    total_net_weight_ton, volume_m3, total_volume_m3, temp_zone,
    initial_ship_warehouse, outbound_logic_warehouse, transit_warehouse, inbound_logic_warehouse,
    planned_ship_at, expected_arrival_at, shipping_remark, created_at, updated_at
) VALUES
(
    'TS290721812345678901234567890123456789012345678901234567890',
    'MOCK_YLP001', 'MOCK_YLP001', '伊利牛奶片32g原味(袋装)', 'EA', '成人营养品事业部',
    '690000000001', 'MO202607020001', 'SR20260702001', '生效', '未生成',
    1200.000, 0.003200, 3.840, 0.002944, 3.533, 0.012000, 14.400, '常温',
    '天津基地仓一盘货仓', '天津基地仓一盘货仓', '-', '郑州销售仓一盘货仓',
    TIMESTAMPTZ '2026-07-01 08:00:00+08', TIMESTAMPTZ '2026-07-03 18:00:00+08', NULL,
    TIMESTAMPTZ '2026-06-28 10:00:00+08', TIMESTAMPTZ '2026-06-28 10:00:00+08'
),
(
    'TS290721812345678901234567890123456789012345678901234567891',
    'MOCK_YLP001', 'MOCK_YLP001', '伊利牛奶片32g原味(袋装)', 'EA', '成人营养品事业部',
    '690000000001', 'MO202607020002', 'SR20260702002', '生效', '已生成',
    860.000, 0.003200, 2.752, 0.002944, 2.532, 0.012000, 10.320, '常温',
    '武汉基地仓一盘货仓', '武汉基地仓一盘货仓', '郑州中转仓', '济南销售仓一盘货仓',
    TIMESTAMPTZ '2026-07-02 06:00:00+08', TIMESTAMPTZ '2026-07-05 12:00:00+08', '干线+枢纽分拨',
    TIMESTAMPTZ '2026-06-29 14:30:00+08', TIMESTAMPTZ '2026-06-30 09:00:00+08'
),
(
    'TS290721812345678901234567890123456789012345678901234567892',
    'MOCK_YLP004', 'MOCK_YLP004', '伊利牛奶片160g草莓味(盒装)', 'EA', '成人营养品事业部',
    '690000000004', NULL, NULL, '生效', '未生成',
    2400.000, 0.001920, 4.608, 0.001766, 4.238, 0.004000, 9.600, '常温',
    '武汉基地仓一盘货仓', '武汉基地仓一盘货仓', '-', '广州销售仓一盘货仓',
    TIMESTAMPTZ '2026-07-03 08:00:00+08', TIMESTAMPTZ '2026-07-06 18:00:00+08', NULL,
    TIMESTAMPTZ '2026-06-30 11:00:00+08', TIMESTAMPTZ '2026-06-30 11:00:00+08'
),
(
    'TS290721812345678901234567890123456789012345678901234567893',
    'MOCK_YLP002', 'MOCK_YLP002', '伊利牛奶片32g草莓味(袋装)', 'EA', '成人营养品事业部',
    '690000000002', 'MO202607020004', 'SR20260702004', '作废', '未生成',
    500.000, 0.003200, 1.600, 0.002944, 1.472, 0.012000, 6.000, '常温',
    '呼市基地仓一盘货仓', '呼市基地仓一盘货仓', '-', '武汉销售仓一盘货仓',
    TIMESTAMPTZ '2026-07-01 08:00:00+08', TIMESTAMPTZ '2026-07-04 18:00:00+08', NULL,
    TIMESTAMPTZ '2026-06-27 16:00:00+08', TIMESTAMPTZ '2026-06-28 08:00:00+08'
),
(
    'TS290721812345678901234567890123456789012345678901234567894',
    'MOCK_YLP003', 'MOCK_YLP003', '伊利牛奶片160g原味(盒装)', 'EA', '成人营养品事业部',
    '690000000003', 'MO202607020005', 'SR20260702005', '草稿', '未生成',
    680.000, 0.001920, 1.306, 0.001766, 1.201, 0.004000, 2.720, '冷藏',
    '天津基地仓一盘货仓', '天津基地仓一盘货仓', '济南中转仓', '合肥销售仓一盘货仓',
    TIMESTAMPTZ '2026-07-04 06:00:00+08', TIMESTAMPTZ '2026-07-07 12:00:00+08', '礼盒装注意防潮',
    TIMESTAMPTZ '2026-07-02 09:00:00+08', TIMESTAMPTZ '2026-07-02 09:00:00+08'
),
(
    'BR-OIP-20260630-TJ-ZZ-3200',
    'MOCK_YLP001', 'MOCK_YLP001', '伊利牛奶片32g原味(袋装)', 'EA', '成人营养品事业部',
    '690000000001', NULL, 'OIP-S1-郑州正向', '生效', '已生成',
    3200.000, 0.003200, 10.240, 0.002944, 9.421, 0.012000, 38.400, '常温',
    '天津基地仓一盘货仓', '天津基地仓一盘货仓', '-', '郑州销售仓一盘货仓',
    TIMESTAMPTZ '2026-06-30 11:00:00+08', TIMESTAMPTZ '2026-07-01 18:00:00+08', 'OIP Script2 临时方案',
    TIMESTAMPTZ '2026-06-30 10:45:00+08', TIMESTAMPTZ '2026-06-30 10:45:00+08'
);

COMMIT;
