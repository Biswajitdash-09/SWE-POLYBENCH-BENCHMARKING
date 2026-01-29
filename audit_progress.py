import json
import os
from datasets import load_dataset

def audit_progress():
    predictions_file = 'predictions.jsonl'
    
    # Load all completed instances
    completed = set()
    if os.path.exists(predictions_file):
        with open(predictions_file, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    try:
                        entry = json.loads(line)
                        completed.add(entry.get('instance_id'))
                    except:
                        pass
    
    # Load dataset
    print("Loading dataset...")
    dataset = load_dataset('AmazonScience/SWE-PolyBench', split='test')
    
    range_start = 200
    range_end = 299
    
    print(f"\nAudit for indices {range_start} to {range_end}:")
    print("-" * 30)
    
    missing = []
    for i in range(range_start, range_end + 1):
        iid = dataset[i]['instance_id']
        if iid not in completed:
            missing.append({'index': i, 'instance_id': iid})
            
    with open('missing_problems.json', 'w') as f:
        json.dump(missing, f, indent=2)
        
    print(f"Total missing in range: {len(missing)}")
    if missing:
        print(f"First missing: Index {missing[0]['index']} | ID: {missing[0]['instance_id']}")
    print("Results saved to missing_problems.json")

if __name__ == "__main__":
    audit_progress()
