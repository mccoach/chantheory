from pytdx.reader import GbbqReader

def export_gbbq_to_txt(gbbq_path, out_txt_path, encoding="utf-8-sig"):
    reader = GbbqReader()
    df = reader.get_df(gbbq_path)

    # 统一按日期排序（如果 df 里有 date 字段）
    for col in ("code", "market", "date", "datetime"):
        if col not in df.columns:
            pass
    if "code" in df.columns and "date" in df.columns:
        df = df.sort_values(["code", "date"], kind="mergesort")
    elif "code" in df.columns:
        df = df.sort_values(["code"], kind="mergesort")

    # 写 TXT：tab 分隔，首行表头
    with open(out_txt_path, "w", encoding=encoding, newline="\n") as f:
        f.write("\t".join(df.columns) + "\n")
        df.to_csv(f, sep="\t", index=False, header=False, lineterminator="\n")

    return df.shape[0], list(df.columns)

if __name__ == "__main__":
    gbbq_path = r"D:\TDX_new\T0002\hq_cache\gbbq"
    out_txt = r"D:\TDX_new\T0002\hq_cache\gbbq_dump.txt"

    n, cols = export_gbbq_to_txt(gbbq_path, out_txt)
    print("已导出记录数:", n)
    print("字段:", cols)
    print("输出文件:", out_txt)
