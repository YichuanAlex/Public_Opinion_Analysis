#!/usr/bin/env python3
"""
JSONL 文件切分与合并工具
- split_jsonl(): 将大 JSONL 文件切分成多个小于指定大小的小文件
- merge_jsonl(): 将切分的小文件合并回原始文件
"""

import os
import json
import argparse
from pathlib import Path


def split_jsonl(input_file: str, max_size_mb: float = 25.0, output_dir: str = None) -> list:
    """
    将 JSONL 文件切分成多个小文件

    Args:
        input_file: 输入的 JSONL 文件路径
        max_size_mb: 每个小文件的最大大小（MB）
        output_dir: 输出目录，默认为输入文件同目录下的 `split_<filename>` 子目录

    Returns:
        生成的切分文件列表
    """
    input_path = Path(input_file)
    if not input_path.exists():
        raise FileNotFoundError(f"文件不存在: {input_file}")

    max_size_bytes = int(max_size_mb * 1024 * 1024)

    # 创建输出目录
    if output_dir is None:
        output_dir = input_path.parent / f"split_{input_path.stem}"
    else:
        output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 保存元信息，用于合并
    meta = {
        "original_file": input_path.name,
        "max_size_mb": max_size_mb,
        "total_lines": 0,
        "parts": []
    }

    part_num = 1
    current_size = 0
    current_lines = 0
    part_file = None
    part_files = []

    with open(input_path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line_bytes = len(line.encode('utf-8'))

            # 如果当前部分文件为空或超出大小限制，创建新的部分文件
            if part_file is None or current_size + line_bytes > max_size_bytes:
                if part_file is not None:
                    part_file.close()
                    meta["parts"].append({
                        "file": f"part_{part_num}.jsonl",
                        "lines": current_lines,
                        "size_bytes": current_size
                    })
                    part_files.append(str(output_dir / f"part_{part_num}.jsonl"))
                    part_num += 1

                part_path = output_dir / f"part_{part_num}.jsonl"
                part_file = open(part_path, 'w', encoding='utf-8')
                current_size = 0
                current_lines = 0

            part_file.write(line)
            current_size += line_bytes
            current_lines += 1
            meta["total_lines"] += 1

    # 关闭最后一个部分文件
    if part_file is not None:
        part_file.close()
        meta["parts"].append({
            "file": f"part_{part_num}.jsonl",
            "lines": current_lines,
            "size_bytes": current_size
        })
        part_files.append(str(output_dir / f"part_{part_num}.jsonl"))

    # 保存元信息文件
    meta_path = output_dir / "meta.json"
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(meta, f, indent=2)

    print(f"切分完成:")
    print(f"  原文件: {input_path.name}")
    print(f"  总行数: {meta['total_lines']}")
    print(f"  切分数: {len(meta['parts'])} 个部分")
    for p in meta['parts']:
        size_mb = p['size_bytes'] / (1024 * 1024)
        print(f"    - {p['file']}: {p['lines']} 行, {size_mb:.2f} MB")
    print(f"  输出目录: {output_dir}")
    print(f"  元信息文件: {meta_path}")

    return part_files


def merge_jsonl(input_dir: str, output_file: str = None) -> str:
    """
    将切分的小文件合并回原始 JSONL 文件

    Args:
        input_dir: 包含切分文件的目录
        output_file: 输出文件路径，默认为原始文件名（从 meta.json 读取）

    Returns:
        合并后的文件路径
    """
    input_path = Path(input_dir)
    meta_path = input_path / "meta.json"

    if not meta_path.exists():
        raise FileNotFoundError(f"元信息文件不存在: {meta_path}")

    with open(meta_path, 'r', encoding='utf-8') as f:
        meta = json.load(f)

    # 确定输出文件
    if output_file is None:
        output_file = input_path.parent / meta["original_file"]
    else:
        output_file = Path(output_file)

    # 按顺序合并
    total_lines = 0
    with open(output_file, 'w', encoding='utf-8') as out_f:
        for part_info in meta["parts"]:
            part_path = input_path / part_info["file"]
            with open(part_path, 'r', encoding='utf-8') as part_f:
                for line in part_f:
                    out_f.write(line)
                    total_lines += 1

    print(f"合并完成:")
    print(f"  输出文件: {output_file}")
    print(f"  合并行数: {total_lines}")
    print(f"  原始行数: {meta['total_lines']}")

    if total_lines != meta['total_lines']:
        print(f"  警告: 行数不一致!")

    return str(output_file)


def main():
    parser = argparse.ArgumentParser(description="JSONL 文件切分与合并工具")
    parser.add_argument("action", choices=["split", "merge"], help="操作类型: split 或 merge")
    parser.add_argument("--input", "-i", required=True, help="输入文件（split）或输入目录（merge）")
    parser.add_argument("--output", "-o", help="输出目录（split）或输出文件（merge）")
    parser.add_argument("--max-size", "-m", type=float, default=25.0, help="切分时每个文件的最大大小（MB），默认 25")

    args = parser.parse_args()

    if args.action == "split":
        split_jsonl(args.input, args.max_size, args.output)
    else:
        merge_jsonl(args.input, args.output)


if __name__ == "__main__":
    main()