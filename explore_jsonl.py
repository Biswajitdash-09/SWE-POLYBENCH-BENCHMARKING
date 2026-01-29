import json

def explore():
    try:
        with open('predictions.jsonl', 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip(): continue
                entry = json.loads(line)
                iid = entry.get('instance_id')
                patch = entry.get('model_patch', '')
                files = [l for l in patch.split('\n') if l.startswith('diff --git')]
                print(f"Instance: {iid}")
                for f_line in files:
                    print(f"  {f_line}")
                print("-" * 20)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    explore()
