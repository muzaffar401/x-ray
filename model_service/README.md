# CXR-LLaVA Model Service

A standalone FastAPI microservice for running **CXR-LLaVA** (`ECOFRI/CXR-LLAVA-v2`) on a GPU-enabled environment (such as **Kaggle** or **Google Colab**).

---

## ⚠️ Important Safety Notice

**AI-generated DRAFT. Must be reviewed and approved by a qualified radiologist. Not a final diagnosis.**

Never use this service for direct clinical decisions or real patient data.

---

## ⚖️ License Notice

- **Model License:** Creative Commons NonCommercial ([CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/)).
- **Base LLM License:** Built on Meta's LLaMA-2-7B-Chat. Users must accept the [Meta LLaMA-2 License](https://ai.meta.com/resources/models-and-libraries/llama-downloads/).
- **Commercial Use:** This model is strictly non-commercial. Any commercial application is strictly prohibited without explicit licensing from the authors.

---

## 🖥️ Hardware Requirements

- **GPU Required:** NVIDIA GPU with at least **14 GB VRAM** (e.g. Kaggle T4 or P100 16GB, Google Colab T4 15GB).
- Do not attempt to run on standard CPU instances; loading will fail or run out of memory.

---

## 🚀 Running on Kaggle (Step-by-Step)

1. **Create a Kaggle Notebook:**
   - Go to [kaggle.com](https://www.kaggle.com) -> **Create** -> **New Notebook**.
   - Under **Notebook Options** (right sidebar):
     - **Accelerator**: Select **GPU T4 x2** or **GPU P100**.
     - **Internet**: Switch to **Internet On**.

2. **Upload or Clone Code:**
   In the first cell, clone or write the files:
   ```bash
   !git clone https://github.com/<your-repo>/x-ray.git
   %cd x-ray/model_service
   ```

3. **Install Dependencies:**
   ```bash
   !pip install -r requirements.txt
   !pip install pyngrok uvicorn
   ```

4. **Set Environment Variables:**
   ```python
   import os
   os.environ["MODEL_SERVICE_KEY"] = "your-long-secure-secret-key"
   ```

5. **Expose and Run FastAPI:**
   ```python
   from pyngrok import ngrok
   import uvicorn
   import threading

   # Connect ngrok tunnel to port 8000 (enter your ngrok authtoken if prompted)
   # ngrok.set_auth_token("YOUR_NGROK_TOKEN")
   public_url = ngrok.connect(8000)
   print(f"Model service running publicly at: {public_url}")

   # Run server in thread or directly
   !uvicorn server:app --host 0.0.0.0 --port 8000
   ```

---

## 🚀 Running on Google Colab (Step-by-Step)

1. Open [colab.research.google.com](https://colab.research.google.com) and create a notebook.
2. In the menu: **Runtime** -> **Change runtime type** -> select **T4 GPU**.
3. Install dependencies:
   ```bash
   !pip install -r requirements.txt
   !pip install pyngrok uvicorn
   ```
4. Set secret key:
   ```python
   import os
   os.environ["MODEL_SERVICE_KEY"] = "your-long-secure-secret-key"
   ```
5. Launch Uvicorn with ngrok:
   ```python
   from pyngrok import ngrok
   tunnel = ngrok.connect(8000)
   print("Public URL:", tunnel.public_url)
   !uvicorn server:app --host 0.0.0.0 --port 8000
   ```

---

## 📡 API Endpoints

### 1. Health Check
- **`GET /health`**
- Returns:
  ```json
  {
    "status": "ok",
    "model_loaded": true,
    "device": "cuda",
    "is_mock": false,
    "disclaimer": "AI-generated DRAFT. Must be reviewed and approved by a qualified radiologist. Not a final diagnosis."
  }
  ```

### 2. Generate Draft Report
- **`POST /generate`**
- **Header:** `X-API-Key: <your MODEL_SERVICE_KEY>`
- **Body:** `multipart/form-data` with `file: <png/jpeg image>`
- Returns:
  ```json
  {
    "findings": "Clear lungs bilaterally. Normal cardiac silhouette. No pleural effusion or pneumothorax.",
    "impression": "",
    "model_name": "ECOFRI/CXR-LLAVA-v2",
    "disclaimer": "AI-generated DRAFT. Must be reviewed and approved by a qualified radiologist. Not a final diagnosis."
  }
  ```
