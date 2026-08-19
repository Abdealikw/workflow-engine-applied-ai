import pytest
from src.api.schemas import DAG, Node

def test_valid_dag():
    dag = DAG(nodes=[
        Node(id="A", handler="input", dependencies=[]),
        Node(id="B", handler="process", dependencies=["A"]),
        Node(id="C", handler="output", dependencies=["B"])
    ])
    assert len(dag.nodes) == 3

def test_missing_dependency():
    with pytest.raises(ValueError, match="does not exist"):
        DAG(nodes=[
            Node(id="A", handler="input", dependencies=["Z"])
        ])

def test_cycle_detection():
    with pytest.raises(ValueError, match="Cycle detected"):
        DAG(nodes=[
            Node(id="A", handler="input", dependencies=["C"]),
            Node(id="B", handler="process", dependencies=["A"]),
            Node(id="C", handler="output", dependencies=["B"])
        ])

def test_self_loop():
    with pytest.raises(ValueError, match="Cycle detected"):
        DAG(nodes=[
            Node(id="A", handler="input", dependencies=["A"])
        ])

def test_fan_out_fan_in():
    dag = DAG(nodes=[
        Node(id="A", handler="input", dependencies=[]),
        Node(id="B", handler="process", dependencies=["A"]),
        Node(id="C", handler="process", dependencies=["A"]),
        Node(id="D", handler="output", dependencies=["B", "C"])
    ])
    assert len(dag.nodes) == 4
