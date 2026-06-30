#!/usr/bin/env python3
"""
JSONL 文件切分与合并工具
"""

import os
import json
import argparse
from pathlib import Path


def split_jsonl(input_file: str, max_size_mb: float = 45.0, output_dir: str = None) -> list:
    input_path = Path(input_file)
    if not input_path.exists():
        raise FileNotFoundError(f"文件不存在: {input_file}")

    max_size_bytes = int(max_size_mb * 1024 * 1024)

    if output_dir is None:
        output_dir = input_path.parent / f"split_{input_path.stem}"
    else:
        output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    meta = {
        "original_file": input_path.name,
        "max_size_mb": max_size_mb,
        "total_lines": 0,
        "original_total_lines": 0,
        "split_lines": 0,
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
            meta["original_total_lines"] += 1

            if line_bytes <= max_size_bytes:
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
            else:
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    if part_file is None:
                        part_path = output_dir / f"part_{part_num}.jsonl"
                        part_file = open(part_path, 'w', encoding='utf-8')
                        current_size = 0
                        current_lines = 0

                    part_file.write(line)
                    current_size += line_bytes
                    current_lines += 1
                    meta["total_lines"] += 1
                    continue

                split_id = line_num
                payload = obj.get("payload", {})
                images = payload.get("images", [])

                small_payload = {k: v for k, v in payload.items() if k != "images"}
                header_obj = {
                    "timestamp": obj.get("timestamp"),
                    "type": obj.get("type"),
                    "payload": small_payload,
                    "_split_id": split_id,
                    "_split_total": len(images) + 1,
                    "_split_index": 0
                }

                header_line = json.dumps(header_obj, ensure_ascii=False) + '\n'
                header_size = len(header_line.encode('utf-8'))

                if part_file is None or current_size + header_size > max_size_bytes:
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

                part_file.write(header_line)
                current_size += header_size
                current_lines += 1
                meta["total_lines"] += 1

                for i, image in enumerate(images, 1):
                    image_obj = {
                        "_split_id": split_id,
                        "_split_total": len(images) + 1,
                        "_split_index": i,
                        "payload": {"images": [image]}
                    }
                    image_line = json.dumps(image_obj, ensure_ascii=False) + '\n'
                    image_size = len(image_line.encode('utf-8'))

                    if part_file is None or current_size + image_size > max_size_bytes:
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

                    part_file.write(image_line)
                    current_size += image_size
                    current_lines += 1
                    meta["total_lines"] += 1

                meta["split_lines"] += len(images) + 1

    if part_file is not None:
        part_file.close()
        meta["parts"].append({
            "file": f"part_{part_num}.jsonl",
            "lines": current_lines,
            "size_bytes": current_size
        })
        part_files.append(str(output_dir / f"part_{part_num}.jsonl"))

    meta_path = output_dir / "meta.json"
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(meta, f, indent=2)

    print(f"切分完成:")
    print(f"  原文件: {input_path.name}")
    print(f"  原始行数: {meta['original_total_lines']}")
    print(f"  切分后行数: {meta['total_lines']}")
    print(f"  拆分行数: {meta['split_lines']}")
    print(f"  切分数: {len(meta['parts'])} 个部分")
    for p in meta['parts']:
        size_mb = p['size_bytes'] / (1024 * 1024)
        print(f"    - {p['file']}: {p['lines']} 行, {size_mb:.2f} MB")
    print(f"  输出目录: {output_dir}")
    print(f"  元信息文件: {meta_path}")

    return part_files


def merge_jsonl(input_dir: str, output_file: str = None) -> str:
    input_path = Path(input_dir)
    meta_path = input_path / "meta.json"

    if not meta_path.exists():
        raise FileNotFoundError(f"元信息文件不存在: {meta_path}")

    with open(meta_path, 'r', encoding='utf-8') as f:
        meta = json.load(f)

    if output_file is None:
        output_file = input_path.parent / meta["original_file"]
    else:
        output_file = Path(output_file)

    split_buffers = {}
    total_lines = 0

    with open(output_file, 'w', encoding='utf-8') as out_f:
        for part_info in meta["parts"]:
            part_path = input_path / part_info["file"]
            with open(part_path, 'r', encoding='utf-8') as part_f:
                for line in part_f:
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        out_f.write(line + '\n')
                        total_lines += 1
                        continue

                    if "_split_id" in obj:
                        split_id = obj["_split_id"]
                        split_index = obj["_split_index"]
                        split_total = obj["_split_total"]

                        if split_id not in split_buffers:
                            split_buffers[split_id] = {
                                "total": split_total,
                                "header": None,
                                "images": []
                            }

                        buffer = split_buffers[split_id]

                        if split_index == 0:
                            buffer["header"] = obj.copy()
                            del buffer["header"]["_split_id"]
                            del buffer["header"]["_split_total"]
                            del buffer["header"]["_split_index"]
                        else:
                            img_data = obj.get("payload", {}).get("images", [])
                            buffer["images"].extend(img_data)

                        if buffer["header"] is not None and len(buffer["images"]) == split_total - 1:
                            merged_obj = buffer["header"].copy()
                            merged_obj["payload"]["images"] = buffer["images"]
                            merged_line = json.dumps(merged_obj, ensure_ascii=False)
                            out_f.write(merged_line + '\n')
                            total_lines += 1
                            del split_buffers[split_id]
                    else:
                        out_f.write(line + '\n')
                        total_lines += 1

    for split_id, buffer in split_buffers.items():
        print(f"  警告: 拆分对象 {split_id} 未完整收集")

    print(f"合并完成:")
    print(f"  输出文件: {output_file}")
    print(f"  合并行数: {total_lines}")
    print(f"  原始行数: {meta['original_total_lines']}")

    if total_lines != meta['original_total_lines']:
        print(f"  警告: 行数不一致!")

    return str(output_file)


def main():
    parser = argparse.ArgumentParser(description="JSONL 文件切分与合并工具")
    parser.add_argument("action", choices=["split", "merge"], help="操作类型: split 或 merge")
    parser.add_argument("--input", "-i", required=True, help="输入文件（split）或输入目录（merge）")
    parser.add_argument("--output", "-o", help="输出目录（split）或输出文件（merge）")
    parser.add_argument("--max-size", "-m", type=float, default=45.0, help="切分时每个文件的最大大小（MB），默认 45")

    args = parser.parse_args()

    if args.action == "split":
        split_jsonl(args.input, args.max_size, args.output)
    else:
        merge_jsonl(args.input, args.output)


if __name__ == "__main__":
    main()