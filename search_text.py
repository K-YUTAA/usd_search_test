import requests
import json
import base64
import io
import math
import sys
import subprocess
import platform
import os
from PIL import Image

import matplotlib

matplotlib.use('Agg') 
import matplotlib.pyplot as plt

# サーバーの設定
API_URL = "http://192.168.11.65:30080/search"
API_BASIC_AUTH = "omniverse:tsukuverse"
BLACKLIST_FILE = os.path.join(os.path.dirname(__file__), "search_blacklist.json")


def _normalize_asset_url(asset_url: str) -> str:
    if not asset_url:
        return ""
    normalized = asset_url.strip()
    if normalized.startswith("http://"):
        normalized = normalized.replace("http://", "omniverse://")
    if normalized.startswith("/"):
        normalized = f"omniverse://192.168.11.65{normalized}"
    return normalized


def _split_asset_filename(asset_url: str):
    if not asset_url:
        return "", ""
    basename = asset_url.split("?")[0].split("/")[-1]
    if "." in basename:
        name, ext = basename.rsplit(".", 1)
    else:
        name, ext = basename, ""
    return name.lower(), ext.lower()


def _build_identity_key(asset_url: str, size_bytes):
    name, ext = _split_asset_filename(asset_url)
    if not name and not ext:
        return None
    size_token = str(size_bytes) if isinstance(size_bytes, int) else "unknown"
    if ext:
        return f"{name}.{ext}|{size_token}"
    return f"{name}|{size_token}"


def _extract_size(data):
    if not isinstance(data, dict):
        return None
    for key in ("size", "file_size", "fileSize", "bytes", "file_size_bytes", "content_length"):
        if key in data:
            try:
                value = int(data.get(key))
                return value if value >= 0 else None
            except (TypeError, ValueError):
                continue
    nested = data.get("stat")
    if isinstance(nested, dict):
        for key in ("size", "file_size", "bytes"):
            if key in nested:
                try:
                    value = int(nested.get(key))
                    return value if value >= 0 else None
                except (TypeError, ValueError):
                    continue
    return None


def _load_blacklist():
    if not os.path.exists(BLACKLIST_FILE):
        return set(), set()
    try:
        with open(BLACKLIST_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        urls = set(data.get("urls", []))
        keys = set(data.get("keys", []))
        return urls, keys
    except Exception as exc:
        print(f"[Warning] Failed to load blacklist: {exc}")
        return set(), set()


def _save_blacklist(urls, keys):
    payload = {"urls": sorted(list(urls)), "keys": sorted(list(keys))}
    try:
        with open(BLACKLIST_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
    except Exception as exc:
        print(f"[Warning] Failed to save blacklist: {exc}")

def open_file(filepath):
    """OSごとのデフォルトビューワーでファイルを開く"""
    if platform.system() == 'Darwin':       # macOS
        subprocess.call(('open', filepath))
    elif platform.system() == 'Windows':    # Windows
        os.startfile(filepath)
    else:                                   # Linux variants
        subprocess.call(('xdg-open', filepath))

def search_and_display(query_text):
    try:
        print(f"検索中: '{query_text}' ...")

        target_valid = 10
        limit = 10
        max_limit = 200
        prev_total_hits = -1
        filtered = []
        total_hits = 0
        blacklist_urls, blacklist_keys = _load_blacklist()

        while True:
            payload = {
                "vector_queries": [
                    {
                        "field_name": "clip-embedding.embedding",
                        "query_type": "text",
                        "query": query_text
                    }
                ],
                "return_metadata": True,
                "return_images": True,
                "limit": limit,
                "file_extension_include": "usd,usda,usdc,usdz",
                "file_extension_exclude": "png,jpg,jpeg"
            }

            auth_user, auth_pass = API_BASIC_AUTH.split(":", 1)
            response = requests.post(
                API_URL,
                headers={"Content-Type": "application/json", "accept": "application/json"},
                auth=(auth_user, auth_pass),
                data=json.dumps(payload),
                timeout=30
            )
            response.raise_for_status()

            result = response.json()
            if isinstance(result, list):
                hits = result
            else:
                if "results" in result:
                    hits = result.get("results", [])
                elif isinstance(result.get("hits"), dict) and "hits" in result["hits"]:
                    hits = result["hits"]["hits"]
                else:
                    hits = result.get("hits", [])

            total_hits = len(hits)
            if total_hits == 0:
                print("検索結果が見つかりませんでした。")
                return

            candidates = []
            for hit in hits:
                data = hit.get("_source", hit) if isinstance(hit, dict) else {}
                size_val = _extract_size(data) or _extract_size(hit)
                url = None
                for key in ("url", "uri", "path", "file_path", "asset_path"):
                    if isinstance(data, dict) and key in data:
                        candidate = data.get(key)
                        if isinstance(candidate, str) and candidate:
                            url = candidate
                            break
                if not url:
                    continue
                normalized_url = _normalize_asset_url(url)
                identity_key = _build_identity_key(normalized_url, size_val)
                score = hit.get("score", 0)
                b64_image = hit.get("image") or data.get("image")
                candidates.append(
                    {
                        "url": normalized_url,
                        "key": identity_key,
                        "size": size_val,
                        "score": score,
                        "image": b64_image,
                    }
                )

            filtered = []
            seen_keys = set()
            for cand in candidates:
                if cand["url"] in blacklist_urls:
                    continue
                if cand["key"] and cand["key"] in blacklist_keys:
                    continue
                if cand["key"] and cand["key"] in seen_keys:
                    continue
                if cand["key"]:
                    seen_keys.add(cand["key"])
                filtered.append(cand)

            if len(filtered) >= target_valid:
                break
            if limit >= max_limit:
                print(f"有効候補が {len(filtered)} 件のため、limit上限({max_limit})で終了します。")
                break
            if total_hits <= prev_total_hits:
                print("追加候補が増えないため再検索を終了します。")
                break
            prev_total_hits = total_hits
            limit = min(limit * 2, max_limit)
            print(f"有効候補が {len(filtered)} 件のため、limit={limit} で再検索します...")

        if not filtered:
            print("ブラックリスト/重複除外後に候補がありません。")
            return

        print(
            f"{total_hits} 件ヒット → 有効候補 {len(filtered)} 件。Matplotlibで画像を生成中..."
        )

        # --- Matplotlibによる画像生成 ---
        cols = 5
        rows = math.ceil(len(filtered) / cols)
        if rows == 0: rows = 1
        
        # 図のサイズ設定
        fig = plt.figure(figsize=(15, 4 * rows))
        fig.suptitle(f"Search Result: '{query_text}'", fontsize=16)

        for i, hit in enumerate(filtered):
            b64_image = hit.get("image")
            file_url = hit.get("url", "Unknown")
            file_name = file_url.split("/")[-1] if file_url != "Unknown" else "Unknown"
            score = hit.get("score", 0)

            ax = plt.subplot(rows, cols, i + 1)
            
            if b64_image:
                try:
                    image_data = base64.b64decode(b64_image)
                    image = Image.open(io.BytesIO(image_data))
                    ax.imshow(image)
                except Exception as e:
                    ax.text(0.5, 0.5, "Image Error", ha='center', va='center')
            else:
                ax.text(0.5, 0.5, "No Image", ha='center', va='center')

            ax.set_title(f"{file_name}\nScore: {score:.2f}", fontsize=9)
            ax.axis('off')

        plt.tight_layout()
        
        # --- ファイルに保存して開く (Tkinterを使わない表示方法) ---
        output_filename = "search_result_view.png"
        plt.savefig(output_filename, dpi=100)
        plt.close(fig) # メモリ解放

        print(f"画像を生成しました: {output_filename}")
        open_file(output_filename)

        # --- ブラックリスト追加 ---
        print("\n候補一覧:")
        for i, cand in enumerate(filtered):
            print(f"[{i}] {cand['url']} (key={cand['key']})")

        user_select = input("ブラックリストに追加する番号（カンマ区切り、空でスキップ）: ").strip()
        if user_select:
            try:
                indices = {int(x.strip()) for x in user_select.split(",") if x.strip().isdigit()}
            except ValueError:
                indices = set()
            for idx in indices:
                if 0 <= idx < len(filtered):
                    cand = filtered[idx]
                    blacklist_urls.add(cand["url"])
                    if cand["key"]:
                        blacklist_keys.add(cand["key"])
            _save_blacklist(blacklist_urls, blacklist_keys)
            print("ブラックリストを更新しました。")

    except Exception as e:
        print(f"エラーが発生しました: {e}")

if __name__ == "__main__":
    while True:
        try:
            user_input = input("\n検索したい言葉を入力してください (終了するには 'q'): ")
            if user_input.lower() == 'q':
                break
            if user_input.strip() == "":
                continue
                
            search_and_display(user_input)
        except KeyboardInterrupt:
            print("\n終了します")
            break