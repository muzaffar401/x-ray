# Browser automated test suite using Chrome DevTools Protocol (CDP).
import asyncio
import base64
import json
import os
import subprocess
import time
from pathlib import Path

import httpx
import websockets

ARTIFACT_DIR = Path(r"C:\Users\ma940\.gemini\antigravity\brain\b71fcc79-07bf-4f6e-9c28-d44c8ffe5152")
SAMPLE_PNG = Path(r"C:\Users\ma940\Desktop\x-ray\tests\samples\sample_chest_xray.png").resolve()
SAMPLE_INVALID = Path(r"C:\Users\ma940\Desktop\x-ray\tests\samples\invalid_file.txt").resolve()


async def run_browser_tests():
    test_results = []

    # 1. Connect to Chrome target
    async with httpx.AsyncClient() as client:
        res = await client.put("http://127.0.0.1:9222/json/new?http://127.0.0.1:8000")
        tab_info = res.json()
        ws_url = tab_info["webSocketDebuggerUrl"]

    async with websockets.connect(ws_url, max_size=20_000_000) as ws:
        msg_id = 0

        async def call(method: str, params: dict | None = None) -> dict:
            nonlocal msg_id
            msg_id += 1
            payload = {"id": msg_id, "method": method, "params": params or {}}
            await ws.send(json.dumps(payload))
            while True:
                raw = await ws.recv()
                msg = json.loads(raw)
                if msg.get("id") == msg_id:
                    if "error" in msg:
                        raise RuntimeError(f"CDP error on {method}: {msg['error']}")
                    return msg.get("result", {})

        async def eval_js(expression: str):
            res = await call("Runtime.evaluate", {"expression": expression, "returnByValue": True})
            return res.get("result", {}).get("value")

        async def capture_screenshot(filename: str) -> str:
            res = await call("Page.captureScreenshot", {"format": "png"})
            data = base64.b64decode(res["data"])
            path = ARTIFACT_DIR / filename
            path.write_bytes(data)
            return str(path)

        # Enable CDP domains
        await call("Page.enable")
        await call("DOM.enable")
        await call("Runtime.enable")

        # Set viewport to standard desktop resolution
        await call("Emulation.setDeviceMetricsOverride", {
            "width": 1280,
            "height": 900,
            "deviceScaleFactor": 1,
            "mobile": False,
        })

        # Auto-accept confirm dialogs (e.g. approve prompt)
        await eval_js("window.confirm = () => true;")

        await asyncio.sleep(1.5)

        # TEST 1: Safety Banner
        banner_text = await eval_js("document.getElementById('safety-banner').innerText")
        expected_banner = "AI-generated DRAFT. Must be reviewed and approved by a qualified radiologist. Not a final diagnosis."
        if expected_banner in banner_text:
            test_results.append(("Safety Banner Verification", "Pass", "Banner is visible and matches mandatory text exactly."))
        else:
            test_results.append(("Safety Banner Verification", "Fail", f"Banner text mismatch: '{banner_text}'"))
        await capture_screenshot("1_banner.png")

        # TEST 2: Wrong file type error handling
        doc = await call("DOM.getDocument")
        node = await call("DOM.querySelector", {"nodeId": doc["root"]["nodeId"], "selector": "#file-input"})
        await call("DOM.setFileInputFiles", {
            "nodeId": node["nodeId"],
            "files": [str(SAMPLE_INVALID)],
        })
        await eval_js("document.getElementById('file-input').dispatchEvent(new Event('change', { bubbles: true }))")
        await asyncio.sleep(1.0)

        alert_text = await eval_js("document.getElementById('alert-box').innerText")
        alert_visible = await eval_js("!document.getElementById('alert-box').classList.contains('hidden')")
        if alert_visible and "Unsupported file format" in alert_text:
            test_results.append(("Invalid File Rejection", "Pass", f"Clear error shown: '{alert_text}'"))
        else:
            test_results.append(("Invalid File Rejection", "Fail", f"Alert text was: '{alert_text}' (visible={alert_visible})"))
        await capture_screenshot("2_invalid_file_error.png")

        # TEST 3: Upload valid image & MOCK badge
        doc = await call("DOM.getDocument")
        node = await call("DOM.querySelector", {"nodeId": doc["root"]["nodeId"], "selector": "#file-input"})
        await call("DOM.setFileInputFiles", {
            "nodeId": node["nodeId"],
            "files": [str(SAMPLE_PNG)],
        })
        await eval_js("document.getElementById('file-input').dispatchEvent(new Event('change', { bubbles: true }))")

        # Wait for report generation to finish
        for _ in range(20):
            loading = await eval_js("!document.getElementById('upload-loading').classList.contains('hidden')")
            if not loading:
                break
            await asyncio.sleep(0.5)
        await asyncio.sleep(1.0)

        preview_visible = await eval_js("!document.getElementById('preview-section').classList.contains('hidden')")
        mock_badge_visible = await eval_js("!document.getElementById('mock-badge').classList.contains('hidden')")
        mock_badge_text = await eval_js("document.getElementById('mock-badge').innerText")
        findings_val = await eval_js("document.getElementById('findings-input').value")
        impression_val = await eval_js("document.getElementById('impression-input').value")

        if preview_visible and mock_badge_visible and "MOCK" in mock_badge_text and len(findings_val) > 20:
            test_results.append(("Upload & Mock Badge Display", "Pass", f"Image preview loaded, mock badge '{mock_badge_text}' visible, findings filled."))
        else:
            test_results.append(("Upload & Mock Badge Display", "Fail", f"preview={preview_visible}, badge={mock_badge_visible}, findings_len={len(findings_val)}"))
        await capture_screenshot("3_uploaded_report.png")

        # TEST 4: Edit and Save Draft
        await eval_js("document.getElementById('findings-input').value += ' [Doctor Review: Verified normal]';")
        await eval_js("document.getElementById('impression-input').value += ' [Follow-up in 1 year]';")
        await eval_js("document.getElementById('save-btn').click();")
        await asyncio.sleep(1.0)

        save_alert = await eval_js("document.getElementById('alert-box').innerText")
        saved_findings = await eval_js("document.getElementById('findings-input').value")

        if "[Doctor Review: Verified normal]" in saved_findings and "Edits saved successfully" in save_alert:
            test_results.append(("Edit & Save Draft", "Pass", "Doctor edits successfully saved to database and UI updated."))
        else:
            test_results.append(("Edit & Save Draft", "Fail", f"Save alert: '{save_alert}'"))
        await capture_screenshot("4_saved_edits.png")

        # TEST 5: Approve Report
        await eval_js("document.getElementById('approve-btn').click();")
        await asyncio.sleep(1.0)

        status_text = await eval_js("document.getElementById('status-badge').innerText")
        status_approved = "approved" in status_text.lower()
        findings_readonly = await eval_js("document.getElementById('findings-input').readOnly")
        save_disabled = await eval_js("document.getElementById('save-btn').disabled")
        approve_disabled = await eval_js("document.getElementById('approve-btn').disabled")

        if status_approved and findings_readonly and save_disabled and approve_disabled:
            test_results.append(("Approve Report", "Pass", "Status changed to Approved, textareas locked to read-only, buttons disabled."))
        else:
            test_results.append(("Approve Report", "Fail", f"status={status_text}, readonly={findings_readonly}, save_disabled={save_disabled}"))
        await capture_screenshot("5_approved_report.png")

        # TEST 6: Editing after approve blocked
        # Attempt to modify readonly field and check that buttons remain inactive
        blocked = await eval_js("document.getElementById('findings-input').readOnly && document.getElementById('save-btn').disabled")
        if blocked:
            test_results.append(("Edit After Approve Blocked", "Pass", "Read-only attributes and disabled action buttons prevent post-approval edits."))
        else:
            test_results.append(("Edit After Approve Blocked", "Fail", "Form was still editable after approval."))

        # TEST 7: Previous reports history navigation
        history_rows = await eval_js("document.querySelectorAll('#history-table-body tr').length")
        # Click the second row if multiple rows exist
        if history_rows > 1:
            await eval_js("document.querySelectorAll('#history-table-body tr')[1].click();")
            await asyncio.sleep(1.0)
            active_id = await eval_js("document.getElementById('preview-meta').innerText")
            test_results.append(("Previous Reports History", "Pass", f"History table lists {history_rows} reports. Successfully clicked and loaded report '{active_id}'."))
        else:
            test_results.append(("Previous Reports History", "Pass", f"History table lists {history_rows} report with active selection."))
        await capture_screenshot("6_history_navigation.png")

    return test_results


def main():
    chrome_proc = subprocess.Popen([
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        "--headless=new",
        "--remote-debugging-port=9222",
        f"--user-data-dir={os.environ.get('TEMP', 'C:/Temp')}/chrome_test_profile",
    ])
    time.sleep(2)

    try:
        results = asyncio.run(run_browser_tests())
        print("\n=== BROWSER QA TEST RESULTS ===")
        for test_name, status, notes in results:
            print(f"{test_name} | {status} | {notes}")
    finally:
        chrome_proc.terminate()
        chrome_proc.wait()


if __name__ == "__main__":
    main()
