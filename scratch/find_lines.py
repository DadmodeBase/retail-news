with open("skills/neta_gatherer/neta_gatherer.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if "def generate_contents" in line:
        print(f"Start: {i+1}")
        for j in range(i, len(lines)):
            if "def " in lines[j] and j > i:
                print(f"End: {j}")
                break
        else:
            print(f"End: {len(lines)}")
        break
