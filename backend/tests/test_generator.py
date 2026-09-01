import sys
from app.terraform.generator import AWSTerraformGenerator


def test_aws_generator_renders_templates():
    gen = AWSTerraformGenerator()

    nodes = [
        {"id": "vpc1", "type": "vpc", "data": {"resourceType": "vpc", "properties": {"name": "Test VPC"}}},
        {"id": "subnet1", "type": "subnet", "data": {"resourceType": "subnet", "properties": {"name": "subnet-a"}}},
    ]

    edges = [
        {"source": "vpc1", "target": "subnet1"}
    ]

    files = gen.generate(nodes, edges, project_name="MyProject")

    # Expect common terraform files
    filenames = {f.filename for f in files}
    assert "providers.tf" in filenames
    assert "variables.tf" in filenames
    assert "main.tf" in filenames

    # main.tf should contain a rendered block (or at least a comment)
    main = next(f for f in files if f.filename == "main.tf")
    assert isinstance(main.content, str)
    assert "vpc" in main.content.lower() or "subnet" in main.content.lower()
