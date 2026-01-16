import requests
import json
import base64
import io
from PIL import Image
import matplotlib
# Macでのエラー回避のため、バックエンドを指定（GUIなしでも動くように設定後、表示）
matplotlib.use('TkAgg') 
import matplotlib.pyplot as plt
import math

# サーバーの設定
API_URL = "http://192.168.11.65:30080/search_hybrid"

def search_and_display(query_text):
    payload = {
        "hybrid_text_query": "",
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
        "return_images": True, # 画像を要求
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
        hits = result.get("hits", [])
        
        if not hits:
            print("❌ 検索結果が見つかりませんでした。")
            return

        print(f"✅ {len(hits)} 件ヒットしました。")

        # --- デバッグ情報: 最初の1件のデータを分析 ---
        print("\n--- [DEBUG INFO: 最初のデータの構造確認] ---")
        first_hit = hits[0]
        print(f"File Name: {first_hit.get('source', {}).get('name')}")
        print(f"Available Keys: {list(first_hit.keys())}")
        print(f"Thumbnail Exists Flag: {first_hit.get('thumbnail_exists')}")
        
        image_data_len = len(first_hit.get("image", "")) if first_hit.get("image") else 0
        print(f"Image Data Length: {image_data_len} bytes")
        print("----------------------------------------\n")
        # ---------------------------------------------

        cols = 5
        rows = math.ceil(len(hits) / cols)
        plt.figure(figsize=(15, 3 * rows))
        plt.suptitle(f"Search Result: '{query_text}'", fontsize=16)

        for i, hit in enumerate(hits):
            b64_image = hit.get("image")
            file_name = hit.get("source", {}).get("name", "Unknown")
            score = hit.get("score", 0)

            ax = plt.subplot(rows, cols, i + 1)
            
            if b64_image:
                try:
                    image_data = base64.b64decode(b64_image)
                    image = Image.open(io.BytesIO(image_data))
                    ax.imshow(image)
                except Exception as e:
                    ax.text(0.5, 0.5, "Decode Error", ha='center', va='center')
                    print(f"⚠️ {file_name}: 画像デコードエラー ({e})")
            else:
                # 画像データがない場合の理由を表示
                ax.text(0.5, 0.5, "No Image Data\n(Server didn't send it)", ha='center', va='center')
                # デバッグ用にログを出す
                # print(f"⚠️ {file_name}: 画像データがレスポンスに含まれていません")

            ax.set_title(f"{file_name}\nScore: {score:.2f}", fontsize=9)
            ax.axis('off')

        plt.tight_layout()
        plt.show()

    except Exception as e:
        print(f"⚠️ エラーが発生しました: {e}")

if __name__ == "__main__":
    # Macのエラー回避のおまじない
    try:
        matplotlib.use('TkAgg')
    except:
        pass

    user_input = input("\n検索したい言葉を入力してください (例: red car): ")
    if user_input:
        search_and_display(user_input)