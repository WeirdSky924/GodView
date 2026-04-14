import json
import urllib.request

def main():
    # Read execution_id
    with open("E:/_Workspace/Godview/test_execution_id.txt", "r") as f:
        execution_id = f.read().strip()
    
    print(f"Checking execution: {execution_id}")
    
    req = urllib.request.Request(
        f"http://localhost:8000/api/workflows/executions/{execution_id}"
    )
    
    with urllib.request.urlopen(req, timeout=10) as response:
        execution = json.loads(response.read().decode('utf-8'))
        status = execution.get('status', 'unknown')
        current_node = execution.get('current_node', 'N/A')
        
        print(f"Status: {status}")
        print(f"Current node: {current_node}")
        
        # Print node states
        node_states = execution.get('node_states', {})
        print("\nNode states:")
        for node_id, state in node_states.items():
            node_status = state.get('status', 'unknown')
            duration = state.get('duration_ms', 0)
            error = state.get('error', '')
            output_keys = list(state.get('output_data', {}).keys()) if state.get('output_data') else []
            print(f"  {node_id}: {node_status} ({duration}ms)")
            if output_keys:
                print(f"    Output keys: {output_keys}")
            if error:
                print(f"    Error: {error[:200]}...")
        
        # Save result
        with open("E:/_Workspace/Godview/test_execution_result.json", "w", encoding="utf-8") as f:
            json.dump(execution, f, ensure_ascii=False, indent=2)
        print("\nFull result saved to test_execution_result.json")

if __name__ == "__main__":
    main()
