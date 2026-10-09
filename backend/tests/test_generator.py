from app.terraform.generator import AWSTerraformGenerator, aws_name


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


def test_aws_generator_renders_new_resources_and_relationships():
    gen = AWSTerraformGenerator()
    nodes = [
        {"id": "vpc1", "type": "vpc", "data": {"resourceType": "vpc", "properties": {"name": "network"}}},
        {"id": "igw1", "type": "internet_gateway", "data": {"resourceType": "internet_gateway", "properties": {"name": "public"}}},
        {"id": "rt1", "type": "route_table", "data": {"resourceType": "route_table", "properties": {"name": "routes"}}},
        {"id": "sub1", "type": "subnet", "data": {"resourceType": "subnet", "properties": {"name": "private"}}},
        {"id": "nat1", "type": "nat_gateway", "data": {"resourceType": "nat_gateway", "properties": {"name": "egress"}}},
        {"id": "role1", "type": "iam_role", "data": {"resourceType": "iam_role", "properties": {"name": "runtime"}}},
        {"id": "fn1", "type": "lambda", "data": {"resourceType": "lambda", "properties": {"functionName": "worker", "runtime": "python3.12", "handler": "app.handler"}}},
        {"id": "db1", "type": "dynamodb", "data": {"resourceType": "dynamodb", "properties": {"tableName": "items", "hashKey": "id"}}},
    ]
    edges = [
        {"source": "vpc1", "target": "igw1"}, {"source": "vpc1", "target": "rt1"},
        {"source": "sub1", "target": "rt1"}, {"source": "sub1", "target": "nat1"},
        {"source": "sub1", "target": "fn1"}, {"source": "role1", "target": "fn1"},
    ]
    files = gen.generate(nodes, edges, "NewApp")
    main = next(file.content for file in files if file.filename == "main.tf")
    for resource in ("aws_internet_gateway", "aws_route_table", "aws_nat_gateway", "aws_lambda_function", "aws_dynamodb_table", "aws_iam_role"):
        assert resource in main
    assert "aws_vpc.network.id" in main
    assert "aws_subnet.private.id" in main
    assert "aws_iam_role.runtime.arn" in main


def test_unknown_resource_type_is_skipped_not_raised():
    """A saved architecture may contain a type with no template; generation
    must skip it with a comment instead of failing with TemplateNotFound."""
    gen = AWSTerraformGenerator()
    nodes = [
        {"id": "vpc1", "type": "vpc", "data": {"resourceType": "vpc", "properties": {"name": "net"}}},
        {"id": "mystery", "type": "quantum_computer", "data": {"resourceType": "quantum_computer", "properties": {"name": "q"}}},
    ]
    files = gen.generate(nodes, [], "Skips")
    main = next(f.content for f in files if f.filename == "main.tf")
    assert 'resource "aws_vpc" "net"' in main
    assert "Skipped 'quantum_computer'" in main


def test_aws_name_sanitizes_for_aws():
    # underscores (from slugs) and other invalid chars become hyphens
    assert aws_name("app_lb") == "app-lb"
    assert aws_name("app_lb-tg") == "app-lb-tg"
    assert aws_name("My_Bucket.Name!") == "my-bucket-name"
    # collapses repeats and trims edges
    assert aws_name("__a__b__") == "a-b"
    # falls back when empty
    assert aws_name("___") == "resource"
    # respects max_len (default 32, the LB/TG limit)
    assert len(aws_name("a" * 50)) == 32
    assert len(aws_name("a" * 50, 63)) == 50


def test_security_group_infers_vpc_from_protected_resources():
    """A SG attached to an EC2 in a designed VPC must be pinned to that VPC.
    Otherwise AWS creates it in the account default VPC and EC2 launch fails
    with 'security group and subnet belong to different networks'."""
    gen = AWSTerraformGenerator()
    nodes = [
        {"id": "vpc1", "type": "vpc", "data": {"resourceType": "vpc", "properties": {"name": "app_vpc"}}},
        {"id": "sub1", "type": "subnet", "data": {"resourceType": "subnet", "properties": {"name": "app_subnet"}}},
        {"id": "ec21", "type": "ec2", "data": {"resourceType": "ec2", "properties": {"name": "web"}}},
        {"id": "sg1", "type": "security_group", "data": {"resourceType": "security_group", "properties": {"name": "web_sg"}}},
    ]
    edges = [
        {"source": "vpc1", "target": "sub1"},
        {"source": "sub1", "target": "ec21"},
        {"source": "sg1", "target": "ec21"},
    ]
    files = gen.generate(nodes, edges, "SGTest")
    main = next(f.content for f in files if f.filename == "main.tf")
    # The SG block must reference the designed VPC (not be omitted).
    assert 'vpc_id      = aws_vpc.app_vpc.id' in main
    assert 'vpc_security_group_ids = [aws_security_group.web_sg.id]' in main


def test_subnets_span_azs_and_db_subnet_group_is_vpc_scoped():
    """Subnets in a VPC must land in different AZs (RDS subnet groups require
    ≥2 AZs), and a DB subnet group must only reference subnets from its own
    VPC — not every subnet in the design."""
    gen = AWSTerraformGenerator()
    nodes = [
        {"id": "vpc1", "type": "vpc", "data": {"resourceType": "vpc", "properties": {"name": "net-a"}}},
        {"id": "sub1", "type": "subnet", "data": {"resourceType": "subnet", "properties": {"name": "subnet-a"}}},
        {"id": "sub2", "type": "subnet", "data": {"resourceType": "subnet", "properties": {"name": "subnet-b"}}},
        {"id": "vpc2", "type": "vpc", "data": {"resourceType": "vpc", "properties": {"name": "net-b"}}},
        {"id": "sub3", "type": "subnet", "data": {"resourceType": "subnet", "properties": {"name": "subnet-c"}}},
        {"id": "db", "type": "rds", "data": {"resourceType": "rds", "properties": {
            "identifier": "app-db", "engine": "mysql", "instanceClass": "db.t3.micro",
        }}},
    ]
    edges = [
        {"source": "vpc1", "target": "sub1"},
        {"source": "vpc1", "target": "sub2"},
        {"source": "vpc2", "target": "sub3"},
        {"source": "sub1", "target": "db"},
    ]
    main = next(f.content for f in gen.generate(nodes, edges, "AZApp") if f.filename == "main.tf")

    # Two subnets in the same VPC must be spread across two AZs.
    assert 'availability_zone = "us-east-1a"' in main
    assert 'availability_zone = "us-east-1b"' in main

    # The DB subnet group must contain only the RDS VPC's subnets.
    db_block = main.split('resource "aws_db_subnet_group"')[1]
    assert "aws_subnet.subnet_a.id" in db_block
    assert "aws_subnet.subnet_b.id" in db_block
    assert "aws_subnet.subnet_c.id" not in db_block


def test_region_aware_fallbacks_for_ec2_and_ebs():
    """Fallbacks must use the deployment region and the Free-Tier t3.micro,
    not a hardcoded us-east-1a / t2.micro that breaks in other regions."""
    gen = AWSTerraformGenerator()
    nodes = [
        {"id": "vpc1", "type": "vpc", "data": {"resourceType": "vpc", "properties": {"name": "vpc"}}},
        {"id": "sub1", "type": "subnet", "data": {"resourceType": "subnet", "properties": {"name": "subnet"}}},
        {"id": "ec2x", "type": "ec2", "data": {"resourceType": "ec2", "properties": {"name": "web"}}},
        {"id": "vol", "type": "ebs_volume", "data": {"resourceType": "ebs_volume", "properties": {"name": "data", "size": 8}}},
    ]
    edges = [{"source": "vpc1", "target": "sub1"}, {"source": "sub1", "target": "ec2x"}]
    files = gen.generate(nodes, edges, "Fallback", aws_region="eu-west-1")
    variables = next(f.content for f in files if f.filename == "variables.tf")
    main = next(f.content for f in files if f.filename == "main.tf")
    assert 'default     = "t3.micro"' in variables
    assert 'availability_zone = "eu-west-1a"' in main


def test_templates_use_provider_valid_arguments():
    """Guards against arguments the AWS provider rejects (found by running the
    real `terraform validate` over the generated output)."""
    gen = AWSTerraformGenerator()

    sqs = gen.generate(
        [{"id": "q", "type": "sqs", "data": {"resourceType": "sqs", "properties": {"name": "q"}}}],
        [], "SQS",
    )
    sqs_main = next(f.content for f in sqs if f.filename == "main.tf")
    assert "max_message_size" in sqs_main
    assert "maximum_message_size" not in sqs_main

    aurora = gen.generate(
        [{"id": "a", "type": "aurora", "data": {"resourceType": "aurora", "properties": {
            "identifier": "a", "engine": "aurora-mysql"}}}],
        [], "Aurora",
    )
    aurora_main = next(f.content for f in aurora if f.filename == "main.tf")
    assert "manage_master_user_password = true" in aurora_main
    assert "manage_master_password" not in aurora_main

    efs_nodes = [
        {"id": "vpc1", "type": "vpc", "data": {"resourceType": "vpc", "properties": {"name": "v"}}},
        {"id": "sub1", "type": "subnet", "data": {"resourceType": "subnet", "properties": {"name": "s"}}},
        {"id": "efs1", "type": "efs", "data": {"resourceType": "efs", "properties": {"name": "files"}}},
    ]
    efs_edges = [{"source": "vpc1", "target": "sub1"}, {"source": "sub1", "target": "efs1"}]
    efs_main = next(f.content for f in gen.generate(efs_nodes, efs_edges, "EFS") if f.filename == "main.tf")
    mount_block = efs_main.split('resource "aws_efs_mount_target"')[1].split("resource ")[0]
    assert "tags = {" not in mount_block  # aws_efs_mount_target has no tags argument


def test_ebs_volume_matches_instance_subnet_az():
    """An EBS volume must be created in the same AZ as the instance it attaches
    to; it takes the AZ of the instance's subnet."""
    gen = AWSTerraformGenerator()
    nodes = [
        {"id": "vpc1", "type": "vpc", "data": {"resourceType": "vpc", "properties": {"name": "v"}}},
        {"id": "s1", "type": "subnet", "data": {"resourceType": "subnet", "properties": {"name": "sub-a"}}},
        {"id": "s2", "type": "subnet", "data": {"resourceType": "subnet", "properties": {"name": "sub-b"}}},
        {"id": "ec2x", "type": "ec2", "data": {"resourceType": "ec2", "properties": {"name": "web"}}},
        {"id": "vol", "type": "ebs_volume", "data": {"resourceType": "ebs_volume", "properties": {"name": "data", "size": 8}}},
    ]
    edges = [
        {"source": "vpc1", "target": "s1"},
        {"source": "vpc1", "target": "s2"},
        {"source": "s2", "target": "ec2x"},
        {"source": "ec2x", "target": "vol"},
    ]
    main = next(f.content for f in gen.generate(nodes, edges, "EBS") if f.filename == "main.tf")
    ebs_block = main.split('resource "aws_ebs_volume"')[1].split("resource ")[0]
    assert 'availability_zone = "us-east-1b"' in ebs_block


def test_ec2_custom_ami_is_used_when_provided():
    gen = AWSTerraformGenerator()
    nodes = [
        {"id": "vpc1", "type": "vpc", "data": {"resourceType": "vpc", "properties": {"name": "v"}}},
        {"id": "sub1", "type": "subnet", "data": {"resourceType": "subnet", "properties": {"name": "s"}}},
        {"id": "ec21", "type": "ec2", "data": {"resourceType": "ec2", "properties": {
            "name": "web", "amiId": "ami-0720cb7af233b0529"}}},
    ]
    edges = [{"source": "vpc1", "target": "sub1"}, {"source": "sub1", "target": "ec21"}]
    main = next(f.content for f in gen.generate(nodes, edges, "AMI") if f.filename == "main.tf")
    assert 'ami           = "ami-0720cb7af233b0529"' in main


def test_ec2_defaults_to_latest_ami_when_no_custom():
    gen = AWSTerraformGenerator()
    nodes = [
        {"id": "ec21", "type": "ec2", "data": {"resourceType": "ec2", "properties": {"name": "web"}}},
    ]
    main = next(f.content for f in gen.generate(nodes, [], "AMI2") if f.filename == "main.tf")
    assert "data.aws_ami.amazon_linux.id" in main


def test_ami_lookup_omitted_when_every_ec2_has_custom_ami():
    gen = AWSTerraformGenerator()
    nodes = [
        {"id": "ec21", "type": "ec2", "data": {"resourceType": "ec2", "properties": {
            "name": "web", "amiId": "ami-0720cb7af233b0529"}}},
    ]
    files = gen.generate(nodes, [], "AMIOnly")
    providers = next(f.content for f in files if f.filename == "providers.tf")
    main = next(f.content for f in files if f.filename == "main.tf")
    assert "data.aws_ami" not in providers
    assert 'ami           = "ami-0720cb7af233b0529"' in main


def test_ami_lookup_present_when_an_ec2_has_no_custom_ami():
    gen = AWSTerraformGenerator()
    nodes = [
        {"id": "ec21", "type": "ec2", "data": {"resourceType": "ec2", "properties": {"name": "web"}}},
    ]
    files = gen.generate(nodes, [], "AMIDefault")
    providers = next(f.content for f in files if f.filename == "providers.tf")
    assert 'data "aws_ami" "amazon_linux"' in providers


def test_unimplemented_providers_raise_clear_error():
    import pytest

    from app.terraform.generator import get_generator

    with pytest.raises(NotImplementedError) as exc:
        get_generator("azure").generate([], [], "proj")
    assert "Azure" in str(exc.value)
    with pytest.raises(ValueError):
        get_generator("oracle")
