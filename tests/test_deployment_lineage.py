from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_deployment_lineage_records_all_branch_baselines() -> None:
    lineage_path = ROOT / "docs" / "deployment-lineage.md"
    assert lineage_path.is_file(), "缺少 deployment lineage 文件"
    readme_path = ROOT / "README.md"
    hosting_path = ROOT / "docs" / "hosting.md"
    assert readme_path.is_file(), "缺少 README 文件"
    assert hosting_path.is_file(), "缺少 hosting 文件"

    text = lineage_path.read_text(encoding="utf-8")
    readme_text = readme_path.read_text(encoding="utf-8")
    hosting_text = hosting_path.read_text(encoding="utf-8")
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
    public_entry_points = (
        (readme_text, "Tests-586%20passed-success"),
        (
            readme_text,
            "https://github.com/kuotunyu/ltc-benefit-agent/blob/main/docs/deployment-lineage.md",
        ),
        (hosting_text, "(deployment-lineage.md)"),
    )

    for marker in (*required_sections, *required_refs):
        assert marker in text, f"deployment lineage 缺少必要標記：{marker}"
    for source_text, marker in public_entry_points:
        assert marker in source_text, f"公開入口缺少必要標記：{marker}"
    assert "](docs/deployment-lineage.md)" not in readme_text, (
        "README 不應使用相對 deployment lineage 連結"
    )
    assert "release-checklist" not in hosting_text, (
        "hosting 文件不應依賴已移除的 release checklist"
    )
