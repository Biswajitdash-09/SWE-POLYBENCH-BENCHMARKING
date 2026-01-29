import json

def analyze_predictions(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip():
                    continue
                entry = json.loads(line)
                instance_id = entry.get('instance_id')
                patch = entry.get('model_patch', '')
                
                # Get files changed in the patch
                files_changed = []
                for p_line in patch.split('\n'):
                    if p_line.startswith('diff --git'):
                        files_changed.append(p_line.split(' b/')[-1])
                
                print(f"Instance: {instance_id}")
                print(f"  Files changed: {files_changed}")
                # Check for package-lock.json
                lockfile_changed = 'package-lock.json' in files_changed
                if lockfile_changed:
                    print(f"  [!] Warning: package-lock.json included in patch.")
                
                # Check if there are other meaningful changes
                logic_changes = [f for f in files_changed if f not in ('package-lock.json', 'package.json')]
                if not logic_changes:
                    print(f"  [X] Error: No logic code changes found (only lockfile/package.json).")
                else:
                    print(f"  [✓] Logic changes found in: {logic_changes}")
                print("-" * 40)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    analyze_predictions('predictions.jsonl')
