from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_deployment_lineage_records_all_branch_baselines() -> None:
    lineage_path = ROOT / "docs" / "deployment-lineage.md"
    assert lineage_path.is_file(), "缺少 deployment lineage 文件"

    text = lineage_path.read_text(encoding="utf-8")
    required_sections = (
        "## GitHub source branch",
        "## Hugging Face Space branch",
        "## Why local main differs",
        "## Rule snapshot boundary",
        "## Safe update procedure",
    )
    required_refs = (
        "79fa210cdb1b0258b6e8475e00c78083f67eb014",
        "c710b0c34e244424b4c03408ea298fcf3d46cbfe",
        "2b71b85f25d50567506b73885590f6dec95e088e",
    )

    for marker in (*required_sections, *required_refs):
        assert marker in text, f"deployment lineage 缺少必要標記：{marker}"
