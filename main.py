import os
import json
import time
import glob
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv
import google.generativeai as genai
from playwright.sync_api import sync_playwright

def download_google_sheet_as_csv(page, temp_csv_path="temp_sheet.csv"):
    """
    Automates the 'File > Download > Comma Separated Values (.csv)' in Google Sheets.
    """
    print("Downloading current Google Sheet as CSV for a precise sync...")
    try:
        # Click "File" menu (Usually the first top-level menu)
        page.get_by_text("File", exact=True).click()
        time.sleep(1)
        
        # Hover over "Download"
        page.get_by_text("Download", exact=True).hover()
        time.sleep(1)
        
        # Click "Comma Separated Values (.csv)"
        with page.expect_download() as download_info:
            page.get_by_text("Comma Separated Values (.csv)", exact=True).click()
        
        download = download_info.value
        download.save_as(temp_csv_path)
        print(f"Downloaded sheet to {temp_csv_path}")
        return temp_csv_path
    except Exception as e:
        print(f"FAILED to download sheet as CSV: {e}")
        return None

def sync_data_and_save_excel(temp_csv, target_file, search_key, new_value):
    """
    Reads the downloaded CSV, finds the target row/column, and updates master_data.xlsx.
    """
    if not temp_csv or not os.path.exists(temp_csv):
        return

    # Load the full CSV
    df = pd.read_csv(temp_csv)
    
    # Identify the target column for the "Hinglish Value"
    # Heuristic: Find first column that is largely empty or has 'Hinglish' in it
    target_col = None
    for col in df.columns:
        if "Hinglish" in str(col) or "Value" in str(col):
            target_col = col
            break
    if not target_col:
        target_col = df.columns[-1] # Fallback to last column

    # Find the row index where any column contains the search_key (fuzzy match)
    row_idx = None
    for idx, row in df.iterrows():
        if any(str(search_key).strip().lower() in str(val).strip().lower() for val in row.values):
            row_idx = idx
            break
            
    if row_idx is not None:
        print(f"Found search key '{search_key}' at row {row_idx}. Updating column '{target_col}'...")
        df.at[row_idx, target_col] = new_value
    else:
        print(f"Warning: Could not find '{search_key}' in the downloaded sheet. Appending a new row.")
        new_row = {df.columns[0]: search_key, target_col: new_value}
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

    # Save to Master Excel
    excel_path = "master_data.xlsx"
    sheet_name = Path(target_file).stem[:31]
    
    if os.path.exists(excel_path):
        with pd.ExcelWriter(excel_path, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
            df.to_excel(writer, sheet_name=sheet_name, index=False)
    else:
        with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name=sheet_name, index=False)
    print(f"Success: Updated {excel_path} with the exact structure and new data on sheet '{sheet_name}'.")

def run_auto_anuvaad():
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: GEMINI_API_KEY is not set.")
        return

    genai.configure(api_key=api_key)
    try:
        available_models = [m.name for m in genai.list_models() if 'flash' in m.name.lower()]
        model_name = available_models[0].replace('models/', '') if available_models else 'gemini-1.5-flash'
        print(f"Model: {model_name}")
    except:
        model_name = 'gemini-1.5-flash'
    model = genai.GenerativeModel(model_name)
    
    inbox_dir = "./inbox"
    output_dir = "./output"
    os.makedirs(inbox_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)
    
    image_files = []
    for ext in ["*.jpg", "*.jpeg", "*.pdf"]:
        image_files.extend(glob.glob(os.path.join(inbox_dir, ext)))
        
    if not image_files:
        print(f"No files found in {inbox_dir}.")
        return

    cdp_port = os.getenv('CDP_PORT', '9222')
    cdp_url = f"http://localhost:{cdp_port}"
    print(f"DEBUG: Connecting to browser via CDP at {cdp_url}...", flush=True)
    try:
        with sync_playwright() as p:
            print("DEBUG: Initializing browser connection...", flush=True)
            browser = p.chromium.connect_over_cdp(cdp_url)
            print("DEBUG: Connection successful, getting first page...", flush=True)
            if not browser.contexts: raise Exception("No browser contexts found!")
            if not browser.contexts[0].pages: raise Exception("No pages open in Brave!")
            
            page = browser.contexts[0].pages[0]
            print(f"Connected: {page.title()}", flush=True)
            page.bring_to_front()

            print(f"DEBUG: Starting processing loop for {len(image_files)} files...", flush=True)
            for img_path in image_files:
                abs_path = os.path.abspath(img_path)
                print(f"\n[STEP 1] Starting file: {img_path} (Full: {abs_path})", flush=True)
                try:
                    mime_type = "application/pdf" if img_path.lower().endswith(".pdf") else "image/jpeg"
                    print(f"[STEP 2] Uploading to Gemini (MIME: {mime_type})...", flush=True)
                    myfile = genai.upload_file(abs_path, mime_type=mime_type)
                    
                    print(f"[STEP 3] Uploading done. Server ID: {myfile.name}. Waiting for 'READY' state...", flush=True)
                    while myfile.state.name == "PROCESSING":
                        print(".", end="", flush=True)
                        time.sleep(2)
                        myfile = genai.get_file(myfile.name)
                    
                    if myfile.state.name == "FAILED":
                        raise Exception(f"File failed to process on server: {myfile.state}")
                    print(f"\n[STEP 4] File is READY. Sending analysis request...", flush=True)
                    
                    prompt = "Process this handwritten Hindi table into JSON: {\"rows\": [{\"search_key\": \"...\", \"data_to_enter\": \"...\"}]}"
                    response = model.generate_content([myfile, prompt], generation_config={"temperature": 0.1})
                    print("[STEP 5] AI Analysis received.", flush=True)
                    
                    clean_text = response.text.strip()
                    if "```json" in clean_text: clean_text = clean_text.split("```json")[1].split("```")[0].strip()
                    elif "```" in clean_text: clean_text = clean_text.split("```")[1].split("```")[0].strip()

                    output_file_path = os.path.join(output_dir, f"{os.path.basename(img_path)}_output.json")
                    with open(output_file_path, "w", encoding="utf-8") as f: f.write(clean_text)

                    data = json.loads(clean_text)
                    if isinstance(data, list):
                        rows = data
                    else:
                        rows = data.get("rows", [])
                    
                    for row in rows:
                        search_key, value = row.get("search_key"), row.get("data_to_enter")
                        print(f"\n[REVIEW] Search: '{search_key}' | Value: '{value}'")
                        confirm = input("Confirm sync and browser entry? (y/n): ")
                        
                        if confirm.lower() == 'y':
                            # 1. Sync from Browser Download
                            temp_csv = download_google_sheet_as_csv(page)
                            sync_data_and_save_excel(temp_csv, img_path, search_key, value)

                            # 2. Inject into Chrome
                            print("Injecting into Brave...")
                            page.keyboard.press("Control+f")
                            time.sleep(1.0)
                            page.keyboard.type(search_key)
                            time.sleep(1.5)
                            page.keyboard.press("Enter")
                            time.sleep(0.5)
                            page.keyboard.press("Escape")
                            time.sleep(0.5)
                            page.keyboard.press("Tab")
                            time.sleep(0.5)
                            page.keyboard.press("Delete")
                            page.keyboard.press("Backspace")
                            for char in str(value):
                                page.keyboard.type(char)
                                time.sleep(0.1)
                            page.keyboard.press("Enter")
                            print("Done.")
                        else:
                            print("Skipped.")
                except Exception as ex:
                    print(f"Error {img_path}: {ex}")
    except Exception as e:
        print(f"Fatal error: {e}")

if __name__ == "__main__":
    run_auto_anuvaad()
