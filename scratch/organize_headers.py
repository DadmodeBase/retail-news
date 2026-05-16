import os
import datetime
import shutil

# 設定
PROJECT_ROOT = r"c:\Users\admin\Documents\Antigravity"
TEMP_DIR = os.path.join(PROJECT_ROOT, "temp_headers")
TARGET_DIR = os.path.join(PROJECT_ROOT, "assets", "headers")
START_DATE = datetime.date(2026, 5, 11)

def main():
    if not os.path.exists(TEMP_DIR):
        print(f"Error: {TEMP_DIR} does not exist.")
        return

    if not os.path.exists(TARGET_DIR):
        os.makedirs(TARGET_DIR)

    # 1.png から 80.png までをループ
    for i in range(1, 81):
        src_name = f"{i}.png"
        src_path = os.path.join(TEMP_DIR, src_name)
        
        if os.path.exists(src_path):
            # 日付を計算
            current_date = START_DATE + datetime.timedelta(days=i-1)
            dst_name = current_date.strftime("%m-%d.png")
            dst_path = os.path.join(TARGET_DIR, dst_name)
            
            print(f"Moving {src_name} -> {dst_name}")
            shutil.move(src_path, dst_path)
        else:
            print(f"Warning: {src_name} not found in {TEMP_DIR}")

    print("Done.")

if __name__ == "__main__":
    main()
