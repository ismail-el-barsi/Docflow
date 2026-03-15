from reportlab.pdfgen import canvas
from pathlib import Path

def create_pdf(filename, content):
    c = canvas.Canvas(str(filename))
    y = 800
    for line in content:
        c.drawString(100, y, line)
        y -= 20
    c.save()

output_dir = Path("/Users/abdallahnassur/Ipssi/cours/semaine_hackathon/test_documents")
output_dir.mkdir(exist_ok=True)

# 1. SIRET Mismatch (Acme Corp)
create_pdf(output_dir / "facture_acme.pdf", [
    "FACTURE",
    "Emetteur: ACME CORP",
    "SIRET: 12345678900010",
    "Date: 2026-03-01",
    "Montant TTC: 1200.00 EUR",
    "Description: Services de consultation"
])

create_pdf(output_dir / "attestation_acme_error.pdf", [
    "ATTESTATION VIGILANCE",
    "L'entreprise ACME CORP",
    "SIRET: 99999999900099",  # Different SIRET
    "est a jour de ses cotisations.",
    "Fait le 2026-02-15"
])

# 2. Amount Mismatch (Tech solutions)
create_pdf(output_dir / "devis_tech.pdf", [
    "DEVIS D2026-01",
    "Emetteur: TECH SOLUTIONS",
    "SIRET: 55566677700011",
    "Date: 2026-01-10",
    "Montant TTC: 1000.00",
    "Objet: Installation reseau"
])

create_pdf(output_dir / "facture_tech_fraud.pdf", [
    "FACTURE F2026-01",
    "Emetteur: TECH SOLUTIONS",
    "SIRET: 55566677700011",
    "Date: 2026-02-10",
    "Montant TTC: 5000.00", # 5x the quote
    "Objet: Installation reseau (suite)"
])

# 3. Date Mismatch (Early Bird)
create_pdf(output_dir / "devis_early.pdf", [
    "DEVIS",
    "Entreprise: EARLY BIRD",
    "Date: 2026-06-01",
    "Montant: 500.00"
])

create_pdf(output_dir / "facture_early_wrong_date.pdf", [
    "FACTURE",
    "Entreprise: EARLY BIRD",
    "Date: 2026-01-01", # Before devis
    "Montant: 500.00"
])

# 4. Invalid SIREN (Bad Format)
create_pdf(output_dir / "facture_bad_siren.pdf", [
    "FACTURE",
    "Emetteur: BAD SIREN ENT",
    "SIREN: 123-456 (Invalid)",
    "Montant: 100.00"
])

print(f"Generated test PDFs in {output_dir}")
