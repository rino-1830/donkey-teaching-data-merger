#!/usr/bin/env python3
"""Donkeycar データセットを結合してブレーキの新要素を追加するスクリプト。

使い方
------
```
python add_brake.py --src <src_dir> --dst <dst_dir>
```
参数は両方ともDonkeycarのデータセットディレクトリを指定する。スクリプトは
``dst``側の最終レコード終了番号に続けて、``src``側のレコードを追加する。
その際、``user/brake``がない場合は0.0で埋める。
"""

import argparse
import importlib.util
import json
import sys
import types
from pathlib import Path
from typing import List, Tuple

import numpy as np
from PIL import Image


def _import_donkeycar_parts():
    """donkeycarのパーツをロードする。

    Returns:
        type: ``Tub`` クラス
    """
    sys.modules["donkeycar"] = types.ModuleType("donkeycar")
    sys.modules["donkeycar.parts"] = types.ModuleType("donkeycar.parts")

    base = Path(__file__).resolve().parents[1] / "donkeycar/parts"

    spec_ds = importlib.util.spec_from_file_location(
        "donkeycar.parts.datastore_v2", base / "datastore_v2.py"
    )
    ds = importlib.util.module_from_spec(spec_ds)
    sys.modules["donkeycar.parts.datastore_v2"] = ds
    spec_ds.loader.exec_module(ds)

    spec_tub = importlib.util.spec_from_file_location(
        "donkeycar.parts.tub_v2", base / "tub_v2.py"
    )
    tub = importlib.util.module_from_spec(spec_tub)
    sys.modules["donkeycar.parts.tub_v2"] = tub
    spec_tub.loader.exec_module(tub)
    return tub.Tub


def _load_manifest(path: Path) -> List:
    """manifest.jsonを読み込む。

    Args:
        path: manifest.jsonのパス

    Returns:
        list: ファイル内の5行を解析したリスト
    """
    with path.open() as fp:
        return [json.loads(fp.readline()) for _ in range(5)]


def _write_manifest(path: Path, lines: List) -> None:
    """manifest.jsonを書き出す。

    Args:
        path: 書き込み先
        lines: JSONオブジェクトのリスト
    """
    with path.open("w") as fp:
        for entry in lines:
            fp.write(json.dumps(entry, sort_keys=True))
            fp.write("\n")


def _ensure_brake(path: Path) -> Tuple[List, List, int]:
    """manifestに``user/brake``を追加して必要な情報を返す。

    Args:
        path: manifest.jsonのパス

    Returns:
        Tuple[List, List, int]: 更新後のinputs、types、max_len
    """
    lines = _load_manifest(path)
    inputs, types, metadata, man_meta, cat_meta = lines
    changed = False
    if "user/brake" not in inputs:
        idx = (
            inputs.index("user/throttle") + 1
            if "user/throttle" in inputs
            else len(inputs)
        )
        inputs.insert(idx, "user/brake")
        types.insert(idx, "float")
        changed = True
    if changed:
        lines[0] = inputs
        lines[1] = types
        _write_manifest(path, lines)
    return inputs, types, cat_meta.get("max_len", 1000)


def convert(src_dir: str, dst_dir: str) -> None:
    """``src``側のデータを``dst``に追加する。

    Args:
        src_dir: brakeのないデータのパス
        dst_dir: brakeがあるデータのパス
    """
    Tub = _import_donkeycar_parts()

    src = Path(src_dir)
    dst = Path(dst_dir)

    inputs, types, max_len = _ensure_brake(dst / "manifest.json")
    tub = Tub(
        dst_dir, inputs=inputs, types=types, max_catalog_len=max_len, read_only=False
    )

    src_manifest = _load_manifest(src / "manifest.json")
    cat_meta = src_manifest[4]

    for cat in cat_meta["paths"]:
        with (src / cat).open() as fp:
            for line in fp:
                rec = json.loads(line)
                rec.setdefault("user/brake", 1.0)
                data = {}
                for key in inputs:
                    if key == "cam/image_array":
                        img_path = src / "images" / rec[key]
                        with Image.open(img_path) as img:
                            data[key] = np.asarray(img)
                    else:
                        data[key] = rec.get(key)
                tub.write_record(data)
    tub.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="brake無データを結合する")
    parser.add_argument("--src", required=True, help="変換元ディレクトリ")
    parser.add_argument("--dst", required=True, help="結合先ディレクトリ")
    args = parser.parse_args()
    convert(args.src, args.dst)
