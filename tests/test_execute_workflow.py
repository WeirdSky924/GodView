import json
import urllib.request
import urllib.error
import time

def main():
    # Read project_id and workflow_id
    with open("E:/_Workspace/Godview/test_project_id.txt", "r") as f:
        project_id = f.read().strip()
    with open("E:/_Workspace/Godview/test_workflow_id.txt", "r") as f:
        workflow_id = f.read().strip()
    
    print(f"Project ID: {project_id}")
    print(f"Workflow ID: {workflow_id}")
    
    print("\n" + "=" * 60)
    print("Step 5: Execute workflow")
    print("=" * 60)
    
    # Execute the workflow
    execute_data = {
        "initial_context": {
            "chapter_number": 1,
            "target_words": 2000,
            "scene_description": "A young hero discovers his magical powers for the first time",
            "genre": "fantasy"
        }
    }
    
    req = urllib.request.Request(
        f"http://localhost:8000/api/workflows/{workflow_id}/execute?project_id={project_id}",
        method="POST",
        headers={"Content-Type": "application/json"},
        data=json.dumps(execute_data).encode('utf-8')
    )
    
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode('utf-8'))
            execution_id = result.get('execution_id')
            print(f"Execution started: {execution_id}")
            print(f"Message: {result.get('message', 'N/A')}")
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        print(f"Error: {e.code} - {error_body}")
        return
    
    # Save execution_id
    with open("E:/_Workspace/Godview/test_execution_id.txt", "w") as f:
        f.write(execution_id)
    
    print("\n" + "=" * 60)
    print("Step 6: Monitor execution status")
    print("=" * 60)
    
    # Poll for status
    max_wait = 120  # 2 minutes max
    start_time = time.time()
    
    while time.time() - start_time < max_wait:
        req = urllib.request.Request(
            f"http://localhost:8000/api/workflows/executions/{execution_id}"
        )
        
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                execution = json.loads(response.read().decode('utf-8'))
                status = execution.get('status', 'unknown')
                current_node = execution.get('current_node', 'N/A')
                
                print(f"Status: {status}, Current node: {current_node}")
                
                if status in ['completed', 'failed', 'cancelled']:
                    print(f"\nExecution finished with status: {status}")
                    
                    # Print node states
                    node_states = execution.get('node_states', {})
                    print("\nNode states:")
                    for node_id, state in node_states.items():
                        node_status = state.get('status', 'unknown')
                        error = state.get('error', '')
                        print(f"  {node_id}: {node_status}" + (f" - Error: {error}" if error else ""))
                    
                    # Print context if completed
                    if status == 'completed':
                        context = execution.get('context', {})
                        print("\nContext keys:", list(context.keys()))
                        
                        # Save result
                        with open("E:/_Workspace/Godview/test_execution_result.json", "w", encoding="utf-8") as f:
                            json.dump(execution, f, ensure_ascii=False, indent=2)
                        print("\nFull result saved to test_execution_result.json")
                    
                    break
        except urllib.error.HTTPError as e:
            print(f"Error getting status: {e.code}")
        
        time.sleep(5)
    else:
        print("Timeout waiting for execution to complete")

if __name__ == "__main__":
    main()
