import os
import sys
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.preprocessing.dataset_split import DatasetSplitter


def generate_sample_images(output_dir: str = "data/raw/sample_leaves", count: int = 5):
    os.makedirs(output_dir, exist_ok=True)
    generated_paths = []

    for i in range(count):
        img_arr = np.zeros((256, 256, 3), dtype=np.uint8)
        img_arr[:, :, 0] = np.random.randint(20, 60, (256, 256))
        img_arr[:, :, 1] = np.random.randint(100, 220, (256, 256))
        img_arr[:, :, 2] = np.random.randint(10, 50, (256, 256))
        
        if i % 2 == 0:
            cx, cy = np.random.randint(50, 200), np.random.randint(50, 200)
            rr, cc = np.ogrid[:256, :256]
            mask = (rr - cx) ** 2 + (cc - cy) ** 2 <= 30 ** 2
            img_arr[mask, 0] = 160
            img_arr[mask, 1] = 120
            img_arr[mask, 2] = 20

        img = Image.fromarray(img_arr)
        file_path = os.path.join(output_dir, f"sample_plant_{i+1}.jpg")
        img.save(file_path)
        generated_paths.append(file_path)

    non_plant_arr = np.random.randint(100, 150, (256, 256, 3), dtype=np.uint8)
    non_plant_path = os.path.join(output_dir, "sample_not_a_plant.jpg")
    Image.fromarray(non_plant_arr).save(non_plant_path)
    generated_paths.append(non_plant_path)

    return generated_paths


def main():
    print("=" * 60)
    print("Initializing Plant Disease Dataset Environment...")
    print("=" * 60)

    splitter = DatasetSplitter(
        class_mapping_path="data/metadata/plantvillage_class_mapping.csv",
        output_dir="data/processed"
    )
    splits = splitter.create_stratified_split(samples_per_class=100)
    saved_files = splitter.save_splits(splits)

    for split_name, path in saved_files.items():
        print(f"Generated split '{split_name}': {path} ({len(splits[split_name])} records)")

    sample_paths = generate_sample_images()
    print(f"Created {len(sample_paths)} test sample images in 'data/raw/sample_leaves/'")
    print("=" * 60)
    print("Dataset preparation complete.")


if __name__ == "__main__":
    main()
