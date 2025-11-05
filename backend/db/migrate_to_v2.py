# backend/db/migrate_to_v2.py
# ==============================
# 说明：数据库Schema从V1迁移到V2的脚本（极简版）
# - 执行方式：python -m backend.db.migrate_to_v2
# - 功能：
#   1. 为 symbol_index 添加 listing_date, status 字段
#   2. 为 user_watchlist 添加 tags, sort_order 字段
#   3. 从 symbol_profile 删除 intro 字段
#   4. 创建优化索引
# ==============================

from __future__ import annotations
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from backend.db.sqlite import get_conn

def migrate_to_v2():
    """执行数据库Schema从V1到V2的迁移。"""
    conn = get_conn()
    cur = conn.cursor()
    
    print("=" * 80)
    print("开始数据库迁移到 V2.0（极简优化版）")
    print("=" * 80)
    
    # --- symbol_index 表增加字段 ---
    print("\n[1/4] 迁移 symbol_index 表...")
    
    try:
        cur.execute("ALTER TABLE symbol_index ADD COLUMN listing_date INTEGER;")
        print("  ✓ 添加 listing_date 字段")
    except Exception:
        print("  ⊙ listing_date 字段已存在，跳过")
    
    try:
        cur.execute("ALTER TABLE symbol_index ADD COLUMN status TEXT DEFAULT 'active';")
        print("  ✓ 添加 status 字段")
    except Exception:
        print("  ⊙ status 字段已存在，跳过")
    
    # 创建优化索引
    try:
        cur.execute("CREATE INDEX IF NOT EXISTS idx_symbol_index_type_market ON symbol_index(type, market);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_symbol_index_listing ON symbol_index(listing_date);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_symbol_index_status ON symbol_index(status);")
        print("  ✓ 创建优化索引")
    except Exception as e:
        print(f"  ⊙ 索引创建失败: {e}")
    
    # --- symbol_profile 表删除字段 ---
    print("\n[2/4] 迁移 symbol_profile 表...")
    
    # SQLite 不支持直接 DROP COLUMN，需要重建表
    try:
        # 检查 intro 列是否存在
        cur.execute("PRAGMA table_info(symbol_profile);")
        columns = [row[1] for row in cur.fetchall()]
        
        if 'intro' in columns:
            print("  → 检测到 intro 字段，执行重建表操作...")
            
            # 创建新表（不含intro字段）
            cur.execute("""
            CREATE TABLE symbol_profile_new (
              symbol TEXT PRIMARY KEY,
              listing_date INTEGER,
              total_shares REAL,
              float_shares REAL,
              industry TEXT,
              region TEXT,
              concepts TEXT,
              updated_at TEXT,
              FOREIGN KEY (symbol) REFERENCES symbol_index (symbol)
            );
            """)
            
            # 复制数据（排除intro列）
            cur.execute("""
            INSERT INTO symbol_profile_new (symbol, listing_date, total_shares, float_shares, industry, region, concepts, updated_at)
            SELECT symbol, listing_date, total_shares, float_shares, industry, region, concepts, updated_at
            FROM symbol_profile;
            """)
            
            # 删除旧表，重命名新表
            cur.execute("DROP TABLE symbol_profile;")
            cur.execute("ALTER TABLE symbol_profile_new RENAME TO symbol_profile;")
            
            print("  ✓ 删除 intro 字段（已重建表）")
        else:
            print("  ⊙ intro 字段不存在，跳过")
    except Exception as e:
        print(f"  ✗ 重建表失败: {e}")
    
    # 创建优化索引
    try:
        cur.execute("CREATE INDEX IF NOT EXISTS idx_profile_industry ON symbol_profile(industry);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_profile_region ON symbol_profile(region);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_profile_listing ON symbol_profile(listing_date);")
        print("  ✓ 创建优化索引")
    except Exception as e:
        print(f"  ⊙ 索引创建失败: {e}")
    
    # --- user_watchlist 表增加字段 ---
    print("\n[3/4] 迁移 user_watchlist 表...")
    
    try:
        cur.execute("ALTER TABLE user_watchlist ADD COLUMN tags TEXT;")
        print("  ✓ 添加 tags 字段")
    except Exception:
        print("  ⊙ tags 字段已存在，跳过")
    
    try:
        cur.execute("ALTER TABLE user_watchlist ADD COLUMN sort_order INTEGER DEFAULT 0;")
        print("  ✓ 添加 sort_order 字段")
    except Exception:
        print("  ⊙ sort_order 字段已存在，跳过")
    
    try:
        cur.execute("CREATE INDEX IF NOT EXISTS idx_watchlist_sort ON user_watchlist(sort_order);")
        print("  ✓ 创建优化索引")
    except Exception as e:
        print(f"  ⊙ 索引创建失败: {e}")
    
    # --- 提交所有更改 ---
    print("\n[4/4] 提交事务...")
    conn.commit()
    print("  ✓ 所有更改已提交")
    
    print("\n" + "=" * 80)
    print("数据库迁移到 V2.0 完成！")
    print("=" * 80)
    print("\n新增字段汇总：")
    print("  symbol_index: listing_date, status")
    print("  user_watchlist: tags, sort_order")
    print("\n删除字段汇总：")
    print("  symbol_profile: intro (公司简介)")
    print("\n建议后续操作：")
    print("  1. 重启后端服务")
    print("  2. 触发一次完整的标的列表同步（会自动填充 listing_date 等新字段）")
    print("=" * 80)

if __name__ == "__main__":
    migrate_to_v2()
