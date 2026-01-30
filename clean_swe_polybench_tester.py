"""
SWE-PolyBench Clean Automated Runner
- Scans generic range (default 0-300)
- SKIPS already completed tasks (checks predictions.jsonl)
- FILLS GAPS naturally by iterating sequentially
- AUTOMATES progression by watching for stable git diffs
"""

import os
import subprocess
import json
import time
import shutil
from colorama import Fore, Style, init
import argparse
import traceback
from threading import Thread
from pathlib import Path
from datasets import load_dataset
import sys
import hashlib

init(autoreset=True)

# ========================== CONFIGURATION ==========================

MAX_CLONE_RETRIES = 3
CLONE_TIMEOUT = 600
FETCH_TIMEOUT = 300
GIT_COMMAND_TIMEOUT = 60

# Automation Settings
STABILITY_TIMEOUT = 10  # Seconds the diff must be stable to be considered "done"
POLL_INTERVAL = 2       # Seconds between git diff checks

# ========================== UTILS ==========================

def run_git_command(cmd, cwd, timeout=GIT_COMMAND_TIMEOUT, capture_output=True):
    """Run git command with timeout."""
    try:
        if capture_output:
            result = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
                errors='replace'
            )
        else:
            result = subprocess.run(
                cmd,
                cwd=cwd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=timeout
            )
        return result
    except subprocess.TimeoutExpired:
        print(f"{Fore.YELLOW}⏱️  Git command timed out after {timeout}s{Style.RESET_ALL}")
        return None
    except Exception as e:
        print(f"{Fore.YELLOW}⚠️  Git command error: {e}{Style.RESET_ALL}")
        return None

def check_and_enable_longpaths():
    """Check and enable git long paths on Windows."""
    if sys.platform != "win32":
        return True
    try:
        result = subprocess.run(["git", "config", "--global", "core.longpaths"], capture_output=True, text=True, timeout=5)
        if result.stdout.strip().lower() == "true":
            return True
        print(f"{Fore.YELLOW}⚙️  Enabling Windows long path support in Git...{Style.RESET_ALL}")
        subprocess.run(["git", "config", "--global", "core.longpaths", "true"], timeout=10)
        print(f"{Fore.GREEN}✓ Git long paths enabled{Style.RESET_ALL}")
        return True
    except Exception as e:
        print(f"{Fore.YELLOW}⚠️  Could not enable long paths: {e}{Style.RESET_ALL}")
        return False

def copy_to_clipboard(text):
    """Robust clipboard copy."""
    try:
        # Try Windows clip command first
        process = subprocess.Popen(['clip'], stdin=subprocess.PIPE, shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
        process.communicate(input=text.encode('utf-16le'), timeout=2)
        return True
    except:
        try:
            import pyperclip
            pyperclip.copy(text)
            return True
        except:
            return False

def safe_rmtree(path):
    """Safely remove directory with retries."""
    if not os.path.exists(path):
        return True
    for attempt in range(3):
        try:
            shutil.rmtree(path, ignore_errors=True)
            time.sleep(0.5)
            if not os.path.exists(path):
                return True
        except:
            time.sleep(1)
    return False

# ========================== GIT LOGIC ==========================

def reset_git_repo(repo_path, base_commit):
    """Reset git repository to base commit."""
    try:
        # Check if commit exists
        result = run_git_command(["git", "cat-file", "-e", base_commit], repo_path, timeout=10)
        
        if result is None or result.returncode != 0:
            print(f"{Fore.CYAN}  → Fetching commit history...{Style.RESET_ALL}")
            run_git_command(["git", "fetch", "origin", base_commit], repo_path, timeout=FETCH_TIMEOUT)
            
            result = run_git_command(["git", "cat-file", "-e", base_commit], repo_path, timeout=10)
            if result is None or result.returncode != 0:
                print(f"{Fore.CYAN}  → Unshallowing repository...{Style.RESET_ALL}")
                run_git_command(["git", "fetch", "--unshallow"], repo_path, timeout=FETCH_TIMEOUT)
        
        # Checkout base commit
        result = run_git_command(["git", "checkout", "-f", base_commit], repo_path)
        if result is None or result.returncode != 0:
            print(f"{Fore.RED}Failed to checkout {base_commit}{Style.RESET_ALL}")
            return False
        
        # Clean untracked files
        run_git_command(["git", "clean", "-fd"], repo_path)
        return True
        
    except Exception as e:
        print(f"{Fore.RED}Git reset error: {e}{Style.RESET_ALL}")
        return False

def clone_repo(repo, base_commit, target_folder):
    """Clone repository with Windows support."""
    if os.path.exists(target_folder):
        if os.path.exists(os.path.join(target_folder, ".git")):
            if reset_git_repo(target_folder, base_commit):
                return True
        safe_rmtree(target_folder)
    
    clone_url = f"https://github.com/{repo}.git"
    print(f"{Fore.CYAN}  → Cloning: {clone_url}{Style.RESET_ALL}")
    
    clone_cmd = ["git", "clone"]
    if sys.platform == "win32":
        clone_cmd.extend(["-c", "core.longpaths=true"])
    clone_cmd.extend(["--depth", "50", "--no-single-branch", clone_url, target_folder])
    
    result = run_git_command(clone_cmd, os.getcwd(), timeout=CLONE_TIMEOUT, capture_output=False)
    
    if result and result.returncode == 0:
        # Fetch base commit
        run_git_command(["git", "fetch", "origin", base_commit], target_folder, timeout=FETCH_TIMEOUT)
        return reset_git_repo(target_folder, base_commit)
    
    return False

def get_git_diff(repo_path):
    """Get git diff of changes."""
    try:
        run_git_command(["git", "add", "-A"], repo_path)
        result = run_git_command(["git", "diff", "--cached"], repo_path)
        diff = result.stdout if result else ""
        run_git_command(["git", "reset", "HEAD"], repo_path) # Unstage
        return diff
    except:
        return ""

# ========================== AUTOMATION LOGIC ==========================

def wait_for_stable_changes(repo_path):
    """
    Watches the repo for changes.
    Returns the diff content when changes have been made and are stable for STABILITY_TIMEOUT.
    """
    print(f"{Fore.CYAN}⌛ Waiting for changes (Polling every {POLL_INTERVAL}s, Stable for {STABILITY_TIMEOUT}s)...{Style.RESET_ALL}")
    
    last_diff = ""
    stable_start_time = None
    
    while True:
        try:
            current_diff = get_git_diff(repo_path)
            
            # If we have changes
            if current_diff.strip():
                if current_diff != last_diff:
                    # Changes are new or modified, reset timer
                    print(f"{Fore.YELLOW}🔸 Changes detected/updated... waiting for stability{Style.RESET_ALL}")
                    last_diff = current_diff
                    stable_start_time = time.time()
                else:
                    # Changes are same as last check
                    elapsed = time.time() - stable_start_time
                    if elapsed >= STABILITY_TIMEOUT:
                        print(f"{Fore.GREEN}✓ Changes stable for {elapsed:.1f}s. Proceeding.{Style.RESET_ALL}")
                        return current_diff
            else:
                # No changes yet
                if last_diff:
                     print(f"{Fore.RED}🔸 Changes reverted! Waiting for new changes...{Style.RESET_ALL}")
                     last_diff = ""
                     stable_start_time = None
            
            time.sleep(POLL_INTERVAL)
            
        except KeyboardInterrupt:
            raise
        except Exception as e:
            print(f"{Fore.RED}Error in watcher: {e}{Style.RESET_ALL}")
            time.sleep(POLL_INTERVAL)

# ========================== MAIN ==========================

def get_completed_instances(predictions_file):
    completed = set()
    if not os.path.exists(predictions_file):
        return completed
    with open(predictions_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                try:
                    entry = json.loads(line)
                    if entry.get("instance_id"):
                        completed.add(entry["instance_id"])
                except:
                    pass
    return completed

def format_problem(problem_data):
    p = f"Instance ID: {problem_data['instance_id']}\nRepository: {problem_data['repo']}\n"
    p += f"PROBLEM STATEMENT:\n{problem_data['problem_statement']}"
    if problem_data.get("hints_text"):
        p += f"\n\nHINTS:\n{problem_data['hints_text']}"
    return p

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model-name', default='cora')
    parser.add_argument('--start', type=int, default=0)
    parser.add_argument('--end', type=int, default=300)
    args = parser.parse_args()
    
    WORKING_FOLDER = "swe_polybench_workspace"
    PREDICTIONS_FILE = "predictions.jsonl"
    os.makedirs(WORKING_FOLDER, exist_ok=True)
    
    print(f"{Fore.CYAN}🤖 SWE-PolyBench Clean Runner ({args.start}-{args.end}){Style.RESET_ALL}")
    
    # Load Data
    try:
        print("Loading dataset...")
        dataset = load_dataset("AmazonScience/SWE-PolyBench", split="test")
        full_dataset = [dict(item) for item in dataset]
    except Exception as e:
        print(f"Failed to load dataset: {e}")
        return

    check_and_enable_longpaths()
    
    # Loop
    for i in range(args.start, args.end + 1):
        if i >= len(full_dataset):
            break
            
        problem = full_dataset[i]
        instance_id = problem["instance_id"]
        
        # 1. Check if done
        completed_ids = get_completed_instances(PREDICTIONS_FILE)
        if instance_id in completed_ids:
            print(f"{Fore.GREEN}⏭️  {i}: {instance_id} (Skipping - Already Done){Style.RESET_ALL}")
            continue
            
        # 2. Process
        print(f"\n{Fore.YELLOW}{'='*60}")
        print(f"🚀 Processing {i}: {instance_id}")
        print(f"{'='*60}{Style.RESET_ALL}")
        
        repo_path = os.path.join(WORKING_FOLDER, instance_id.replace("/", "_"))
        
        # Clone
        if not clone_repo(problem["repo"], problem["base_commit"], repo_path):
            print(f"{Fore.RED}❌ Clone/Reset failed. Skipping.{Style.RESET_ALL}")
            continue
            
        # Clipboard
        prompt = format_problem(problem)
        copy_to_clipboard(prompt)
        with open("current_problem.txt", "w", encoding="utf-8") as f:
            f.write(prompt)
            
        print(f"{Fore.GREEN}✓ Prompt copied & saved to current_problem.txt{Style.RESET_ALL}")
        print(f"{Fore.CYAN}👉 ACTION REQUIRED:{Style.RESET_ALL}")
        print("   1. Paste patch content below (end with 'EOF' on new line)")
        print("   2. OR type 'REPO' to scan local changes in 'swe_polybench_workspace'")
        print("   3. OR type 'SKIP' to move to next")
        
        # Manual Input Loop
        final_diff = None
        while True:
            try:
                first_line = input(f"\n{Fore.YELLOW}Input > {Style.RESET_ALL}")
                
                if first_line.strip().upper() == 'SKIP':
                    print("Skipping...")
                    break
                    
                if first_line.strip().upper() == 'REPO':
                    diff = get_git_diff(repo_path)
                    if diff.strip():
                        print(f"{Fore.GREEN}✓ Found changes ({len(diff)} bytes).{Style.RESET_ALL}")
                        if input("Save this? (y/n) > ").lower() == 'y':
                            final_diff = diff
                            break
                    else:
                        print(f"{Fore.RED}❌ No changes found in {repo_path}{Style.RESET_ALL}")
                    continue
                
                # Assume paste mode
                lines = [first_line]
                while True:
                    line = input()
                    if line.strip() == 'EOF':
                        break
                    lines.append(line)
                final_diff = '\n'.join(lines)
                break
                
            except KeyboardInterrupt:
                print("\nInterrupted.")
                return

        if final_diff is not None:
            # Save
            prediction = {
                "instance_id": instance_id,
                "model_name_or_path": args.model_name,
                "model_patch": final_diff
            }
            with open(PREDICTIONS_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(prediction) + "\n")
            
            print(f"{Fore.GREEN}💾 Saved result for {instance_id}{Style.RESET_ALL}")
            
        # Cleanup
        reset_git_repo(repo_path, problem["base_commit"])

if __name__ == "__main__":
    main()
