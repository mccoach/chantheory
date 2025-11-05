# scripts/fix_db_imports.py
# ==============================
# 说明：自动修复所有文件中的 backend.db.sqlite 导入语句
# - 执行：python scripts/fix_db_imports.py
# ==============================

import re
from pathlib import Path

# 获取项目根目录
project_root = Path(__file__).resolve().parents[1]

print("=" * 80)
print("开始批量修复 backend.db.sqlite 导入语句...")
print("=" * 80)
print(f"项目根目录: {project_root}")
print(f"当前工作目录: {Path.cwd()}")

def fix_imports_in_file(file_path: Path) -> bool:
    """修复单个文件中的导入语句。"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # 替换 from backend.db.sqlite import -> from backend.db import
        content = re.sub(
            r'from\s+backend\.db\.sqlite\s+import',
            'from backend.db import',
            content
        )
        
        # 替换 import backend.db.sqlite -> import backend.db
        content = re.sub(
            r'import\s+backend\.db\.sqlite',
            'import backend.db',
            content
        )
        
        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        
        return False
        
    except Exception as e:
        print(f"  ✗ 处理失败: {e}")
        return False


def main():
    modified_files = []
    scanned_count = 0
    skipped_count = 0
    
    # 扫描整个 backend 目录
    backend_path = project_root / "backend"
    
    if not backend_path.exists():
        print(f"✗ 错误：backend 目录不存在: {backend_path}")
        return
    
    print(f"\n正在扫描: {backend_path}\n")
    
    for file_path in backend_path.rglob("*.py"):
        # 跳过特定目录
        relative_path = file_path.relative_to(project_root)
        
        if '__pycache__' in str(relative_path):
            skipped_count += 1
            continue
        
        # 跳过 backend/db/ 目录本身的新模块文件
        if file_path.parent == backend_path / "db":
            print(f"  ⊙ 跳过 db 模块: {relative_path}")
            skipped_count += 1
            continue
        
        scanned_count += 1
        
        # 先读取文件内容检查是否包含目标字符串
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if 'backend.db.sqlite' in content:
                print(f"  → 发现需要修复: {relative_path}")
                
                if fix_imports_in_file(file_path):
                    modified_files.append(file_path)
                    print(f"    ✓ 修复完成")
                else:
                    print(f"    ⊙ 无需修改（可能已是正确格式）")
        
        except Exception as e:
            print(f"  ✗ 无法读取: {relative_path}, 错误: {e}")
    
    print("\n" + "=" * 80)
    print(f"扫描统计:")
    print(f"  - 已扫描: {scanned_count} 个文件")
    print(f"  - 已跳过: {skipped_count} 个文件")
    print(f"  - 已修改: {len(modified_files)} 个文件")
    print("=" * 80)
    
    if modified_files:
        print("\n✓ 成功修改的文件：")
        for f in modified_files:
            print(f"  - {f.relative_to(project_root)}")
    else:
        print("\n⊙ 未发现需要修改的文件。")
        print("\n可能的原因：")
        print("  1. 所有文件已经使用正确的导入格式")
        print("  2. 或者这些文件目前还未使用数据库功能")
        print("\n建议手动检查关键文件:")
        key_files = [
            "backend/services/symbol_sync.py",
            "backend/services/sync_task_executor.py",
            "backend/services/sync_data_fetcher.py",
            "backend/routers/candles.py",
            "backend/routers/symbols.py",
        ]
        for kf in key_files:
            kf_path = project_root / kf
            if kf_path.exists():
                try:
                    with open(kf_path, 'r', encoding='utf-8') as f:
                        if 'backend.db.sqlite' in f.read():
                            print(f"  ! {kf} - 包含旧导入")
                except:
                    pass

if __name__ == "__main__":
    main()
