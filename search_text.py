import requests
import json
import base64
import io
import math
import sys
import subprocess
import platform
from PIL import Image

import matplotlib

matplotlib.use('Agg') 
import matplotlib.pyplot as plt

# サーバーの設定
API_URL = "http://192.168.11.65:30080/search"

def open_file(filepath):
    """OSごとのデフォルトビューワーでファイルを開く"""
    if platform.system() == 'Darwin':       # macOS
        subprocess.call(('open', filepath))
    elif platform.system() == 'Windows':    # Windows
        os.startfile(filepath)
    else:                                   # Linux variants
        subprocess.call(('xdg-open', filepath))

def search_and_display(query_text):
    # 検索クエリ (成功した設定)
    payload = {
        "vector_queries": [
            {
                "field_name": "clip-embedding.embedding",
                "query_type": "text",
                "query": query_text
            }
        ],
        "filters": {
            "and": [
                {
                    "field": "ext",
                    "value": ["usd", "usda", "usdc", "usdz"],
                    "relation": "in"
                }
            ]
        },
        "return_metadata": True,
        "return_images": True,
        "limit": 10
    }

    try:
        print(f"🔍 '{query_text}' を検索中...")
        
        response = requests.post(
            API_URL, 
            headers={"Content-Type": "application/json", "accept": "application/json"},
            data=json.dumps(payload)
        )
        response.raise_for_status()
        
        result = response.json()
        if isinstance(result, list):
             hits = result
        else:
             hits = result.get("hits", [])
        
        total_hits = len(hits)
        if total_hits == 0:
            print("❌ 検索結果が見つかりませんでした。")
            return

        print(f"✅ {total_hits} 件ヒットしました。Matplotlibで画像を生成中...")

        # --- Matplotlibによる画像生成 ---
        cols = 5
        rows = math.ceil(total_hits / cols)
        if rows == 0: rows = 1
        
        # 図のサイズ設定
        fig = plt.figure(figsize=(15, 4 * rows))
        fig.suptitle(f"Search Result: '{query_text}'", fontsize=16)

        for i, hit in enumerate(hits):
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

        print(f"🖼️ 画像を生成しました: {output_filename}")
        open_file(output_filename)

    except Exception as e:
        print(f"⚠️ エラーが発生しました: {e}")

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