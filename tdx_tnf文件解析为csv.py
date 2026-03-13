#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通达信 .tnf 文件全量解析器
============================
解析 shs.tnf / szs.tnf / bjs.tnf 文件，将全部360字节记录的已知字段
及未知区域原样提取，输出到 CSV 文件。

用法:
    python parse_tnf.py
    
    默认路径: D:\TDX_new\T0002\hq_cache\
    输出文件: 当前目录下 tnf_parsed_all.csv 及按市场分文件

文件结构:
    文件头: 50字节
    记录: 每条360字节
    记录数 = (文件大小 - 50) / 360
"""

import struct
import csv
import os
import sys
from pathlib import Path
from datetime import datetime


# ==============================================================================
# 常量定义
# ==============================================================================

HEADER_SIZE = 50
RECORD_SIZE = 360

# 默认文件路径
DEFAULT_BASE_DIR = r"D:\TDX_new\T0002\hq_cache"

TNF_FILES = {
    "SH": "shs.tnf",
    "SZ": "szs.tnf",
    "BJ": "bjs.tnf",
}

# 市场ID映射 (market_id字段实测值)
MARKET_ID_MAP = {
    0: "SZ",
    1: "SH",
    2: "BJ",
}


# ==============================================================================
# 文件头解析
# ==============================================================================

def parse_header(data: bytes) -> dict:
    """解析50字节文件头"""
    header = {}

    # 偏移 0x00-0x0F (16字节): 服务器IP地址
    ip_raw = data[0x00:0x10]
    header["server_ip"] = ip_raw.split(b'\x00')[0].decode('ascii', errors='replace').strip()

    # 偏移 0x10-0x31 (34字节): 其他头部数据
    header["header_0x10_raw_hex"] = data[0x10:0x32].hex()

    # 其中 0x30 处 uint32
    if len(data) >= 0x34:
        header["header_0x30_uint32"] = struct.unpack_from('<I', data, 0x30)[0]

    return header


# ==============================================================================
# 单条记录解析
# ==============================================================================

def parse_record(rec: bytes, record_index: int) -> dict:
    """
    解析单条360字节记录，提取全部已知字段和未知区域的原始hex。
    
    已知字段布局:
        +000 (20B)  证券代码 ASCII
        +01F (32B)  证券名称 GBK  (偏移31)
        +04C (4B)   类型 uint32   (偏移76)
        +04E (4B)   面值 float32  (偏移78) — 注意: 与上字段仅差2字节，可能是uint16+float32
        +058 (4B)   未知浮点 float32 (偏移88)
        +110 (4B)   未知字段       (偏移272)
        +114 (4B)   昨收价 float32 (偏移276)
        +118 (2B)   市场ID uint16 (偏移280)
        +11A (2B)   常量1 uint16  (偏移282)
        +149 (20B)  拼音简称 ASCII (偏移329)
    """
    row = {}
    row["_record_index"] = record_index

    # -------------------------------------------------------------------------
    # 已知字段
    # -------------------------------------------------------------------------

    # +000 证券代码 (20字节, ASCII, \0终止)
    code_raw = rec[0:20]
    row["code"] = code_raw.split(b'\x00')[0].decode('ascii', errors='replace').strip()
    row["code_raw_hex"] = code_raw.hex()

    # +014 代码尾部填充 (11字节, rec[20:31])  — 预期全零
    row["pad_014_hex"] = rec[20:31].hex()

    # +01F 证券名称 (32字节, GBK, \0终止, 偏移31)
    name_raw = rec[31:63]
    row["name"] = name_raw.split(b'\x00')[0].decode('gbk', errors='replace').strip()
    row["name_raw_hex"] = name_raw.hex()

    # +03F 名称尾部填充 (13字节, rec[63:76])  — 预期全零
    row["pad_03F_hex"] = rec[63:76].hex()

    # +04C 类型 (4字节 uint32, 偏移76)
    # 注意: 原文档标注+04C=偏移76, 但4字节uint32从76开始有对齐问题
    # 实际可能是 uint16 at 76 + float32 at 78, 这里都提取
    row["field_076_uint32"] = struct.unpack_from('<I', rec, 76)[0]
    row["field_076_uint16"] = struct.unpack_from('<H', rec, 76)[0]
    row["field_076_raw_hex"] = rec[76:80].hex()

    # +04E 面值 (4字节 float32, 偏移78)
    row["field_078_float32"] = struct.unpack_from('<f', rec, 78)[0]
    row["field_078_raw_hex"] = rec[78:82].hex()

    # +052 面值后填充 (6字节, rec[82:88])  — 预期全零
    row["pad_052_hex"] = rec[82:88].hex()

    # +058 未知浮点 (4字节 float32, 偏移88)
    row["field_088_float32"] = struct.unpack_from('<f', rec, 88)[0]
    row["field_088_raw_hex"] = rec[88:92].hex()

    # +05C 未知后填充 (4字节, rec[92:96])  — 预期全零
    row["pad_05C_hex"] = rec[92:96].hex()

    # +060 大段预留空间 (176字节, rec[96:272])  — 预期全零
    region_060 = rec[96:272]
    row["region_060_all_zero"] = all(b == 0 for b in region_060)
    row["region_060_hex"] = region_060.hex()

    # +110 未知字段 (4字节, 偏移272)
    row["field_272_raw_hex"] = rec[272:276].hex()
    row["field_272_uint32"] = struct.unpack_from('<I', rec, 272)[0]
    # 尝试多种解读
    row["field_272_uint16_lo"] = struct.unpack_from('<H', rec, 272)[0]
    row["field_272_uint16_hi"] = struct.unpack_from('<H', rec, 274)[0]
    row["field_272_bytes"] = f"{rec[272]:02X} {rec[273]:02X} {rec[274]:02X} {rec[275]:02X}"

    # +114 昨收价 (4字节 float32, 偏移276)
    row["price_float32"] = struct.unpack_from('<f', rec, 276)[0]
    row["price_raw_hex"] = rec[276:280].hex()

    # +118 市场ID (2字节 uint16, 偏移280)
    row["market_id"] = struct.unpack_from('<H', rec, 280)[0]

    # +11A 常量字段 (2字节 uint16, 偏移282)
    row["const_282"] = struct.unpack_from('<H', rec, 282)[0]

    # +11C 价格/市场后填充 (45字节, rec[284:329])  — 预期全零
    region_11C = rec[284:329]
    row["pad_11C_all_zero"] = all(b == 0 for b in region_11C)
    row["pad_11C_hex"] = region_11C.hex()

    # +149 拼音简称 (20字节, ASCII, 偏移329)
    pinyin_raw = rec[329:349]
    row["pinyin"] = pinyin_raw.split(b'\x00')[0].decode('ascii', errors='replace').strip()
    row["pinyin_raw_hex"] = pinyin_raw.hex()

    # +15D 拼音尾部填充 (11字节, rec[349:360])  — 预期全零
    row["pad_15D_hex"] = rec[349:360].hex()

    # -------------------------------------------------------------------------
    # 整条记录的完整hex (供二次分析)
    # -------------------------------------------------------------------------
    row["full_record_hex"] = rec.hex()

    return row


# ==============================================================================
# 整文件解析
# ==============================================================================

def parse_tnf_file(filepath: str, market_label: str) -> tuple:
    """
    解析整个 tnf 文件。
    返回 (header_dict, list_of_record_dicts)
    """
    filepath = Path(filepath)
    if not filepath.exists():
        print(f"  [跳过] 文件不存在: {filepath}")
        return None, []

    file_size = filepath.stat().st_size
    if file_size < HEADER_SIZE:
        print(f"  [跳过] 文件过小 ({file_size} bytes): {filepath}")
        return None, []

    with open(filepath, 'rb') as f:
        data = f.read()

    # 计算记录数
    num_records = (len(data) - HEADER_SIZE) // RECORD_SIZE
    remainder = (len(data) - HEADER_SIZE) % RECORD_SIZE

    print(f"  文件: {filepath.name}")
    print(f"  大小: {file_size:,} 字节")
    print(f"  记录数: {num_records:,}")
    if remainder:
        print(f"  ⚠ 尾部残余: {remainder} 字节")

    # 解析文件头
    header = parse_header(data[:HEADER_SIZE])
    header["file_name"] = filepath.name
    header["file_size"] = file_size
    header["num_records"] = num_records
    header["market_label"] = market_label

    print(f"  服务器IP: {header['server_ip']}")

    # 逐条解析记录
    records = []
    empty_count = 0

    for i in range(num_records):
        offset = HEADER_SIZE + i * RECORD_SIZE
        rec = data[offset:offset + RECORD_SIZE]

        row = parse_record(rec, i)
        row["_market_label"] = market_label
        row["_file_name"] = filepath.name
        row["_file_offset"] = offset

        if not row["code"]:
            empty_count += 1

        records.append(row)

    if empty_count:
        print(f"  空代码记录数: {empty_count}")
    print(f"  有效记录数: {num_records - empty_count}")

    return header, records


# ==============================================================================
# CSV 输出
# ==============================================================================

# CSV 列顺序定义
CSV_COLUMNS = [
    # 元信息
    "_market_label",
    "_file_name",
    "_record_index",
    "_file_offset",
    # 核心字段
    "code",
    "name",
    "pinyin",
    "field_076_uint16",     # type_val (作为uint16更合理)
    "field_078_float32",    # 面值
    "field_088_float32",    # 未知浮点
    "field_272_raw_hex",    # 未知字段
    "field_272_uint32",
    "field_272_uint16_lo",
    "field_272_uint16_hi",
    "field_272_bytes",
    "price_float32",        # 昨收价
    "market_id",
    "const_282",
    # 原始hex (供二次分析)
    "code_raw_hex",
    "name_raw_hex",
    "pinyin_raw_hex",
    "field_076_raw_hex",
    "field_076_uint32",
    "field_078_raw_hex",
    "field_088_raw_hex",
    "price_raw_hex",
    # 填充区域 (验证用)
    "pad_014_hex",
    "pad_03F_hex",
    "pad_052_hex",
    "pad_05C_hex",
    "region_060_all_zero",
    "pad_11C_all_zero",
    "pad_11C_hex",
    "pad_15D_hex",
    # 大段区域 (可选,很长)
    "region_060_hex",
    # 完整记录 (可选,极长)
    "full_record_hex",
]


def write_csv(records: list, output_path: str, include_full_hex: bool = False):
    """将记录列表写入CSV"""
    if not records:
        print(f"  无记录可写入: {output_path}")
        return

    columns = CSV_COLUMNS.copy()
    if not include_full_hex:
        # 默认不输出超长字段以减小文件体积
        columns = [c for c in columns if c not in ("region_060_hex", "full_record_hex")]

    output_path = Path(output_path)
    with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction='ignore')
        writer.writeheader()
        for row in records:
            writer.writerow(row)

    file_size = output_path.stat().st_size
    print(f"  ✓ 已写入: {output_path}  ({len(records):,} 条, {file_size:,} 字节)")


def write_headers_info(headers: list, output_path: str):
    """将文件头信息写入单独文件"""
    if not headers:
        return

    output_path = Path(output_path)
    with open(output_path, 'w', encoding='utf-8') as f:
        for h in headers:
            f.write(f"{'=' * 60}\n")
            f.write(f"文件: {h.get('file_name', 'N/A')}\n")
            f.write(f"{'=' * 60}\n")
            for k, v in h.items():
                f.write(f"  {k}: {v}\n")
            f.write("\n")

    print(f"  ✓ 文件头信息: {output_path}")


# ==============================================================================
# 主程序
# ==============================================================================

def main():
    print("=" * 70)
    print("  通达信 .tnf 文件全量解析器")
    print(f"  运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    # 确定输入目录
    base_dir = DEFAULT_BASE_DIR
    if len(sys.argv) > 1:
        base_dir = sys.argv[1]

    base_dir = Path(base_dir)
    print(f"\n输入目录: {base_dir}")

    if not base_dir.exists():
        print(f"\n✗ 目录不存在: {base_dir}")
        print(f"  用法: python {Path(__file__).name} [通达信hq_cache目录路径]")
        print(f"  示例: python {Path(__file__).name} D:\\TDX_new\\T0002\\hq_cache")
        sys.exit(1)

    # 确定输出目录 (当前工作目录)
    output_dir = Path(".")
    print(f"输出目录: {output_dir.resolve()}")

    # 是否输出完整hex列 (文件会很大)
    include_full_hex = False
    if "--full-hex" in sys.argv:
        include_full_hex = True
        print("⚠ 已启用完整hex输出模式，CSV文件将非常大")

    # 解析各市场文件
    all_records = []
    all_headers = []

    for market_label, filename in TNF_FILES.items():
        filepath = base_dir / filename
        print(f"\n{'─' * 50}")
        print(f"解析 {market_label} 市场: {filename}")
        print(f"{'─' * 50}")

        header, records = parse_tnf_file(str(filepath), market_label)

        if header:
            all_headers.append(header)

        if records:
            all_records.extend(records)

            # 写单市场CSV
            market_csv = output_dir / f"tnf_{market_label.lower()}.csv"
            write_csv(records, str(market_csv), include_full_hex)

    # 写合并CSV
    if all_records:
        print(f"\n{'─' * 50}")
        print(f"合并输出")
        print(f"{'─' * 50}")
        print(f"  总记录数: {len(all_records):,}")

        all_csv = output_dir / "tnf_all.csv"
        write_csv(all_records, str(all_csv), include_full_hex)

    # 写文件头信息
    if all_headers:
        header_file = output_dir / "tnf_headers.txt"
        write_headers_info(all_headers, str(header_file))

    # 输出统计摘要
    if all_records:
        print(f"\n{'=' * 70}")
        print(f"  解析完成统计")
        print(f"{'=' * 70}")

        # 按市场统计
        market_counts = {}
        for r in all_records:
            m = r["_market_label"]
            market_counts[m] = market_counts.get(m, 0) + 1
        for m, c in sorted(market_counts.items()):
            print(f"  {m}: {c:,} 条")
        print(f"  合计: {len(all_records):,} 条")

        # 按 type_val 统计
        type_counts = {}
        for r in all_records:
            t = r["field_076_uint16"]
            type_counts[t] = type_counts.get(t, 0) + 1
        print(f"\n  type_val 分布:")
        for t, c in sorted(type_counts.items()):
            print(f"    type={t}: {c:,} 条")

        # 按 market_id 统计
        mid_counts = {}
        for r in all_records:
            mid = r["market_id"]
            mid_counts[mid] = mid_counts.get(mid, 0) + 1
        print(f"\n  market_id 分布:")
        for mid, c in sorted(mid_counts.items()):
            label = MARKET_ID_MAP.get(mid, "未知")
            print(f"    market_id={mid} ({label}): {c:,} 条")

        # 空代码统计
        empty_codes = sum(1 for r in all_records if not r["code"])
        if empty_codes:
            print(f"\n  空代码记录: {empty_codes:,} 条")

        # const_282 验证
        const_vals = set(r["const_282"] for r in all_records)
        print(f"\n  const_282 唯一值: {const_vals}")

        # 填充区域验证
        non_zero_060 = sum(1 for r in all_records if not r["region_060_all_zero"])
        non_zero_11C = sum(1 for r in all_records if not r["pad_11C_all_zero"])
        print(f"  region_060 非零记录数: {non_zero_060}")
        print(f"  pad_11C 非零记录数: {non_zero_11C}")

    print(f"\n{'=' * 70}")
    print(f"  全部完成!")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
