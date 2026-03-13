# tdx_probe.py
# 用途：探测 pytdx.reader 读取 day/lc1/lc5 的返回结构（字段名、示例数据）
# 运行：python tdx_probe.py "D:\TDX_new\vipdoc\sh\lday\sh600000.day"

from __future__ import annotations

import sys
from pathlib import Path


def _print_df_like(obj, name: str) -> None:
    print(f"\n=== {name} ===")
    print("type:", type(obj))
    try:
        import pandas as pd  # noqa
        if hasattr(obj, "columns") and hasattr(obj, "head"):
            print("shape:", getattr(obj, "shape", None))
            try:
                print("columns:", list(obj.columns))
            except Exception:
                pass
            try:
                print("head(3):")
                print(obj.head(3))
            except Exception:
                pass
            try:
                print("tail(3):")
                print(obj.tail(3))
            except Exception:
                pass
            return
    except Exception:
        pass

    # list[dict] 或 list[tuple] 之类
    if isinstance(obj, list):
        print("len:", len(obj))
        if obj:
            print("first item type:", type(obj[0]))
            print("first item repr:", repr(obj[0])[:500])
            print("last item repr:", repr(obj[-1])[:500])
        return

    # dict
    if isinstance(obj, dict):
        print("keys:", list(obj.keys())[:50])
        return

    # 其他
    try:
        print("repr:", repr(obj)[:1000])
    except Exception:
        pass


def _try_read_with_pytdx(file_path: Path):
    """
    尝试多种常见 pytdx.reader 入口。
    目的：在不知道你本地 pytdx 版本/reader 类名时，尽量自动找到可用的读取方式。
    """
    suffix = file_path.suffix.lower()

    # 1) 直接按常见类名尝试导入
    candidates = []

    # 常见：pytdx.reader 里会按类型提供不同 Reader
    # 这里用“字符串导入”方式，避免 import 失败就整个脚本退出
    def _import_attr(module_name: str, attr: str):
        try:
            mod = __import__(module_name, fromlist=[attr])
            return getattr(mod, attr, None)
        except Exception:
            return None

    # day 日线
    candidates.append(("pytdx.reader.TdxDailyBarReader",
                       _import_attr("pytdx.reader", "TdxDailyBarReader")))
    candidates.append(("pytdx.reader.TdxDayReader",
                       _import_attr("pytdx.reader", "TdxDayReader")))
    candidates.append(("pytdx.reader.TdxFileReader",
                       _import_attr("pytdx.reader", "TdxFileReader")))

    # 分钟线
    candidates.append(("pytdx.reader.TdxMinuteBarReader",
                       _import_attr("pytdx.reader", "TdxMinuteBarReader")))
    candidates.append(("pytdx.reader.TdxMinBarReader",
                       _import_attr("pytdx.reader", "TdxMinBarReader")))
    candidates.append(
        ("pytdx.reader.TdxLcReader", _import_attr("pytdx.reader",
                                                  "TdxLcReader")))

    # 2) 逐个尝试：实例化 + read
    errors = []
    for tag, cls in candidates:
        if cls is None:
            continue
        try:
            reader = cls()
        except Exception as e:
            errors.append((tag, f"init failed: {e}"))
            continue

        # 常见方法名：read / get_df / get_data / parse
        for method_name in ("read", "get_df", "get_data", "parse"):
            if not hasattr(reader, method_name):
                continue
            method = getattr(reader, method_name)
            try:
                out = method(str(file_path))
                return tag, method_name, out, errors
            except Exception as e:
                errors.append((f"{tag}.{method_name}", str(e)))

    # 3) 全失败
    return None, None, None, errors


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python tdx_probe.py <path_to_.day_or_.lc1_or_.lc5>")
        return 2

    p = Path(sys.argv[1]).expanduser().resolve()
    print("file:", str(p))
    print("exists:", p.exists())
    print("suffix:", p.suffix.lower())
    if not p.exists():
        print("ERROR: file not found")
        return 1

    try:
        import pytdx  # noqa
        import pytdx.reader  # noqa
        print("pytdx imported OK")
        try:
            import pkgutil
            import pytdx.reader as rmod
            print("pytdx.reader attrs sample:",
                  [x for x in dir(rmod) if "Tdx" in x][:50])
        except Exception:
            pass
    except Exception as e:
        print("ERROR: pytdx import failed:", e)
        return 1

    tag, method_name, out, errors = _try_read_with_pytdx(p)

    if tag is None:
        print("\nAll candidates failed.")
        print("Errors (first 30):")
        for i, (k, v) in enumerate(errors[:30], start=1):
            print(f"{i:02d}. {k}: {v}")
        return 1

    print(f"\nReader used: {tag}.{method_name}")
    _print_df_like(out, "output")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
