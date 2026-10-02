# Plant Disease Model Training and Evaluation

## 1. Prepare and inspect the image folders

The CNN reads color images from:

    data/raw/PlantVillage/<original_label>/

Class labels and IDs come from:

    data/metadata/plantvillage_class_mapping.csv

The current extracted dataset contains 31 of the 38 mapped classes. The trainer records that subset in the checkpoint; absent classes are not advertised as trained classes. Add the seven missing class folders before training if the project must cover all 38 diseases.

To create reproducible CSV manifests of the real image paths, run from the project root:

    .\.venv\Scripts\python.exe scripts/prepare_dataset.py

## 2. Train and evaluate on real images

Make sure the project environment has NumPy and Pillow, and install a PyTorch build selected for Windows and your GPU from https://pytorch.org/get-started/locally/. Then run from the project root:

    .\.venv\Scripts\python.exe -m pip install numpy pillow
    .\.venv\Scripts\python.exe -m src.vision.train --epochs 15 --batch-size 32

The trainer makes a deterministic, stratified 70/15/15 train, validation, and test split. It saves the best validation checkpoint to models/plant_disease_cnn.pth and writes metrics to reports/training_report.json. Test accuracy is calculated from the held-out images; it is not inferred from training accuracy or generated sample images.

For an independent evaluation of the same held-out image split, run:

    .\.venv\Scripts\python.exe scripts/evaluate_known_dataset.py

This writes reports/plantvillage_test_report.json and reports/plantvillage_test_report.md. The report includes per-class accuracy and the classes absent from the image set.

## 3. Try the web application

Start the server:

    .\.venv\Scripts\python.exe server.py

Open http://localhost:8000 and upload a real leaf photograph. Check http://localhost:8000/api/health for checkpoint and trained-class status. Sample illustrations are previews only and are not model predictions.

If no real-image checkpoint is available, the API reports that the model is not ready rather than returning a heuristic or hard-coded diagnosis.

## 4. Automated code checks

Run the unit and integration suite from the project root:

    .\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"

These checks cover application code. Use the held-out image report above to assess classification performance.