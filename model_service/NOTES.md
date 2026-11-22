# CXR-LLaVA Model Loading and Inference Notes

Official Source:
- GitHub: [https://github.com/ECOFRI/CXR_LLaVA](https://github.com/ECOFRI/CXR_LLaVA)
- Hugging Face: [https://huggingface.co/ECOFRI/CXR-LLAVA-v2](https://huggingface.co/ECOFRI/CXR-LLAVA-v2)
- Paper: "CXR-LLaVA: Multimodal Large Language Model for Interpreting Chest X-ray Images" (European Radiology / arXiv:2310.18341)

---

## 1. Model Identifier
- Model Card on Hugging Face: `ECOFRI/CXR-LLAVA-v2`
- Architecture: LLaVA-based framework with a custom-trained Vision Transformer (`ViT-L/16`, 512x512 resolution, 1-channel grayscale) paired with LLaMA-2-7B-Chat via a multimodal projector.

---

## 2. Hardware and Environment Requirements
- **GPU Requirement:** Dedicated NVIDIA CUDA GPU with **> 14GB VRAM** (e.g. Kaggle T4/P100 with 16GB VRAM, or Google Colab T4 with 15GB VRAM).
- **Inference on CPU:** Not recommended due to model size and memory overhead.

---

## 3. Official Loading Steps

The model requires `trust_remote_code=True` because custom architecture and helper methods are defined in the Hugging Face repository files:

```python
import torch
from transformers import AutoModel
from PIL import Image

# 1. Load model weights and custom pipeline
model = AutoModel.from_pretrained("ECOFRI/CXR-LLAVA-v2", trust_remote_code=True)

# 2. Move to GPU device
device = "cuda" if torch.cuda.is_available() else "cpu"
model = model.to(device)
model.eval()
```

---

## 4. Official Inference Steps

### Method A: Direct Radiologic Report (Findings)
The official repository provides a built-in convenience method:

```python
cxr_image = Image.open("path/to/chest_xray.png")

# Generates the radiologic findings
report_text = model.write_radiologic_report(cxr_image)
print(report_text)
```

### Method B: Custom Chat / Prompt Template
The official README provides a structured chat interface via `generate_cxr_repsonse` (note: exact spelling in official repo has `repsonse`):

```python
chat = [
    {
        "role": "system",
        "content": "You are a helpful radiologist. Try to interpret chest x ray image and answer to the question that user provides."
    },
    {
        "role": "user",
        "content": "<image>\nWrite a radiologic report on the given chest radiograph, including information about atelectasis, cardiomegaly, consolidation, pulmonary edema, pleural effusion, and pneumothorax.\n"
    }
]

response = model.generate_cxr_repsonse(
    chat=chat,
    image=cxr_image,
    temperature=0.2,
    top_p=0.8
)
print(response)
```

---

## 5. Report Structure & Impression Limitation

- **Findings:** CXR-LLaVA natively generates a descriptive narrative of findings covering common thoracic abnormalities (cardiomegaly, pleural effusion, consolidation, atelectasis, etc.).
- **Impression:** The official CXR-LLaVA repository and model card **do not provide an Impression generator or separate impression field**.
- **Implementation Decision:** The model service outputs the generated text as `findings` and sets `impression: ""` with a clear TODO comment explaining this upstream limitation.

---

## 6. Licensing and Compliance Notice

- **Model License:** Creative Commons Attribution-NonCommercial (CC BY-NC 4.0).
- **Base LLM License:** Subject to Meta's LLaMA-2 Community License Agreement. Users must accept LLaMA-2 terms before accessing or deploying.
- **Commercial Use:** Strictly non-commercial. Any commercial deployment is prohibited by the model authors without explicit commercial licensing.
- **Safety Disclaimer:** The model is strictly for research and evaluation purposes. AI-generated drafts must be reviewed and approved by a qualified radiologist and cannot be used as a final diagnosis or for direct clinical decisions.
