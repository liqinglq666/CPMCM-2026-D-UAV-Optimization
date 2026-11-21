#!/usr/bin/env python3
"""只读检查 Git 已跟踪文件的体积与相同内容，不删除或修改任何文件。"""

from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "paper" / "final_v2" / "manifest.json"
PROTECTED_PREFIXES = (
    "submission/",
    "archive/",
    "paper/final/",
    "paper/final_v2/",
    "results/",
    "config/",
    "data/",
)


def tracked_files():
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    for item in result.stdout.split(b"\0"):
        if not item:
            continue
        name = item.decode("utf-8", errors="surrogateescape").replace("\\", "/")
        path = ROOT / name
        if path.is_file():
            yield name, path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def manifest_paths() -> set[str] | None:
    if not MANIFEST.is_file():
        return None  # Archived manifest is not an empty manifest.
    content = json.loads(MANIFEST.read_text(encoding="utf-8"))
    return set(content.get("files", {}))


def build_report(limit: int, min_duplicate_bytes: int) -> dict:
    protected = manifest_paths()
    roots: dict[str, dict[str, int]] = defaultdict(lambda: {"files": 0, "bytes": 0})
    duplicates: dict[tuple[int, str], list[str]] = defaultdict(list)
    largest: list[tuple[int, str]] = []
    manifest_count = 0

    for name, path in tracked_files():
        size = path.stat().st_size
        top = name.partition("/")[0]
        roots[top]["files"] += 1
        roots[top]["bytes"] += size
        largest.append((size, name))
        manifest_count += (protected is not None and name in protected)
        # 只对达到门槛的文件计算 SHA256；相同大小不表示相同内容。
        if size >= min_duplicate_bytes:
            duplicates[(size, sha256_file(path))].append(name)

    duplicate_groups = []
    for (size, digest), paths in duplicates.items():
        if len(paths) < 2:
            continue
        duplicate_groups.append(
            {
                "size_each_bytes": size,
                "apparent_duplicate_bytes": size * (len(paths) - 1),
                "sha256": digest,
                "paths": paths,
                "protected_paths": [
                    p for p in paths
                    if (protected is not None and p in protected) or p.startswith(PROTECTED_PREFIXES)
                ],
                "note": "仅为相同内容提示，不等于文件可删除；先核对引用与完整性清单。",
            }
        )
    duplicate_groups.sort(
        key=lambda item: item["apparent_duplicate_bytes"], reverse=True
    )
    largest.sort(reverse=True)
    sorted_roots = dict(sorted(
        roots.items(), key=lambda pair: pair[1]["bytes"], reverse=True
    ))
    return {
        "scope": "当前工作树中存在的 Git 已跟踪文件；不是 Git 历史仓库体积",
        "read_only": True,
        "total_files": len(largest),
        "total_bytes": sum(v["bytes"] for v in roots.values()),
        "legacy_manifest_available": protected is not None,
        "manifest_pinned_files": manifest_count if protected is not None else None,
        "by_top_level": sorted_roots,
        "largest_files": [
            {"path": name, "size_bytes": size}
            for size, name in largest[:limit]
        ],
        "duplicate_groups": duplicate_groups[:limit],
        "duplicate_groups_total": len(duplicate_groups),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--top", type=int, default=12, help="最多显示多少项")
    parser.add_argument(
        "--min-duplicate-kb", type=int, default=128,
        help="参与重复内容哈希检测的最小文件体积（KiB）",
    )
    parser.add_argument("--json", action="store_true", help="输出 JSON 到标准输出")
    args = parser.parse_args()
    if args.top <= 0 or args.min_duplicate_kb < 0:
        parser.error("--top 必须大于 0；--min-duplicate-kb 不能为负数")
    report = build_report(args.top, args.min_duplicate_kb * 1024)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return
    print(f"已跟踪文件：{report['total_files']} 个")
    print(f"当前文件合计：{report['total_bytes'] / (1024**2):.2f} MiB")
    if report["legacy_manifest_available"]:
        print(f"被 final_v2 完整性清单引用：{report['manifest_pinned_files']} 个")
    else:
        print("历史图包 manifest 已归档到备份分支；当前 main 不执行旧包锁定路径检查")
    print("\n目录体积：")
    for name, info in report["by_top_level"].items():
        print(f"  {name:24s} {info['files']:4d} 个  {info['bytes'] / (1024**2):8.2f} MiB")
    print("\n最大文件：")
    for item in report["largest_files"]:
        print(f"  {item['size_bytes'] / (1024**2):8.2f} MiB  {item['path']}")
    print(f"\n重复内容组（满足大小门槛）：{report['duplicate_groups_total']} 组")
    for group in report["duplicate_groups"]:
        print(f"  单文件 {group['size_each_bytes'] / (1024**2):.2f} MiB")
        for path in group["paths"]:
            pin = " [需保护]" if path in group["protected_paths"] else ""
            print(f"    {path}{pin}")
    print("\n仅供审查：本脚本不会删除文件，也不会判断任何文件可安全删除。")


if __name__ == "__main__":
    main()
