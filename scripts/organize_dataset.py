import os
import csv
import shutil

def organize_dataset():
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    pv_dir = os.path.join(base_dir, "data", "raw", "PlantVillage")
    samples_dir = os.path.join(base_dir, "data", "raw", "sample_leaves")
    csv_path = os.path.join(base_dir, "data", "metadata", "plantvillage_class_mapping.csv")

    os.makedirs(pv_dir, exist_ok=True)
    os.makedirs(samples_dir, exist_ok=True)

    if not os.path.exists(csv_path):
        print(f"Error: {csv_path} not found.")
        return

    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            original = row["original_label"].strip().strip('"')
            class_folder = os.path.join(pv_dir, original)
            os.makedirs(class_folder, exist_ok=True)
            
            canonical = row["canonical_id"]
            sample_candidates = [
                os.path.join(samples_dir, f"{canonical}_sample.jpg"),
                os.path.join(samples_dir, f"{canonical}.jpg"),
                os.path.join(samples_dir, f"{canonical}_1.jpg")
            ]
            for candidate in sample_candidates:
                if os.path.exists(candidate):
                    target = os.path.join(class_folder, f"{canonical}_01.jpg")
                    shutil.copy2(candidate, target)
                    print(f"Added sample to {original}/")
                    break

    print("PlantVillage class folders and sample images synchronized.")

if __name__ == "__main__":
    organize_dataset()
