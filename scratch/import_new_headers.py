import os
import datetime
import shutil

PROJECT_ROOT = r"c:\Users\admin\Documents\Antigravity"
SOURCE_DIR = os.path.join(PROJECT_ROOT, "日刊リテールニュース ヘッダー画像")
TARGET_DIR = os.path.join(PROJECT_ROOT, "assets", "headers")
START_DATE = datetime.date(2026, 10, 18)

def main():
    if not os.path.exists(SOURCE_DIR):
        print(f"Error: {SOURCE_DIR} does not exist.")
        return

    if not os.path.exists(TARGET_DIR):
        os.makedirs(TARGET_DIR)

    processed_count = 0
    end_date = None

    for i in range(1, 81):
        src_name = f"{i}.png"
        src_path = os.path.join(SOURCE_DIR, src_name)
        
        if os.path.exists(src_path):
            current_date = START_DATE + datetime.timedelta(days=i-1)
            dst_name = current_date.strftime("%m-%d.png")
            dst_path = os.path.join(TARGET_DIR, dst_name)
            
            shutil.copy2(src_path, dst_path)
            processed_count += 1
            end_date = current_date
            print(f"Copied: {src_name} -> {dst_name}")
        else:
            print(f"Warning: {src_name} not found in {SOURCE_DIR}")

    print(f"\nDone! Processed {processed_count} files.")
    if end_date:
        print(f"Headers covered from {START_DATE.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}.")

if __name__ == "__main__":
    main()
