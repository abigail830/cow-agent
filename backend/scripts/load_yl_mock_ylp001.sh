#!/usr/bin/env bash
# Load MOCK_YLP001 mock chain for yl-worker2 integration tests.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SQL_DIR="$ROOT/migrations/sql"
YL_DATABASE_URL="${YL_DATABASE_URL:-$(grep '^YL_DATABASE_URL=' "$ROOT/.env" | cut -d= -f2-)}"
if [[ -z "${YL_DATABASE_URL}" ]]; then
  echo "YL_DATABASE_URL not set" >&2
  exit 1
fi

run_sql() {
  local file="$1"
  echo "==> $file"
  psql "$YL_DATABASE_URL" -v ON_ERROR_STOP=1 -f "$file"
}

run_sql "$SQL_DIR/yl_warehouse_product.sql"
run_sql "$SQL_DIR/yl_zhenhu1_year_batch1_warehouse.sql"
run_sql "$SQL_DIR/yl_zhenhu1_year_batch2_3_4_auxiliary.sql"
run_sql "$SQL_DIR/yl_zhenhu1_year_unship_patch.sql"
run_sql "$SQL_DIR/yl_zhenhu1_year_inventory_dos_patch.sql"
run_sql "$SQL_DIR/yl_product_milk_tablet_replacement.sql"
run_sql "$SQL_DIR/yl_business_unit_adult_nutrition.sql"
run_sql "$SQL_DIR/yl_mock_ylp001_p0_tab1_transit.sql"
run_sql "$SQL_DIR/yl_mock_ylp001_p1_script1_snapshot.sql"
run_sql "$SQL_DIR/yl_mockup_branch_replenishment.sql"
run_sql "$SQL_DIR/yl_worker2_v_sku_site_inventory_cube.sql"
echo "MOCK_YLP001 chain loaded."
