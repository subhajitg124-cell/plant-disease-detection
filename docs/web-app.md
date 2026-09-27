# Leaf Screening Website

## Run the leaf screening website

The repository includes a browser-based upload experience in `app.py`. It uses a public PlantVillage Vision Transformer for screening and the repository's agricultural knowledge base for follow-up guidance. On first launch, Transformers downloads the model files from Hugging Face and caches them locally; the model is about 86 million parameters, so allow time and disk space for the initial download. No API key is required.

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements-web.txt
streamlit run app.py
```

On macOS or Linux, activate the environment with `source .venv/bin/activate` and then run the same install and launch commands. If you want to choose another compatible Hugging Face image-classification checkpoint, set `PLANT_DISEASE_MODEL` to its repository ID before launching.

### What the screening result means

- Upload a close, well-lit image of one leaf. The selected checkpoint was trained on PlantVillage's 38 classes across 14 crops, with detached leaves and controlled backgrounds. It is not a whole-tree or field-canopy detector, and it may be wrong on field photos or plants outside those classes.
- The image overlay is a last-layer Vision Transformer attention estimate. It highlights image regions that influenced classification; it does not segment, measure, or prove the location of a lesion.
- The displayed model score is not a calibrated probability. Low-scoring matches are withheld from treatment guidance.
- Management suggestions come from this repository's knowledge base and linked agricultural sources. Confirm the diagnosis with a local agricultural extension specialist before applying pesticides or making irreversible crop decisions; follow local product labels and regulations.
- The app keeps the uploaded photo in memory for the current request and does not save it. The model downloads from Hugging Face on first run. Review the [model card](https://huggingface.co/kimcomehome/plantvillage-vit-leaf-disease) and its CC BY-SA 3.0 license before redistributing model-backed deployments.

### Hosting

The app can be deployed to Streamlit Community Cloud by pointing the deployment at this repository and setting the entry file to `app.py`; configure the app to install `requirements-web.txt`. The first request will download the model, so the host needs outbound access to Hugging Face and enough memory for PyTorch plus the model. This is an interactive screening prototype, not a validated diagnostic device.

