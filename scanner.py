import sys
import os
import json
import subprocess
import httpx

def run_gitleaks(target_dir="."):
    """Runs gitleaks on the target repository and captures JSON findings."""
    report_path = "/tmp/gitleaks_report.json"
    
    cmd = [
        "gitleaks", "detect",
        "--source", target_dir,
        "--report-format", "json",
        "--report-path", report_path,
        "--no-git" if not os.path.exists(os.path.join(target_dir, ".git")) else "--log-level", "info"
    ]
    
    cmd = [arg for arg in cmd if arg]
    
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    if os.path.exists(report_path):
        with open(report_path, "r") as f:
            try:
                findings = json.load(f)
                os.remove(report_path)
                return findings
            except json.JSONDecodeError:
                return []
    return []

def generate_fix_plan(findings):
    """Sends findings to the local FastAPI Gateway for a structured remediation plan."""
    summary_items = []
    for f in findings:
        summary_items.append(
            f"- Rule: {f.get('RuleID')}\n  File: {f.get('File')}\n  Commit: {f.get('Commit')}\n  Secret Match: {f.get('Secret')[:10]}***"
        )
    
    prompt = (
        "You are a cybersecurity expert. The following leaked secrets were found in a repository:\n\n"
        + "\n".join(summary_items) +
        "\n\nFor each finding, give a concise fix plan:\n"
        "1. Which dashboard/provider to visit to immediately revoke/rotate the key.\n"
        "2. How to replace it with an environment variable.\n"
        "3. Reminder to never rely on git commit deletion alone."
    )
    
    print("\n[AI REMEDIATION PLAN]")
    print("-" * 50)
    
    # Stream remediation plan safely passing params to handle URL encoding
    with httpx.stream("POST", "http://127.0.0.1:8000/stream", params={"prompt": prompt}, timeout=None) as response:
        for chunk in response.iter_text():
            if chunk.startswith("data: "):
                try:
                    payload = json.loads(chunk[6:])
                    print(payload.get("text", ""), end="", flush=True)
                except Exception:
                    pass
    print("\n" + "-" * 50)

def main():
    target = sys.argv[1] if len(sys.argv) > 1 else "."
    print(f"Scanning target repository: '{target}'...")
    
    findings = run_gitleaks(target)
    
    if not findings:
        print("✅ No leaked secrets or keys detected!")
        return
        
    print(f"⚠️ DETECTED {len(findings)} LEAKED SECRET(S):\n")
    for f in findings:
        print(f" • File: {f.get('File')} (Line {f.get('StartLine')})")
        print(f"   Key Type: {f.get('RuleID')}")
        print(f"   Commit: {f.get('Commit')}\n")
        
    generate_fix_plan(findings)

if __name__ == "__main__":
    main()
