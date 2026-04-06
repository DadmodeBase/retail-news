import os
import datetime
from PIL import Image, ImageDraw, ImageFont

def generate_header_image(date_str, output_path):
    print(f"ヘッダー画像を生成しています: {output_path}")
    base_image_path = os.path.join(os.getcwd(), "note", "resources", "header_base.png")
    
    if not os.path.exists(base_image_path):
        # ベース画像がない場合は、水色の単色背景を作成
        img = Image.new('RGB', (1920, 1006), color=(235, 245, 255))
        print("Base image not found, using solid color.")
    else:
        img = Image.open(base_image_path)
        print("Base image loaded.")
    
    draw = ImageDraw.Draw(img)
    
    # フォント設定（Meiryo UI）
    font_path = "C:\\Windows\\Fonts\\meiryo.ttc"
    try:
        font_main = ImageFont.truetype(font_path, 120, index=0) # Meiryo UI Regular
        font_date = ImageFont.truetype(font_path, 80, index=0)
        print("Meiryo font loaded.")
    except Exception as e:
        print(f"Failed to load font: {e}")
        font_main = ImageFont.load_default()
        font_date = ImageFont.load_default()
    
    # 日付の描画 (3月29日 など)
    try:
        date_text = date_str.split("-")[-2].lstrip("0") + "月" + date_str.split("-")[-1].lstrip("0") + "日"
    except:
        date_text = date_str
        
    main_text = "日刊 リテールニュース"
    w, h = 1920, 1006
    
    # 日付を描画
    date_bbox = draw.textbbox((0, 0), date_text, font=font_date)
    draw.text(((w - (date_bbox[2] - date_bbox[0])) / 2, h/2 - 150), date_text, font=font_date, fill=(40, 60, 80))
    
    # メインタイトルを描画
    main_bbox = draw.textbbox((0, 0), main_text, font=font_main)
    draw.text(((w - (main_bbox[2] - main_bbox[0])) / 2, h/2 - 20), main_text, font=font_main, fill=(0, 80, 150))
    
    img.save(output_path)
    print(f"Image saved to {output_path}")

if __name__ == "__main__":
    generate_header_image("2026-04-05", "test_header.png")
