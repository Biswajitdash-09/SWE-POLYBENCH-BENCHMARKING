"""
Process missing problems in order from missing_problems.json
This ensures all skipped problems are completed sequentially
"""
import json
import subprocess
import sys

def main():
    # Load missing problems
    with open('missing_problems.json', 'r') as f:
        missing = json.load(f)
    
    if not missing:
        print("✓ No missing problems! All completed.")
        return
    
    print(f"Found {len(missing)} missing problems in range 200-299")
    print(f"First missing: Index {missing[0]['index']} | ID: {missing[0]['instance_id']}")
    print()
    
    # Process each missing problem one by one
    for item in missing:
        index = item['index']
        instance_id = item['instance_id']
        
        print(f"\n{'='*70}")
        print(f"Processing: Index {index} | {instance_id}")
        print(f"{'='*70}\n")
        
        # Update state to point to this problem
        with open('swe_polybench_state.json', 'r') as f:
            state = json.load(f)
        
        # Set to the problem BEFORE this one, so --resume will pick up THIS one
        state['last_instance_index'] = index - 1
        state['last_instance_id'] = f"placeholder_{index-1}"
        
        with open('swe_polybench_state.json', 'w') as f:
            json.dump(state, f, indent=2)
        
        print(f"Updated state to resume from index {index}")
        print(f"Run: python swe_polybench_tester.py --resume --loop --skip-trajectory")
        print()
        
        # Ask user if they want to process this one
        choice = input("Process this problem? (y/n/q to quit): ").strip().lower()
        
        if choice == 'q':
            print("\nExiting. Progress saved.")
            break
        elif choice == 'y':
            print(f"\nPlease run the tester manually:")
            print(f"  python swe_polybench_tester.py --resume --loop --skip-trajectory")
            print(f"\nPress ENTER when you've completed this problem...")
            input()
            
            # Check if it's now in predictions
            completed_ids = set()
            try:
                with open('predictions.jsonl', 'r') as f:
                    for line in f:
                        if line.strip():
                            entry = json.loads(line)
                            completed_ids.add(entry.get('instance_id'))
            except:
                pass
            
            if instance_id in completed_ids:
                print(f"✓ {instance_id} is now completed!")
            else:
                print(f"⚠️  {instance_id} not found in predictions. Skipping to next...")
        else:
            print(f"Skipping {instance_id}")
            continue
    
    print("\n" + "="*70)
    print("All missing problems processed!")
    print("="*70)

if __name__ == "__main__":
    main()
