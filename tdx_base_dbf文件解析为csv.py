"""
通达信 base.dbf 全量解析工具
将 DBF 文件原样解析并输出为 CSV 文件

用法:
    python parse_base_dbf.py
    或修改底部的文件路径后运行
"""

import struct
import csv
import os
import sys
from datetime import date


def parse_dbf(dbf_path, csv_path=None, encoding='gbk'):
    """
    解析 DBF 文件（支持 dBASE III/IV/V/Visual FoxPro 等常见变体）
    不依赖任何第三方库，纯手工解析二进制结构

    参数:
        dbf_path: DBF 文件路径
        csv_path: 输出 CSV 路径（默认在同目录下生成同名 .csv）
        encoding: 字符串字段编码（通达信用 GBK）
    """

    if csv_path is None:
        csv_path = os.path.splitext(dbf_path)[0] + '.csv'

    with open(dbf_path, 'rb') as f:
        data = f.read()

    print(f"文件: {dbf_path}")
    print(f"文件大小: {len(data):,} 字节")
    print()

    # ========================================================================
    # 一、解析文件头 (32 字节)
    # ========================================================================
    if len(data) < 32:
        print("错误: 文件太小，不是有效的 DBF 文件")
        return

    version = data[0]
    yy, mm, dd = data[1], data[2], data[3]
    # 年份: YY 是相对于 1900 的偏移
    try:
        last_update = date(1900 + yy, mm, dd)
    except ValueError:
        last_update = f"raw({yy},{mm},{dd})"

    num_records = struct.unpack_from('<I', data, 4)[0]
    header_size = struct.unpack_from('<H', data, 8)[0]
    record_size = struct.unpack_from('<H', data, 10)[0]

    # 保留字段和标志
    reserved_12_13 = data[12:14]  # 未完成的事务
    encryption_flag = data[15]  # 加密标志
    reserved_16_27 = data[16:28]  # 多用户保留
    mdx_flag = data[28]  # MDX 标志
    language_driver = data[29]  # 语言驱动 ID
    reserved_30_31 = data[30:32]

    print("=" * 70)
    print("DBF 文件头信息")
    print("=" * 70)
    print(f"  版本标志字节:     0x{version:02X} (十进制 {version})")

    # 解读版本
    version_base = version & 0x07
    version_names = {
        0x02: "FoxBASE",
        0x03: "dBASE III / FoxBASE+",
        0x04: "dBASE IV",
        0x05: "dBASE V",
        0x30: "Visual FoxPro",
        0x31: "Visual FoxPro (自增列)",
        0x32: "Visual FoxPro (Varchar/Varbinary)",
        0x43: "dBASE IV SQL 表 (无 memo)",
        0x63: "dBASE IV SQL 系统文件",
        0x83: "dBASE III + memo",
        0x8B: "dBASE IV + memo",
        0x8E: "dBASE IV + SQL 表",
        0xCB: "dBASE IV SQL 表 + memo",
        0xF5: "FoxPro 2.x + memo",
        0xFB: "FoxBASE",
    }
    version_desc = version_names.get(version, f"未知(0x{version:02X})")
    has_memo = bool(version & 0x80)
    print(f"  版本说明:         {version_desc}")
    print(f"  包含 Memo 字段:   {'是' if has_memo else '否'}")
    print(f"  最后更新日期:     {last_update}")
    print(f"  记录总数:         {num_records:,}")
    print(f"  文件头总长度:     {header_size} 字节")
    print(f"  每条记录长度:     {record_size} 字节")
    print(f"  加密标志:         0x{encryption_flag:02X}")
    print(f"  MDX 标志:         0x{mdx_flag:02X}")
    print(f"  语言驱动 ID:      0x{language_driver:02X} ({language_driver})")

    # ========================================================================
    # 二、解析字段描述符 (每个 32 字节, 以 0x0D 结尾)
    # ========================================================================
    fields = []
    offset = 32

    while offset < header_size - 1:
        # 检查是否到达字段描述符终止符
        if data[offset] == 0x0D:
            break

        if offset + 32 > len(data):
            print(f"警告: 字段描述符在偏移 {offset} 处被截断")
            break

        field_data = data[offset:offset + 32]

        # 字段名: 前 11 字节, \0 终止的 ASCII
        field_name_raw = field_data[0:11]
        field_name = field_name_raw.split(b'\x00')[0].decode(
            'ascii', errors='replace').strip()

        field_type = chr(field_data[11])  # 字段类型 (C/N/D/L/F/M/B/G/P/Y/T/I/...)
        field_reserved_12_15 = field_data[12:16]  # 保留（或 Visual FoxPro 中为偏移）
        field_length = field_data[16]  # 字段长度
        field_decimal = field_data[17]  # 小数位数
        field_reserved_18_19 = field_data[18:20]  # 保留
        work_area_id = field_data[20]  # 工作区 ID
        field_reserved_21_31 = field_data[21:32]  # 其余保留字节

        # Visual FoxPro 扩展: 某些版本把 field_data[12:16] 当做 displacement
        # 这里都记录下来以备用
        displacement = struct.unpack_from('<I', field_data, 12)[0]

        fields.append({
            'name': field_name,
            'type': field_type,
            'length': field_length,
            'decimal': field_decimal,
            'displacement': displacement,
            'raw_12_15': field_reserved_12_15,
        })

        offset += 32

    print()
    print("=" * 70)
    print(f"字段定义 (共 {len(fields)} 个字段)")
    print("=" * 70)
    print(f"  {'#':>3}  {'字段名':<16} {'类型':>4} {'长度':>6} {'小数':>6}  说明")
    print(
        f"  {'---':>3}  {'-' * 16:<16} {'----':>4} {'------':>6} {'------':>6}  {'-' * 20}"
    )

    type_desc_map = {
        'C': '字符(Character)',
        'N': '数值(Numeric)',
        'F': '浮点(Float)',
        'D': '日期(Date YYYYMMDD)',
        'L': '逻辑(Logical T/F)',
        'M': '备注(Memo)',
        'B': '双精度(Double)/二进制Memo',
        'G': 'OLE对象(General)',
        'P': '图片(Picture)',
        'Y': '货币(Currency)',
        'T': '日期时间(DateTime)',
        'I': '整数(Integer)',
        '0': '标志(NullFlags)',
        'Q': '二进制(Varbinary)',
        'V': '可变长(Varchar)',
    }

    calculated_record_size = 1  # 删除标记占 1 字节
    for i, fld in enumerate(fields):
        desc = type_desc_map.get(fld['type'], f"未知({fld['type']})")
        print(
            f"  {i + 1:>3}  {fld['name']:<16} {fld['type']:>4} {fld['length']:>6} {fld['decimal']:>6}  {desc}"
        )
        calculated_record_size += fld['length']

    print()
    print(f"  字段长度合计+1(删除标记) = {calculated_record_size}")
    print(f"  文件头声明的记录长度     = {record_size}")
    if calculated_record_size != record_size:
        print(f"  ⚠ 不一致! 差异 = {record_size - calculated_record_size} 字节")

    # ========================================================================
    # 三、解析所有记录
    # ========================================================================
    print()
    print("=" * 70)
    print(f"开始解析 {num_records:,} 条记录...")
    print("=" * 70)

    records = []
    data_start = header_size
    skipped = 0
    errors = 0

    for rec_idx in range(num_records):
        rec_offset = data_start + rec_idx * record_size

        if rec_offset + record_size > len(data):
            print(f"  警告: 记录 #{rec_idx + 1} 超出文件边界，停止解析")
            break

        rec_data = data[rec_offset:rec_offset + record_size]

        # 第一个字节: 删除标记 (0x20=正常, 0x2A='*'=已删除)
        delete_flag = rec_data[0]
        is_deleted = (delete_flag == 0x2A)

        row = {}
        row['_DELETED'] = '*' if is_deleted else ''

        field_offset = 1  # 跳过删除标记

        for fld in fields:
            raw = rec_data[field_offset:field_offset + fld['length']]
            field_offset += fld['length']

            ft = fld['type']

            try:
                if ft == 'C':
                    # 字符型: 用 GBK 解码
                    value = raw.decode(
                        encoding, errors='replace').rstrip('\x00').rstrip()
                elif ft == 'N' or ft == 'F':
                    # 数值型 / 浮点型: ASCII 数字字符串
                    txt = raw.decode('ascii', errors='replace').strip()
                    if txt == '' or txt == '.' or txt.startswith('*'):
                        value = ''
                    else:
                        # 保留原始字符串，不做浮点转换，避免精度丢失
                        value = txt
                elif ft == 'D':
                    # 日期型: 8 字节 ASCII "YYYYMMDD"
                    value = raw.decode('ascii', errors='replace').strip()
                elif ft == 'L':
                    # 逻辑型
                    ch = chr(raw[0]) if raw else '?'
                    value = ch
                elif ft == 'M':
                    # Memo 型: 存的是 block 编号 (ASCII 或 binary)
                    txt = raw.decode('ascii',
                                     errors='replace').strip('\x00').strip()
                    value = txt if txt else ''
                elif ft == 'I':
                    # 整数型 (4 字节 little-endian)
                    if fld['length'] == 4:
                        value = struct.unpack_from('<i', raw, 0)[0]
                    else:
                        value = raw.hex()
                elif ft == 'B':
                    # 双精度 (8 字节) 或 二进制 Memo
                    if fld['length'] == 8:
                        value = struct.unpack_from('<d', raw, 0)[0]
                    else:
                        value = raw.hex()
                elif ft == 'Y':
                    # 货币型 (8 字节, 实际是 int64 / 10000)
                    if fld['length'] == 8:
                        raw_val = struct.unpack_from('<q', raw, 0)[0]
                        value = raw_val / 10000.0
                    else:
                        value = raw.hex()
                elif ft == 'T':
                    # 日期时间 (8 字节)
                    if fld['length'] == 8:
                        # Julian Day Number (4 bytes) + milliseconds since midnight (4 bytes)
                        jdn = struct.unpack_from('<I', raw, 0)[0]
                        ms = struct.unpack_from('<I', raw, 4)[0]
                        value = f"JDN={jdn},ms={ms}"
                    else:
                        value = raw.hex()
                elif ft == '0':
                    # NullFlags
                    value = raw.hex()
                else:
                    # 其他未知类型: 输出 hex
                    value = raw.hex()
            except Exception as e:
                value = f"ERR:{raw.hex()}"
                errors += 1

            row[fld['name']] = value

        records.append(row)

    print(f"  解析完成: {len(records):,} 条记录")
    if skipped:
        print(f"  跳过已删除记录: {skipped}")
    if errors:
        print(f"  解析错误: {errors}")

    # ========================================================================
    # 四、输出 CSV
    # ========================================================================
    # 构建表头: _DELETED + 所有字段名
    headers = ['_DELETED'] + [fld['name'] for fld in fields]

    with open(csv_path, 'w', newline='', encoding='utf-8-sig') as csvf:
        writer = csv.DictWriter(csvf,
                                fieldnames=headers,
                                extrasaction='ignore')
        writer.writeheader()
        for row in records:
            writer.writerow(row)

    csv_size = os.path.getsize(csv_path)
    print()
    print("=" * 70)
    print(f"CSV 已保存: {csv_path}")
    print(f"CSV 大小:   {csv_size:,} 字节")
    print(f"记录数:     {len(records):,}")
    print(f"字段数:     {len(fields)}")
    print("=" * 70)

    # ========================================================================
    # 五、打印前几条记录预览
    # ========================================================================
    preview_count = min(10, len(records))
    print()
    print(f"前 {preview_count} 条记录预览:")
    print("-" * 70)

    for i in range(preview_count):
        row = records[i]
        print(f"  记录 #{i + 1}:")
        for h in headers:
            val = row.get(h, '')
            if val != '' and val != ' ':
                print(f"    {h:<20} = {val}")
        print()

    return records, fields


def main():
    # =============================================
    # 配置区: 修改这里的路径
    # =============================================
    dbf_path = r"D:\TDX_new\T0002\hq_cache\base.dbf"
    csv_path = None  # None 表示自动生成同名 .csv

    # 如果命令行传了参数，优先使用
    if len(sys.argv) >= 2:
        dbf_path = sys.argv[1]
    if len(sys.argv) >= 3:
        csv_path = sys.argv[2]

    if not os.path.exists(dbf_path):
        print(f"错误: 文件不存在 - {dbf_path}")
        print()
        print("用法:")
        print(f"  python {os.path.basename(__file__)} <dbf文件路径> [csv输出路径]")
        print()
        print("示例:")
        print(
            f'  python {os.path.basename(__file__)} "D:\\TDX_new\\T0002\\hq_cache\\base.dbf"'
        )
        sys.exit(1)

    parse_dbf(dbf_path, csv_path, encoding='gbk')


if __name__ == '__main__':
    main()
