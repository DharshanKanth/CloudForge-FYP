"""Tests for the deterministic architecture-diagram importer."""
import base64
import json
import urllib.parse
import zlib

import pytest

from app.services.diagram_import import DiagramParseError, detect_format, import_diagram
from app.services.diagram_import.mapping import classify_label, classify_style


# ── classification (pure) ────────────────────────────────────────────────────

@pytest.mark.parametrize("label,expected", [
    ("EC2 Instance", "ec2"),
    ("Web Server", "ec2"),
    ("Amazon S3 Bucket", "s3"),
    ("Application Load Balancer", "load_balancer"),
    ("Public Subnet", "subnet"),
    ("VPC", "vpc"),
    ("RDS Database", "rds"),
    ("Aurora Cluster", "aurora"),
    ("AWS WAF", None),
    ("EKS Cluster", None),
])
def test_classify_label(label, expected):
    assert classify_label(label) == expected


def test_classify_style_drawio_icons():
    assert classify_style("shape=mxgraph.aws4.group;grIcon=mxgraph.aws4.group_vpc;") == "vpc"
    assert classify_style("shape=mxgraph.aws4.group_subnet") == "subnet"
    assert classify_style("shape=mxgraph.aws4.resourceIcon;resIcon=mxgraph.aws4.ec2;") == "ec2"
    assert classify_style("shape=mxgraph.aws4.elastic_load_balancing") == "load_balancer"


# ── draw.io ──────────────────────────────────────────────────────────────────

DRAWIO_XML = """<mxfile host="app.diagrams.net">
  <diagram name="Page-1" id="p1">
    <mxGraphModel>
      <root>
        <mxCell id="0" />
        <mxCell id="1" parent="0" />
        <mxCell id="vpc" value="VPC" style="shape=mxgraph.aws4.group;grIcon=mxgraph.aws4.group_vpc;" vertex="1" parent="1">
          <mxGeometry x="40" y="40" width="600" height="400" as="geometry" />
        </mxCell>
        <mxCell id="subnet" value="Public Subnet" style="shape=mxgraph.aws4.group;grIcon=mxgraph.aws4.group_subnet;" vertex="1" parent="vpc">
          <mxGeometry x="40" y="60" width="300" height="250" as="geometry" />
        </mxCell>
        <mxCell id="ec2" value="Web Server" style="shape=mxgraph.aws4.resourceIcon;resIcon=mxgraph.aws4.ec2;" vertex="1" parent="subnet">
          <mxGeometry x="40" y="60" width="78" height="78" as="geometry" />
        </mxCell>
        <mxCell id="s3" value="Static Assets" style="shape=mxgraph.aws4.resourceIcon;resIcon=mxgraph.aws4.s3;" vertex="1" parent="1">
          <mxGeometry x="700" y="80" width="78" height="78" as="geometry" />
        </mxCell>
      </root>
    </mxGraphModel>
  </diagram>
</mxfile>"""


def test_import_drawio_hierarchy_becomes_containment_edges():
    result = import_diagram("arch.drawio", DRAWIO_XML)
    assert result["format"] == "drawio"
    by_id = {n["id"]: n for n in result["nodes"]}
    assert by_id["ec2"]["data"]["resourceType"] == "ec2"
    assert by_id["ec2"]["data"]["properties"]["instanceType"] == "t3.micro"
    assert by_id["vpc"]["data"]["properties"]["cidr"] == "10.0.0.0/16"
    assert by_id["subnet"]["data"]["properties"]["cidr"].startswith("10.0.")
    pairs = {(e["source"], e["target"]) for e in result["edges"]}
    assert ("vpc", "subnet") in pairs
    assert ("subnet", "ec2") in pairs
    assert result["validation"] is not None


def test_import_drawio_compressed_page():
    model = (
        '<mxGraphModel><root><mxCell id="0"/><mxCell id="1" parent="0"/>'
        '<mxCell id="ec2" value="Web Server" style="shape=mxgraph.aws4.ec2" vertex="1" parent="1">'
        '<mxGeometry x="0" y="0" width="78" height="78" as="geometry"/></mxCell>'
        '</root></mxGraphModel>'
    )
    compressor = zlib.compressobj(9, zlib.DEFLATED, -15)
    raw = compressor.compress(model.encode("utf-8")) + compressor.flush()
    encoded = urllib.parse.quote(base64.b64encode(raw).decode("ascii"), safe="")
    xml = f'<mxfile><diagram id="p1">{encoded}</diagram></mxfile>'
    result = import_diagram("compressed.drawio", xml)
    assert any(n["data"]["resourceType"] == "ec2" for n in result["nodes"])


# ── Mermaid ──────────────────────────────────────────────────────────────────

MERMAID = """flowchart TD
  subgraph vpc1[VPC]
    subgraph sub1[Public Subnet]
      web[Web Server]
    end
  end
  lb[Load Balancer]
  db[(Database)]
  lb --> web
"""


def test_import_mermaid_subgraphs_and_edges():
    result = import_diagram("arch.mmd", MERMAID)
    assert result["format"] == "mermaid"
    types = {n["id"]: n["data"]["resourceType"] for n in result["nodes"]}
    assert types["web"] == "ec2"
    assert types["db"] == "rds"
    assert types["lb"] == "load_balancer"
    assert types["vpc1"] == "vpc"
    assert types["sub1"] == "subnet"
    pairs = {(e["source"], e["target"]) for e in result["edges"]}
    assert ("vpc1", "sub1") in pairs
    assert ("sub1", "web") in pairs
    assert ("lb", "web") in pairs


# ── JSON ─────────────────────────────────────────────────────────────────────

def test_import_json_reports_unsupported_types():
    payload = {
        "nodes": [
            {"id": "v1", "resourceType": "vpc", "properties": {"name": "main", "cidr": "10.0.0.0/16"}},
            {"id": "s1", "resourceType": "subnet", "properties": {"name": "pub", "cidr": "10.0.1.0/24"}},
            {"id": "w1", "resourceType": "waf", "properties": {}},
        ],
        "edges": [{"source": "v1", "target": "s1"}],
    }
    result = import_diagram("arch.json", json.dumps(payload))
    assert result["format"] == "json"
    ids = {n["id"] for n in result["nodes"]}
    assert {"v1", "s1"} <= ids
    assert "w1" not in ids
    assert any(u["label"] == "w1" for u in result["unrecognized"])


def test_import_json_falls_back_to_label_classification():
    payload = {"nodes": [{"id": "db", "label": "Database"}], "edges": []}
    result = import_diagram("arch.json", json.dumps(payload))
    assert result["nodes"][0]["data"]["resourceType"] == "rds"


# ── format detection ─────────────────────────────────────────────────────────

def test_detect_format_rejects_unknown():
    with pytest.raises(DiagramParseError):
        detect_format("diagram.png", "not a diagram")


def test_detect_format_recognises_each():
    assert detect_format("a.drawio", DRAWIO_XML) == "drawio"
    assert detect_format("a.mmd", MERMAID) == "mermaid"
    assert detect_format("a.json", '{"nodes": [], "edges": []}') == "json"
