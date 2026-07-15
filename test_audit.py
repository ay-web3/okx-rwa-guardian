"""Quick test: run static analysis on the vulnerable vault contract."""
import sys
import os
sys.path.insert(0, r"C:\Users\HP\Desktop\okx")
os.environ["PYTHONIOENCODING"] = "utf-8"

from backend.analyzer.static_analysis import StaticAnalyzer
from backend.analyzer.report_generator import ReportGenerator

# Load safe contract
with open(r"C:\Users\HP\Desktop\okx\tests\contracts\flash_loan_receiver.sol", "r", encoding="utf-8") as f:
    source_code = f.read()

# Run static analysis
analyzer = StaticAnalyzer()
findings = analyzer.analyze(source_code)

print(f"\n{'='*60}")
print(f"  HACK MY CONTRACT - Static Analysis Results")
print(f"{'='*60}\n")
print(f"  Findings: {len(findings)}\n")

severity_icons = {"CRITICAL": "[!!]", "HIGH": "[!]", "MEDIUM": "[~]", "LOW": "[.]", "INFO": "[i]"}

for f in findings:
    severity = f["severity"]
    icon = severity_icons.get(severity, "[?]")
    print(f"  {icon} [{severity}] {f['id']}: {f['title']}")
    snippet = f['location']['code_snippet'][:80].encode('ascii', 'replace').decode()
    print(f"     Line {f['location']['line_number']}: {snippet}")
    print()

# Generate full report
report_gen = ReportGenerator()
report = report_gen.generate(
    contract_name="VulnerableVault",
    source_code=source_code,
    static_findings=findings,
    llm_findings=[],
)

print(f"{'='*60}")
print(f"  REPORT SUMMARY")
print(f"{'='*60}")
print(f"  Risk Score: {report['overall_risk_score']}/100")
print(f"  Risk Level: {report['risk_level']}")
print(f"  Critical:   {report['summary']['critical']}")
print(f"  High:       {report['summary']['high']}")
print(f"  Medium:     {report['summary']['medium']}")
print(f"  Low:        {report['summary']['low']}")
print(f"  Info:       {report['summary']['info']}")
print()

# Save markdown report
with open(r"C:\Users\HP\Desktop\okx\test_report.md", "w", encoding="utf-8") as f:
    f.write(report["markdown_report"])
print(f"  >> Full report saved to test_report.md")
