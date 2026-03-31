# 🤖 Auto-Anuvaad

> **Vision-to-Hinglish Automation Engine** > *Translating physical Hindi records into structured Hinglish data with 99% accuracy using Gemini 1.5 Flash.*

---

## 📌 The Problem
Manual data entry from handwritten Hindi documents into digital spreadsheets is:
1. **Slow:** Humans average 30-40 WPM with high mental fatigue.
2. **Error-Prone:** Phonetic transliteration (Hindi -> Hinglish) varies between individuals.
3. **Inconsistent:** Maintaining Excel formatting while switching between physical and digital media is difficult.

**Auto-Anuvaad** solves this by using Multimodal LLMs to handle the heavy lifting of reading, transliterating, and injecting data.

---

## ✨ Key Features
- **Intelligent Transliteration:** Converts Devanagari script to Roman-script Hinglish (e.g., `नमस्ते` → `Namaste`) while preserving context.
- **Header Mapping:** Automatically maps Hindi topics in the JPG to English headers in the CSV/Sheet.
- **Human-in-the-Loop (HITL):** A built-in terminal verification step allows users to "Check & Correct" before the data is committed.
- **Dual Export Modes:**
    - **CSV Mode:** Fast, batch-processing of local images into a `.csv` file.
    - **Live Injection:** Direct typing into an already-open browser tab via Playwright CDP.

---

## 🛠️ Tech Stack
- **Language:** Python 3.10+
- **OCR/LLM:** Google Gemini 1.5 Flash (Vision)
- **Automation:** Playwright (CDP Mode)
- **Data Handling:** Python `csv` module & `pandas`

---

## 🚀 Setup & Installation

### 1. Configure Your Environment
Create a `.env` file in the root directory:
```env
GEMINI_API_KEY=your_google_ai_studio_key
IMAGE_DIR=./inbox
OUTPUT_FILE=master_data.csv