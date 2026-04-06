# resize_images.py
from PIL import Image
import os
import glob
import io

# 設定（ここを変えれば調整できます）
MAX_SIZE = 800           # 長辺の最大ピクセル数
TARGET_KB = 500          # 目標ファイルサイズ（KB）
INPUT_DIR = "target_images"
OUTPUT_DIR = "resized_images"

def compress_to_target(img, target_kb, min_quality=20):
    """画像を目標サイズ以下になるまで圧縮する"""
    quality = 95
    while quality >= min_quality:
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=quality)
        size_kb = buffer.tell() / 1024
        if size_kb <= target_kb:
            return buffer.getvalue(), quality, size_kb
        quality -= 5
    # 最低品質でも目標に届かない場合はそのまま返す
    return buffer.getvalue(), quality, size_kb

# フォルダ作成
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

# 画像をリストアップ
files = glob.glob(os.path.join(INPUT_DIR, "*.jpg"))
print(f"{len(files)}枚の画像が見つかりました。処理を開始します...")

# 1枚ずつ処理
for file_path in files:
    try:
        img = Image.open(file_path)
        # RGB変換（透過画像対策）
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        # アスペクト比を維持してリサイズ
        img.thumbnail((MAX_SIZE, MAX_SIZE), Image.Resampling.LANCZOS)
        
        # 圧縮して保存
        data, final_quality, final_kb = compress_to_target(img, TARGET_KB)
        basename = os.path.basename(file_path)
        save_path = os.path.join(OUTPUT_DIR, basename)
        with open(save_path, "wb") as f:
            f.write(data)
        print(f"完了: {basename} ({final_kb:.0f}KB, 品質{final_quality})")
    except Exception as e:
        print(f"エラー: {file_path} - {e}")

print("全ての処理が完了しました！")
