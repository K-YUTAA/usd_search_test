import requests
import json
import base64
import io
import math
import os
import sys
import subprocess
import platform
from PIL import Image

# --- Matplotlibの設定 (GUIエラー回避) ---
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

def encode_image_to_base64(image_path):
    """画像を読み込みAPI用のBase64形式に変換"""
    try:
        with open(image_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
        
        ext = image_path.lower().split('.')[-1]
        mime_type = "jpeg" if ext in ["jpg", "jpeg"] else "png"
        
        return f"data:image/{mime_type};base64,{encoded_string}"
    except Exception as e:
        print(f"❌ 画像の読み込みに失敗しました: {e}")
        return None

def search_by_image(image_path):
    base64_input = encode_image_to_base64(image_path)
    if not base64_input:
        return

    # 検索クエリ
    payload = {
        "image_similarity_search": [
            base64_input
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
        "limit": 10  # 修正箇所: 上位10件に変更しました
    }

    try:
        print(f"🔍 画像 '{os.path.basename(image_path)}' で類似アセットを検索中 (Top 10)...")
        
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
            print("❌ 類似するアセットは見つかりませんでした。")
            return

        print(f"✅ {total_hits} 件ヒットしました。画像を生成中...")

        # --- 結果の可視化 (Matplotlib) ---
        # 10件なので 5列 x 2行 で表示
        cols = 5
        rows = math.ceil(total_hits / cols)
        if rows == 0: rows = 1
        
        fig = plt.figure(figsize=(15, 3.5 * rows))
        fig.suptitle(f"Image Similarity Search: '{os.path.basename(image_path)}'", fontsize=16)

        for i, hit in enumerate(hits):
            b64_image = hit.get("image")
            file_path = hit.get("url", hit.get("source", {}).get("base_key", "Unknown"))
            file_name = file_path.split("/")[-1] if file_path != "Unknown" else "Unknown"
            score = hit.get("score", 0)

            ax = plt.subplot(rows, cols, i + 1)
            
            if b64_image:
                try:
                    image_data = base64.b64decode(b64_image)
                    image = Image.open(io.BytesIO(image_data))
                    ax.imshow(image)
                except Exception:
                    ax.text(0.5, 0.5, "Image Error", ha='center', va='center')
            else:
                ax.text(0.5, 0.5, "No Preview", ha='center', va='center')

            ax.set_title(f"{file_name}\nScore: {score:.2f}", fontsize=8)
            ax.axis('off')

        plt.tight_layout()
        
        output_filename = "image_search_top10.png"
        plt.savefig(output_filename, dpi=100)
        plt.close(fig)

        print(f"🖼️ 結果画像を生成しました: {output_filename}")
        open_file(output_filename)

    except Exception as e:
        print(f"⚠️ エラーが発生しました: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        input_path = sys.argv[1]
        search_by_image(input_path)
    else:
        while True:
            input_path = input("\n検索元の画像パスを入力してください (終了するには 'q'): ").strip()
            input_path = input_path.replace("'", "").replace('"', "")
            
            if input_path.lower() == 'q':
                break
            if input_path == "":
                continue
            
            if os.path.exists(input_path):
                search_by_image(input_path)
            else:
                print("⚠️ ファイルが存在しません。")