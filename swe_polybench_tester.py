"""
SWE-PolyBench AI Runner v2.4
Windows-compatible with automatic long path support and enhanced error handling
UPDATED: Separate folders per instance ID + Auto-resume without prompt
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
from datetime import datetime
import sys

init(autoreset=True)

# ========================== CONFIGURATION ==========================

MAX_CLONE_RETRIES = 3
CLONE_TIMEOUT = 600  # 10 minutes for large repos
FETCH_TIMEOUT = 300  # 5 minutes
GIT_COMMAND_TIMEOUT = 60  # 1 minute for regular commands

# ========================== WINDOWS LONG PATH SUPPORT ==========================

def check_and_enable_longpaths():
    """Check and enable git long paths on Windows."""
    if sys.platform != "win32":
        return True
    
    try:
        # Check current setting
        result = subprocess.run(
            ["git", "config", "--global", "core.longpaths"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.stdout.strip().lower() == "true":
            return True
        
        # Enable it
        print(f"{Fore.YELLOW}⚙️  Enabling Windows long path support in Git...{Style.RESET_ALL}")
        subprocess.run(
            ["git", "config", "--global", "core.longpaths", "true"],
            timeout=10
        )
        print(f"{Fore.GREEN}✓ Git long paths enabled{Style.RESET_ALL}")
        return True
        
    except Exception as e:
        print(f"{Fore.YELLOW}⚠️  Could not enable long paths: {e}{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}   Please run manually: git config --global core.longpaths true{Style.RESET_ALL}")
        return False

# ========================== STATE MANAGEMENT ==========================

class StateManager:
    """Manages the state of the evaluation session"""
    
    def __init__(self, state_file="swe_polybench_state.json"):
        self.state_file = state_file
        self.state = self.load_state()
    
    def load_state(self):
        """Load state from file"""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {
            "last_instance_id": None,
            "last_instance_index": -1,
            "session_start": None,
            "total_solved": 0,
            "failed_instances": [],
            "cloning_errors": [],
            "range": {"start": None, "end": None}
        }
    
    def save_state(self):
        """Save current state to file"""
        try:
            with open(self.state_file, 'w') as f:
                json.dump(self.state, f, indent=2)
        except:
            pass
    
    def update_progress(self, instance_id, instance_index):
        """Update current progress"""
        self.state["last_instance_id"] = instance_id
        self.state["last_instance_index"] = instance_index
        self.save_state()
    
    def mark_solved(self):
        """Mark an instance as solved"""
        self.state["total_solved"] += 1
        self.save_state()
    
    def mark_failed(self, instance_id, reason):
        """Mark an instance as failed"""
        self.state["failed_instances"].append({
            "instance_id": instance_id,
            "reason": reason,
            "timestamp": datetime.now().isoformat()
        })
        self.save_state()
    
    def mark_clone_error(self, repo, instance_id, error):
        """Track cloning errors separately"""
        self.state["cloning_errors"].append({
            "repo": repo,
            "instance_id": instance_id,
            "error": str(error),
            "timestamp": datetime.now().isoformat()
        })
        self.save_state()
    
    def set_range(self, start, end):
        """Set the working range"""
        self.state["range"]["start"] = start
        self.state["range"]["end"] = end
        if self.state["session_start"] is None:
            self.state["session_start"] = datetime.now().isoformat()
        self.save_state()
    
    def can_resume(self):
        """Check if we can resume from a previous session"""
        return self.state["last_instance_index"] >= 0

# ========================== CLIPBOARD ==========================

def copy_to_clipboard_windows(text):
    """Copy text to clipboard using native Windows command."""
    try:
        process = subprocess.Popen(
            ['clip'],
            stdin=subprocess.PIPE,
            shell=True,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        process.communicate(input=text.encode('utf-16le'), timeout=2)
        return True
    except:
        return False


def copy_to_clipboard_with_timeout(text, timeout=3):
    """Try to copy to clipboard with timeout."""
    if copy_to_clipboard_windows(text):
        return True
    
    try:
        import pyperclip
        result = [False]
        
        def copy_task():
            try:
                pyperclip.copy(text)
                result[0] = True
            except:
                pass
        
        thread = Thread(target=copy_task, daemon=True)
        thread.start()
        thread.join(timeout=timeout)
        
        return result[0]
    except:
        return False

# ========================== FILE OPERATIONS ==========================

def safe_rmtree(path):
    """Safely remove directory with retries."""
    if not os.path.exists(path):
        return True
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            shutil.rmtree(path, ignore_errors=True)
            time.sleep(0.5)
            if not os.path.exists(path):
                return True
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(1)
            else:
                print(f"{Fore.YELLOW}Warning: Could not fully remove {path}: {e}{Style.RESET_ALL}")
                return False
    return True

# ========================== GIT OPERATIONS ==========================

def run_git_command(cmd, cwd, timeout=GIT_COMMAND_TIMEOUT, capture_output=True):
    """Run git command with timeout and better error handling."""
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


def reset_git_repo(repo_path, base_commit):
    """Reset git repository to base commit."""
    try:
        print(f"{Fore.CYAN}  → Resetting to base commit...{Style.RESET_ALL}")
        
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
        
        print(f"{Fore.GREEN}  ✓ Reset complete{Style.RESET_ALL}")
        return True
        
    except Exception as e:
        print(f"{Fore.RED}Git reset error: {e}{Style.RESET_ALL}")
        return False


def clone_repo_with_retry(repo, base_commit, target_folder, max_retries=MAX_CLONE_RETRIES):
    """Clone repository with retry logic and Windows long path support."""
    
    for attempt in range(max_retries):
        try:
            if attempt > 0:
                print(f"{Fore.YELLOW}🔄 Retry {attempt + 1}/{max_retries}...{Style.RESET_ALL}")
                time.sleep(2 ** attempt)
            
            # If exists, try to reset first (fastest)
            if os.path.exists(target_folder):
                if os.path.exists(os.path.join(target_folder, ".git")):
                    print(f"{Fore.CYAN}  → Repository exists, attempting reset...{Style.RESET_ALL}")
                    if reset_git_repo(target_folder, base_commit):
                        return target_folder
                    print(f"{Fore.YELLOW}  → Reset failed, removing and re-cloning...{Style.RESET_ALL}")
                
                if not safe_rmtree(target_folder):
                    raise Exception("Could not remove existing directory")
            
            # Clone fresh
            clone_url = f"https://github.com/{repo}.git"
            print(f"{Fore.CYAN}  → Cloning: {clone_url}{Style.RESET_ALL}")
            
            # Build clone command with long path support
            clone_cmd = ["git", "clone"]
            
            # CRITICAL: Add long paths config for Windows
            if sys.platform == "win32":
                clone_cmd.extend(["-c", "core.longpaths=true"])
            
            # Strategy based on attempt
            if attempt == 0:
                # Shallow clone (faster)
                clone_cmd.extend(["--depth", "50", "--no-single-branch"])
                print(f"{Fore.CYAN}  → Strategy: Shallow clone (depth=50){Style.RESET_ALL}")
            else:
                # Full clone on retry
                print(f"{Fore.CYAN}  → Strategy: Full clone{Style.RESET_ALL}")
            
            clone_cmd.extend([clone_url, target_folder])
            
            # Show command for debugging
            if attempt > 0:
                print(f"{Fore.CYAN}  → Command: {' '.join(clone_cmd)}{Style.RESET_ALL}")
            
            result = run_git_command(
                clone_cmd,
                os.getcwd(),
                timeout=CLONE_TIMEOUT,
                capture_output=False
            )
            
            if result is None:
                raise Exception(f"Clone timeout after {CLONE_TIMEOUT}s")
            
            if result.returncode != 0:
                # Check for specific errors
                if result.returncode == 128:
                    raise Exception(f"Git error 128 (may be network, auth, or long paths issue)")
                raise Exception(f"Clone failed with code {result.returncode}")
            
            print(f"{Fore.GREEN}  ✓ Clone successful{Style.RESET_ALL}")
            
            # Now fetch and checkout the specific commit
            print(f"{Fore.CYAN}  → Fetching base commit...{Style.RESET_ALL}")
            
            # Try to fetch the specific commit
            run_git_command(["git", "fetch", "origin", base_commit], target_folder, timeout=FETCH_TIMEOUT)
            
            # Check if commit is accessible
            result = run_git_command(["git", "cat-file", "-e", base_commit], target_folder, timeout=10)
            if result is None or result.returncode != 0:
                print(f"{Fore.CYAN}  → Commit not found, unshallowing...{Style.RESET_ALL}")
                run_git_command(["git", "fetch", "--unshallow"], target_folder, timeout=FETCH_TIMEOUT)
            
            # Reset to base commit
            if not reset_git_repo(target_folder, base_commit):
                raise Exception("Failed to reset to base commit")
            
            return target_folder
            
        except Exception as e:
            error_msg = str(e)
            print(f"{Fore.RED}  ✗ Attempt {attempt + 1} failed: {error_msg}{Style.RESET_ALL}")
            
            # Provide helpful error messages
            if "128" in error_msg or "Filename too long" in error_msg:
                print(f"{Fore.YELLOW}  💡 This might be a Windows long path issue.{Style.RESET_ALL}")
                print(f"{Fore.YELLOW}     Run: git config --global core.longpaths true{Style.RESET_ALL}")
            
            # Clean up failed attempt
            if os.path.exists(target_folder):
                safe_rmtree(target_folder)
            
            # Last attempt failed
            if attempt == max_retries - 1:
                raise Exception(f"Clone failed after {max_retries} attempts: {error_msg}")
            
            # Wait before retry
            time.sleep(2)
    
    raise Exception("Clone failed - max retries exceeded")


def get_git_diff(repo_path):
    """Get git diff of changes in standard unified diff format."""
    try:
        # Add all changes, excluding lockfiles to keep patches clean
        run_git_command(["git", "add", "-A", "--", ":!package-lock.json", ":!yarn.lock", ":!pnpm-lock.yaml"], repo_path)
        
        # Check if there are changes
        result = run_git_command(["git", "diff", "--cached", "--exit-code"], repo_path)
        
        if result and result.returncode == 0:
            # No changes
            return ""
        
        # Get the diff in unified format
        result = run_git_command(["git", "diff", "--cached"], repo_path)
        diff = result.stdout if result else ""
        
        # Reset staging area but keep working directory changes
        run_git_command(["git", "reset", "HEAD"], repo_path)
        
        return diff
    except Exception as e:
        print(f"{Fore.RED}Error getting diff: {e}{Style.RESET_ALL}")
        return ""

# ========================== DATASET OPERATIONS ==========================

def load_dataset_swe_polybench():
    """Load SWE-PolyBench dataset from HuggingFace."""
    print(f"{Fore.YELLOW}📂 Loading SWE-PolyBench dataset...{Style.RESET_ALL}")
    dataset = load_dataset("AmazonScience/SWE-PolyBench", split="test")
    
    # Convert to list of dicts
    problems = []
    for item in dataset:
        problems.append(dict(item))
    
    return problems


def get_completed_instances(predictions_file):
    """Get completed instance IDs and details."""
    completed = {}
    if not os.path.exists(predictions_file):
        return completed
    
    with open(predictions_file, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            if line.strip():
                try:
                    entry = json.loads(line)
                    instance_id = entry.get("instance_id")
                    if instance_id:
                        completed[instance_id] = {
                            "model_patch": entry.get("model_patch", ""),
                            "has_changes": bool(entry.get("model_patch", "").strip()),
                            "line_number": line_num
                        }
                except Exception as e:
                    print(f"{Fore.YELLOW}Warning: Skipping malformed line {line_num} in predictions file{Style.RESET_ALL}")
    
    return completed


def save_prediction(predictions_file, output):
    """Save prediction to file in SWE-PolyBench format."""
    with open(predictions_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(output) + "\n")
        f.flush()

# ========================== PROBLEM FORMATTING ==========================

def format_problem(problem_data):
    """Format problem into prompt for AI agent."""
    problem_text = problem_data.get("problem_statement", "No problem statement available")
    hints = problem_data.get("hints_text", "")
    
    prompt = f"""Instance ID: {problem_data.get('instance_id', 'Unknown')}
Repository: {problem_data.get('repo', 'Unknown')}
Language: {problem_data.get('language', 'Unknown')}
Task Category: {problem_data.get('task_category', 'Unknown')}

PROBLEM STATEMENT:
{problem_text}"""
    
    if hints and hints.strip():
        prompt += f"""

HINTS:
{hints}"""
    
    return prompt


def save_prompt_to_file(prompt, filename="current_problem.txt"):
    """Save prompt to a text file for easy access."""
    try:
        with open(filename, "w", encoding="utf-8") as f:
            f.write(prompt)
        return filename
    except:
        return None

# ========================== TRAJECTORY HANDLING ==========================

def save_trajectory(instance_id, trajectories_dir, auto_mode=False):
    """Save agent's reasoning trajectory."""
    if auto_mode:
        trajectory_content = f"Automatic trajectory for {instance_id}\nAgent completed the task."
    else:
        print(f"\n{Fore.CYAN}{'─'*70}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}📝 SAVE TRAJECTORY{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'─'*70}{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}Paste the agent's conversation/reasoning below.{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}Press ENTER twice on empty line to finish, or type 'skip' to skip.{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'─'*70}{Style.RESET_ALL}\n")
        
        lines = []
        empty_line_count = 0
        
        while True:
            try:
                line = input()
                
                if line.strip().lower() == 'skip' and not lines:
                    trajectory_content = "Trajectory skipped by user."
                    break
                
                if line.strip() == "":
                    empty_line_count += 1
                    if empty_line_count >= 2:
                        if lines and lines[-1] == "":
                            lines.pop()
                        break
                    lines.append(line)
                else:
                    empty_line_count = 0
                    lines.append(line)
            except EOFError:
                break
        
        trajectory_content = '\n'.join(lines) if lines else "Agent solved the problem and made necessary code changes."
    
    # Save trajectory
    traj_file = trajectories_dir / f"{instance_id}.md"
    with open(traj_file, 'w', encoding='utf-8') as f:
        f.write(f"# Trajectory: {instance_id}\n\n")
        f.write(f"**Timestamp:** {datetime.now().isoformat()}\n\n")
        f.write(trajectory_content)
    
    if not auto_mode:
        print(f"\n{Fore.GREEN}✓ Trajectory saved to {traj_file}{Style.RESET_ALL}")
    
    return traj_file

# ========================== VALIDATION ==========================

def validate_patch(patch_content):
    """Validate that the patch is in proper diff format."""
    if not patch_content or not patch_content.strip():
        return True, "Empty patch (no changes)"
    
    lines = patch_content.split('\n')
    has_diff_header = any(line.startswith('diff --git') for line in lines[:10])
    has_hunks = any(line.startswith('@@') for line in lines)
    
    if not has_diff_header and not has_hunks:
        return False, "Patch doesn't appear to be in valid diff format"
    
    return True, "Valid diff format"

# ========================== MAIN FUNCTION ==========================

def main():
    parser = argparse.ArgumentParser(
        description='SWE-PolyBench AI Runner v2.4 - Separate Instance Folders + Auto-Resume',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('--model-name', default='cora')
    parser.add_argument('--loop', action='store_true')
    parser.add_argument('--skip-trajectory', action='store_true')
    parser.add_argument('--start', type=int, default=None)
    parser.add_argument('--end', type=int, default=None)
    parser.add_argument('--allow-empty', action='store_true')
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--reset-state', action='store_true')
    parser.add_argument('--skip-clone-errors', action='store_true')
    
    args = parser.parse_args()
    
    WORKING_FOLDER = "swe_polybench_workspace"
    PREDICTIONS_FILE = "predictions.jsonl"
    TRAJECTORIES_DIR = Path(WORKING_FOLDER) / "trajectories"
    
    # Initialize state manager
    state_mgr = StateManager()
    
    if args.reset_state:
        print(f"{Fore.YELLOW}Resetting state...{Style.RESET_ALL}")
        state_mgr.state = StateManager().load_state()
        state_mgr.save_state()
    
    print(f"{Fore.CYAN}{'='*70}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}🤖 SWE-PolyBench AI Runner v2.4{Style.RESET_ALL}")
    print(f"{Fore.CYAN}📊 Model: {args.model_name}{Style.RESET_ALL}")
    
    # Check and enable Windows long paths
    if sys.platform == "win32":
        longpaths_enabled = check_and_enable_longpaths()
        if longpaths_enabled:
            print(f"{Fore.GREEN}✓ Windows long paths: ENABLED{Style.RESET_ALL}")
        else:
            print(f"{Fore.YELLOW}⚠️  Windows long paths: Check failed{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}   Some repos with long paths may fail to clone{Style.RESET_ALL}")
    
    print(f"{Fore.CYAN}{'='*70}{Style.RESET_ALL}\n")
    
    os.makedirs(WORKING_FOLDER, exist_ok=True)
    TRAJECTORIES_DIR.mkdir(exist_ok=True)
    
    # Load dataset
    try:
        dataset = load_dataset_swe_polybench()
        total_instances = len(dataset)
        print(f"{Fore.GREEN}✓ Loaded {total_instances} problems from SWE-PolyBench{Style.RESET_ALL}\n")
    except Exception as e:
        print(f"{Fore.RED}❌ Failed to load dataset: {e}{Style.RESET_ALL}")
        traceback.print_exc()
        return
    
    # Check for resume
    if args.resume and state_mgr.can_resume():
        print(f"{Fore.YELLOW}📁 RESUME MODE{Style.RESET_ALL}")
        print(f"Last processed: {state_mgr.state['last_instance_id']}")
        print(f"Instance index: {state_mgr.state['last_instance_index'] + 1}/{total_instances}")
        print(f"Total solved: {state_mgr.state['total_solved']}")
        
        if state_mgr.state['cloning_errors']:
            print(f"Cloning errors: {len(state_mgr.state['cloning_errors'])}")
        
        # Show original range if available
        orig_start = state_mgr.state['range']['start']
        orig_end = state_mgr.state['range']['end']
        if orig_start is not None and orig_end is not None:
            print(f"Original range: {orig_start + 1} to {orig_end + 1}")
        
        # AUTO-RESUME: Skip prompt, go straight to work
        # Calculate new range
        args.start = state_mgr.state['last_instance_index'] + 1
        args.end = state_mgr.state['range']['end'] if state_mgr.state['range']['end'] is not None else total_instances - 1
        args.loop = True
        
        # Show NEW adjusted range clearly
        remaining = args.end - args.start + 1
        print(f"{Fore.GREEN}✓ Auto-resuming from instance {args.start + 1}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}✓ NEW range: {args.start + 1} to {args.end + 1} ({remaining} instances remaining){Style.RESET_ALL}\n")
    elif args.resume and not state_mgr.can_resume():
        print(f"{Fore.YELLOW}⚠️  Resume requested but no previous state found{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}Starting fresh...{Style.RESET_ALL}\n")
        args.resume = False
    
    # Interactive range selection if not provided and not resuming
    if not args.resume and (args.start is None or args.end is None):
        print(f"{Fore.CYAN}{'='*70}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}SELECT RANGE{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'='*70}{Style.RESET_ALL}")
        print(f"Total instances available: {total_instances}")
        print()
        
        use_range = input(f"{Fore.YELLOW}Test specific range? (y/n): {Style.RESET_ALL}").strip().lower()
        
        if use_range == 'y':
            while True:
                try:
                    start_input = int(input(f"{Fore.YELLOW}Start from instance number (1-{total_instances}): {Style.RESET_ALL}"))
                    end_input = int(input(f"{Fore.YELLOW}End at instance number (1-{total_instances}): {Style.RESET_ALL}"))
                    
                    # Validate 1-indexed input
                    if 1 <= start_input <= total_instances and 1 <= end_input <= total_instances and start_input <= end_input:
                        # Convert to 0-indexed
                        args.start = start_input - 1
                        args.end = end_input - 1
                        break
                    else:
                        print(f"{Fore.RED}❌ Invalid range. Try again.{Style.RESET_ALL}")
                except ValueError:
                    print(f"{Fore.RED}❌ Please enter valid numbers.{Style.RESET_ALL}")
        else:
            args.start = 0
            args.end = total_instances - 1
        
        if use_range == 'y' or input(f"{Fore.YELLOW}Auto-continue through instances? (y/n): {Style.RESET_ALL}").strip().lower() == 'y':
            args.loop = True
        
        print()
    else:
        # Command line args (not resuming)
        if not args.resume:
            if args.start is not None:
                # User provides 1-indexed, validate then convert to 0-indexed
                if args.start < 1 or args.start > total_instances:
                    print(f"{Fore.RED}❌ Invalid start. Must be 1-{total_instances}{Style.RESET_ALL}")
                    return
                args.start = args.start - 1
            else:
                args.start = 0
                
            if args.end is not None:
                # User provides 1-indexed, validate then convert to 0-indexed
                if args.end < 1 or args.end > total_instances:
                    print(f"{Fore.RED}❌ Invalid end. Must be 1-{total_instances}{Style.RESET_ALL}")
                    return
                args.end = args.end - 1
            else:
                args.end = total_instances - 1
            
            # Cross-validate
            if args.end < args.start:
                print(f"{Fore.RED}❌ End ({args.end + 1}) must be >= Start ({args.start + 1}){Style.RESET_ALL}")
                return
    
    # Final validation (for both resume and non-resume)
    if args.start < 0 or args.start >= total_instances:
        print(f"{Fore.RED}❌ Invalid start index after processing. Must be 1-{total_instances}{Style.RESET_ALL}")
        return
    
    if args.end < args.start or args.end >= total_instances:
        print(f"{Fore.RED}❌ Invalid end index after processing. Must be {args.start+1}-{total_instances}{Style.RESET_ALL}")
        return
    
    # Update state with range
    state_mgr.set_range(args.start, args.end)
    
    # Filter dataset to range
    dataset_range = dataset[args.start:args.end+1]
    
    # Show CURRENT working range (updated label for clarity)
    print(f"{Fore.CYAN}📍 Working Range: {args.start+1} to {args.end+1} ({len(dataset_range)} instances){Style.RESET_ALL}")
    print(f"{Fore.CYAN}🔄 Mode: {'Auto-loop' if args.loop else 'Manual (one at a time)'}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}📝 Trajectory: {'Auto-generate' if args.skip_trajectory else 'Manual input'}{Style.RESET_ALL}")
    if args.skip_clone_errors:
        print(f"{Fore.CYAN}⚠️  Clone errors: Auto-skip enabled{Style.RESET_ALL}")
    print()
    
    # Show existing predictions summary
    completed = get_completed_instances(PREDICTIONS_FILE)
    if completed:
        completed_with_changes = sum(1 for v in completed.values() if v['has_changes'])
        completed_empty = len(completed) - completed_with_changes
        print(f"{Fore.YELLOW}📊 Existing predictions: {len(completed)} total ({completed_with_changes} with changes, {completed_empty} empty){Style.RESET_ALL}")
    
    input(f"\n{Fore.GREEN}Press ENTER to start...{Style.RESET_ALL}")
    print()
    
    # Main processing loop
    instances_processed = 0
    instances_with_changes = 0
    instances_empty = 0
    instances_skipped = 0
    clone_errors = 0
    
    for idx, problem in enumerate(dataset_range):
        current_index = args.start + idx
        instance_id = problem["instance_id"]
        
        # Skip if already completed
        if instance_id in completed:
            print(f"{Fore.YELLOW}⏭️  Skipping {instance_id} (already in predictions){Style.RESET_ALL}\n")
            instances_skipped += 1
            continue
        
        repo = problem["repo"]
        base_commit = problem["base_commit"]
        problem_lang = problem.get("language", "Unknown")
        task_category = problem.get("task_category", "Unknown")
        
        # Use instance_id for folder name instead of repo name (creates separate folder per instance)
        repo_path = os.path.join(WORKING_FOLDER, instance_id.replace("/", "_"))
        
        print(f"{Fore.YELLOW}{'='*70}{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}📋 Problem {current_index + 1}/{args.end + 1}: {instance_id}{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}📦 Repository: {repo}{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}🌍 Language: {problem_lang.upper()}{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}🏷️  Category: {task_category}{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}{'='*70}{Style.RESET_ALL}\n")
        
        # Update state
        state_mgr.update_progress(instance_id, current_index)
        
        try:
            # Prepare repository with retry
            print(f"{Fore.CYAN}🔧 Preparing repository...{Style.RESET_ALL}")
            
            try:
                clone_repo_with_retry(repo, base_commit, repo_path)
                print(f"{Fore.GREEN}✓ Repository ready at: {repo_path}{Style.RESET_ALL}\n")
            except Exception as clone_error:
                clone_errors += 1
                error_msg = str(clone_error)
                print(f"{Fore.RED}❌ CLONE FAILED: {error_msg}{Style.RESET_ALL}\n")
                
                
                # Track the error
                state_mgr.mark_clone_error(repo, instance_id, error_msg)
                state_mgr.mark_failed(instance_id, f"Clone error: {error_msg}")
                
                # Always prompt user - don't auto-skip to prevent gaps
                print(f"{Fore.CYAN}Options:{Style.RESET_ALL}")
                print(f"{Fore.CYAN}  r - Retry this instance{Style.RESET_ALL}")
                print(f"{Fore.CYAN}  s - Skip and continue{Style.RESET_ALL}")
                print(f"{Fore.CYAN}  q - Quit{Style.RESET_ALL}\n")
                
                choice = input(f"{Fore.YELLOW}Choose option (r/s/q): {Style.RESET_ALL}").strip().lower()
                
                if choice == 'r':
                    try:
                        print(f"\n{Fore.CYAN}Retrying clone...{Style.RESET_ALL}")
                        clone_repo_with_retry(repo, base_commit, repo_path, max_retries=2)
                        print(f"{Fore.GREEN}✓ Repository ready at: {repo_path}{Style.RESET_ALL}\n")
                    except:
                        print(f"{Fore.RED}❌ Retry failed. Skipping instance.{Style.RESET_ALL}\n")
                        instances_skipped += 1
                        continue
                elif choice == 'q':
                    print(f"{Fore.YELLOW}Exiting... Progress saved.{Style.RESET_ALL}")
                    break
                else:
                    print(f"{Fore.YELLOW}Skipping instance{Style.RESET_ALL}\n")
                    instances_skipped += 1
                    continue
            
            # Format problem
            prompt = format_problem(problem)
            
            # Try to copy to clipboard
            print(f"{Fore.CYAN}📋 Copying problem to clipboard...{Style.RESET_ALL}")
            clipboard_success = copy_to_clipboard_with_timeout(prompt)
            
            if clipboard_success:
                print(f"{Fore.GREEN}✓ Problem copied to clipboard!{Style.RESET_ALL}")
            else:
                print(f"{Fore.YELLOW}⚠️  Clipboard unavailable{Style.RESET_ALL}")
            
            # Always save to file
            prompt_file = save_prompt_to_file(prompt)
            if prompt_file:
                print(f"{Fore.GREEN}✓ Problem saved to: {prompt_file}{Style.RESET_ALL}")
            
            print()
            
            # Show instructions
            print(f"{Fore.CYAN}{'─'*70}{Style.RESET_ALL}")
            print(f"{Fore.CYAN}📝 INSTRUCTIONS:{Style.RESET_ALL}")
            print(f"{Fore.CYAN}1. Open your AI agent/IDE (Codemate, Cursor, Windsurf, etc.){Style.RESET_ALL}")
            print(f"{Fore.CYAN}2. Navigate to: {repo_path}{Style.RESET_ALL}")
            if clipboard_success:
                print(f"{Fore.CYAN}3. Paste the problem (Ctrl+V) into your agent{Style.RESET_ALL}")
            else:
                print(f"{Fore.CYAN}3. Open '{prompt_file}' and copy the problem to your agent{Style.RESET_ALL}")
            print(f"{Fore.CYAN}4. Let the agent solve the problem and make code changes{Style.RESET_ALL}")
            print(f"{Fore.CYAN}5. Press ENTER here when agent has finished{Style.RESET_ALL}")
            print(f"{Fore.CYAN}{'─'*70}{Style.RESET_ALL}\n")
            
            # Wait for user
            start_time = time.time()
            try:
                input(f"{Fore.GREEN}⏸️  Press ENTER when done (or Ctrl+C to quit): {Style.RESET_ALL}")
            except KeyboardInterrupt:
                print(f"\n\n{Fore.YELLOW}🛑 Interrupted by user{Style.RESET_ALL}")
                print(f"{Fore.CYAN}Progress saved. Run with --resume to continue from instance {current_index + 1}{Style.RESET_ALL}")
                break
            
            time_taken = time.time() - start_time
            
            print(f"\n{Fore.YELLOW}⚙️  Processing results...{Style.RESET_ALL}")
            
            # Get diff
            diff = get_git_diff(repo_path)
            
            # Validate the diff
            is_valid, validation_msg = validate_patch(diff)
            
            # Check if changes were made
            has_changes = bool(diff and diff.strip())
            
            if not has_changes:
                print(f"{Fore.RED}❌ NO CHANGES DETECTED!{Style.RESET_ALL}")
                print(f"{Fore.YELLOW}⚠️  The repository has no modifications.{Style.RESET_ALL}")
                print(f"{Fore.YELLOW}⚠️  {validation_msg}{Style.RESET_ALL}\n")
                
                print(f"{Fore.CYAN}What happened?{Style.RESET_ALL}")
                print(f"{Fore.CYAN}  a - Agent couldn't solve it (save empty patch){Style.RESET_ALL}")
                print(f"{Fore.CYAN}  r - Retry (go back and try again){Style.RESET_ALL}")
                print(f"{Fore.CYAN}  s - Skip this instance{Style.RESET_ALL}")
                print(f"{Fore.CYAN}  q - Quit{Style.RESET_ALL}\n")
                
                choice = input(f"{Fore.YELLOW}Choose option (a/r/s/q): {Style.RESET_ALL}").strip().lower()
                
                if choice == 'r':
                    print(f"\n{Fore.YELLOW}Please make changes in the repository and press ENTER when ready...{Style.RESET_ALL}")
                    input(f"{Fore.GREEN}⏸️  Press ENTER when changes are made: {Style.RESET_ALL}")
                    
                    diff = get_git_diff(repo_path)
                    has_changes = bool(diff and diff.strip())
                    
                    if not has_changes:
                        print(f"{Fore.RED}❌ Still no changes detected.{Style.RESET_ALL}")
                        if not args.allow_empty:
                            print(f"{Fore.YELLOW}Skipping instance. Use --allow-empty to force save.{Style.RESET_ALL}")
                            state_mgr.mark_failed(instance_id, "No changes after retry")
                            reset_git_repo(repo_path, base_commit)
                            instances_skipped += 1
                            if not args.loop:
                                break
                            continue
                    else:
                        print(f"{Fore.GREEN}✓ Changes detected: {len(diff)} bytes{Style.RESET_ALL}")
                
                elif choice == 'q':
                    print(f"{Fore.YELLOW}Exiting... Progress saved.{Style.RESET_ALL}")
                    break
                
                elif choice == 's':
                    print(f"{Fore.YELLOW}Skipping this instance{Style.RESET_ALL}")
                    state_mgr.mark_failed(instance_id, "Skipped by user")
                    reset_git_repo(repo_path, base_commit)
                    instances_skipped += 1
                    if not args.loop:
                        break
                    continue
                
                elif choice == 'a' or args.allow_empty:
                    print(f"{Fore.YELLOW}Saving empty patch (agent couldn't solve)...{Style.RESET_ALL}")
                    diff = ""
                    has_changes = False
                
                else:
                    print(f"{Fore.YELLOW}Invalid choice. Skipping instance.{Style.RESET_ALL}")
                    state_mgr.mark_failed(instance_id, "Invalid user choice")
                    reset_git_repo(repo_path, base_commit)
                    instances_skipped += 1
                    if not args.loop:
                        break
                    continue
            else:
                print(f"{Fore.GREEN}✓ Changes detected: {len(diff)} bytes{Style.RESET_ALL}")
                if not is_valid:
                    print(f"{Fore.YELLOW}⚠️  Warning: {validation_msg}{Style.RESET_ALL}")
            
            # Save prediction
            prediction_entry = {
                "instance_id": instance_id,
                "model_name_or_path": args.model_name,
                "model_patch": diff
            }
            
            save_prediction(PREDICTIONS_FILE, prediction_entry)
            print(f"{Fore.GREEN}✓ Prediction saved to {PREDICTIONS_FILE}{Style.RESET_ALL}")
            
            # Update stats
            instances_processed += 1
            if has_changes:
                instances_with_changes += 1
                state_mgr.mark_solved()
            else:
                instances_empty += 1
            
            # Save trajectory
            if not args.skip_trajectory:
                save_trajectory(instance_id, TRAJECTORIES_DIR, auto_mode=False)
            else:
                save_trajectory(instance_id, TRAJECTORIES_DIR, auto_mode=True)
                print(f"{Fore.GREEN}✓ Auto-generated trajectory{Style.RESET_ALL}")
            
            print(f"{Fore.GREEN}✓ Instance completed in {time_taken:.1f}s{Style.RESET_ALL}")
            print(f"{Fore.CYAN}📊 Session: {instances_processed} done, {instances_with_changes} solved, {instances_empty} empty, {instances_skipped} skipped, {clone_errors} clone errors{Style.RESET_ALL}\n")
            
            # Clean repo
            reset_git_repo(repo_path, base_commit)
            
            if not args.loop:
                print(f"{Fore.GREEN}💡 Run with --loop flag to auto-continue, or --resume to continue later{Style.RESET_ALL}")
                break
            
            # Small delay
            if args.loop and idx < len(dataset_range) - 1:
                time.sleep(0.5)
            
        except KeyboardInterrupt:
            print(f"\n\n{Fore.YELLOW}🛑 Interrupted by user{Style.RESET_ALL}")
            print(f"{Fore.CYAN}Progress saved. Run with --resume to continue from instance {current_index + 1}{Style.RESET_ALL}")
            break
            
        except Exception as e:
            print(f"{Fore.RED}❌ Error processing {instance_id}: {e}{Style.RESET_ALL}")
            traceback.print_exc()
            
            state_mgr.mark_failed(instance_id, str(e))
            
            if args.allow_empty:
                save_prediction(PREDICTIONS_FILE, {
                    "instance_id": instance_id,
                    "model_name_or_path": args.model_name,
                    "model_patch": ""
                })
                print(f"{Fore.YELLOW}⚠️  Saved empty prediction due to error{Style.RESET_ALL}")
                instances_empty += 1
            else:
                print(f"{Fore.YELLOW}⚠️  Not saving prediction (use --allow-empty to force){Style.RESET_ALL}")
                instances_skipped += 1
            
            if args.loop:
                continue_choice = input(f"\n{Fore.YELLOW}Continue to next instance? (y/n): {Style.RESET_ALL}").strip().lower()
                if continue_choice != 'y':
                    break
            else:
                break
    
    # Final summary
    print(f"\n{Fore.CYAN}{'='*70}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}📊 SESSION COMPLETE{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'='*70}{Style.RESET_ALL}")
    print(f"{Fore.GREEN}✓ Instances processed: {instances_processed}{Style.RESET_ALL}")
    print(f"{Fore.GREEN}  - With changes: {instances_with_changes}{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}  - Empty patches: {instances_empty}{Style.RESET_ALL}")
    print(f"{Fore.RED}  - Skipped: {instances_skipped}{Style.RESET_ALL}")
    print(f"{Fore.RED}  - Clone errors: {clone_errors}{Style.RESET_ALL}")
    
    final_completed = get_completed_instances(PREDICTIONS_FILE)
    print(f"\n{Fore.CYAN}📁 Total in predictions file: {len(final_completed)}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}📂 Trajectories saved to: {TRAJECTORIES_DIR}{Style.RESET_ALL}")
    
    if state_mgr.state['failed_instances']:
        print(f"\n{Fore.YELLOW}⚠️  Failed instances: {len(state_mgr.state['failed_instances'])}{Style.RESET_ALL}")
    
    if state_mgr.state['cloning_errors']:
        print(f"{Fore.RED}⚠️  Cloning errors: {len(state_mgr.state['cloning_errors'])}{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}   Run 'git config --global core.longpaths true' if on Windows{Style.RESET_ALL}")
    
    print(f"\n{Fore.GREEN}{'='*70}{Style.RESET_ALL}")
    print(f"{Fore.GREEN}🎉 All done! Use --resume to continue if needed.{Style.RESET_ALL}")
    print(f"{Fore.GREEN}{'='*70}{Style.RESET_ALL}\n")


if __name__ == "__main__":
    main()