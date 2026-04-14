from playwright.sync_api import sync_playwright
import time
import json
import urllib.request
import urllib.error

def main():
    print("=" * 60)
    print("Step 1: Check backend health")
    print("=" * 60)
    
    # Check backend health
    req = urllib.request.Request("http://localhost:8000/health")
    with urllib.request.urlopen(req, timeout=10) as response:
        health = json.loads(response.read().decode('utf-8'))
        print(f"Backend status: {health['status']}")
    
    # Get existing projects
    print("\n" + "=" * 60)
    print("Step 2: Get or create project")
    print("=" * 60)
    
    req = urllib.request.Request("http://localhost:8000/api/projects")
    with urllib.request.urlopen(req, timeout=10) as response:
        projects = json.loads(response.read().decode('utf-8'))
    
    if projects:
        project_id = projects[0]['id']
        print(f"Using existing project: {project_id}")
        print(f"Project name: {projects[0].get('name', 'N/A')}")
    else:
        # Create a test project
        project_data = {
            "name": "Test Novel Project",
            "description": "Test project for workflow",
            "genre": "fantasy",
            "target_word_count": 50000,
        }
        req = urllib.request.Request(
            "http://localhost:8000/api/projects",
            method="POST",
            headers={"Content-Type": "application/json"},
            data=json.dumps(project_data).encode('utf-8')
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode('utf-8'))
            project_id = result.get('project', {}).get('id') or result.get('id')
        print(f"Created project: {project_id}")
    
    # Save project_id
    with open("E:/_Workspace/Godview/test_project_id.txt", "w") as f:
        f.write(project_id)
    
    print("\n" + "=" * 60)
    print("Step 3: Create workflow")
    print("=" * 60)
    
    # Create a simplified workflow for testing
    workflow_data = {
        "project_id": project_id,
        "name": "Chapter Generation Test",
        "description": "Simple workflow for chapter generation",
        "is_template": False,
        "nodes": [
            {"id": "node_start", "node_type": "start", "label": "Start", "config": {}, "position": {"x": 400, "y": 0}},
            {"id": "node_outline", "node_type": "agent", "agent_type": "plot_outline", "label": "Plot Outline", "config": {}, "position": {"x": 400, "y": 100}},
            {"id": "node_writer", "node_type": "agent", "agent_type": "writer", "label": "Writer", "config": {}, "position": {"x": 400, "y": 200}},
            {"id": "node_evaluator", "node_type": "agent", "agent_type": "evaluator", "label": "Evaluator", "config": {}, "position": {"x": 400, "y": 300}},
            {"id": "node_end", "node_type": "end", "label": "End", "config": {}, "position": {"x": 400, "y": 400}},
        ],
        "edges": [
            {"id": "e1", "source": "node_start", "target": "node_outline"},
            {"id": "e2", "source": "node_outline", "target": "node_writer"},
            {"id": "e3", "source": "node_writer", "target": "node_evaluator"},
            {"id": "e4", "source": "node_evaluator", "target": "node_end"},
        ],
        "variables": {"chapter_number": 1, "target_words": 2000}
    }
    
    req = urllib.request.Request(
        "http://localhost:8000/api/workflows",
        method="POST",
        headers={"Content-Type": "application/json"},
        data=json.dumps(workflow_data).encode('utf-8')
    )
    
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode('utf-8'))
            workflow_id = result.get('workflow', {}).get('id') or result.get('id')
            print(f"Created workflow: {workflow_id}")
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        print(f"Error: {e.code} - {error_body}")
        return
    
    with open("E:/_Workspace/Godview/test_workflow_id.txt", "w") as f:
        f.write(workflow_id)
    
    print("\n" + "=" * 60)
    print("Step 4: Validate workflow")
    print("=" * 60)
    
    req = urllib.request.Request(
        f"http://localhost:8000/api/workflows/{workflow_id}/validate",
        method="POST"
    )
    
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            validation = json.loads(response.read().decode('utf-8'))
            print(f"Valid: {validation.get('valid', False)}")
            if validation.get('errors'):
                print(f"Errors: {validation['errors']}")
            print(f"Nodes: {validation.get('node_count', 0)}, Edges: {validation.get('edge_count', 0)}")
    except urllib.error.HTTPError as e:
        print(f"Validation error: {e.code}")
    
    print("\n" + "=" * 60)
    print("COMPLETED: Workflow created successfully!")
    print("=" * 60)

if __name__ == "__main__":
    main()
