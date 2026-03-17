import json
import subprocess
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

import requests
from airflow.operators.python import PythonOperator
from reportlab.pdfgen import canvas

from airflow import DAG

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2023, 1, 1),
    'retries': 1,
    'retry_delay': timedelta(minutes=1),
}

dag = DAG(
    'generate_real_documents',
    default_args=default_args,
    description='Generate test PDFs based on real enterprise data from the API',
    schedule_interval=None,  # Run manually
    catchup=False
)

def create_pdf(filename, content):
    c = canvas.Canvas(str(filename))
    y = 800
    for line in content:
        c.drawString(100, y, str(line))
        y -= 25
    c.save()

def fetch_data_and_generate_pdfs(**kwargs):
    # Retrieve the search query from Airflow UI params, default to "orange"
    query = kwargs.get('dag_run').conf.get('query', 'orange') if kwargs.get('dag_run') and kwargs.get('dag_run').conf else 'orange'
    
    url = f"https://recherche-entreprises.api.gouv.fr/search?q={query}&per_page=1"
    print(f"Fetching real data for '{query}' from: {url}")
    
    response = requests.get(url)
    response.raise_for_status()
    data = response.json()
    
    output_dir = Path("/opt/airflow/test_documents")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    results = data.get("results", [])
    
    if not results:
        print(f"No results found for query: {query}")
        return

    # Take only the first result to avoid generating too many documents
    entreprise = results[0]
    
    nom = entreprise.get("nom_complet", "ENTREPRISE_INCONNUE")
    siren = entreprise.get("siren", "INCONNU")
    
    siege = entreprise.get("siege", {})
    siret = siege.get("siret", "INCONNU")
    adresse = siege.get("adresse", "Adresse Inconnue")
    
    current_date = datetime.now().strftime('%Y-%m-%d')
    
    # 1. Generation: Valid invoice (FACTURE)
    filename_valid_invoice = output_dir / f"facture_valid_{query}_{siren}.pdf"
    create_pdf(filename_valid_invoice, [
        "FACTURE N° F-2026-04-10023",
        "--------------------------------------------------",
        f"EMETTEUR:",
        f"Raison Sociale: {nom}",
        f"SIRET: {siret}",
        f"Adresse: {adresse}",
        "",
        "CLIENT:",
        "Nom: SARL DUPONT & CO",
        "Adresse: 12 Rue de la Paix, 75001 PARIS",
        "SIRET: 40483304800022",
        "",
        f"Date d'emission: {current_date}",
        "Date d'echeance: " + (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d'),
        "--------------------------------------------------",
        "DESCRIPTION DES PRESTATIONS:",
        "- Developpement logiciel sur mesure         : 2 500.00 EUR",
        "- Maintenance serveur (Avril)               :   450.00 EUR",
        "- Licence annuelle Cloud                    : 1 200.00 EUR",
        "--------------------------------------------------",
        "Total HT                                  : 4 150.00 EUR",
        "TVA (20%)                                 :   830.00 EUR",
        "--------------------------------------------------",
        "TOTAL TTC A PAYER                         : 4 980.00 EUR"
    ])
    print(f"Generated {filename_valid_invoice.name}")
    
    # 2. Generation: Fake/Fraud invoice (FACTURE)
    filename_fake_invoice = output_dir / f"facture_fake_{query}_{siren}.pdf"
    fake_siret = siret[:-4] + "9999" if len(siret) > 4 else "99999999999999"
    create_pdf(filename_fake_invoice, [
        "FACTURE N° F-2026-04-10099",
        "--------------------------------------------------",
        f"EMETTEUR:",
        f"Raison Sociale: {nom}",
        f"SIRET: {fake_siret}",
        f"Adresse: {adresse}",
        "",
        "CLIENT:",
        "Nom: SARL DUPONT & CO",
        "Adresse: 12 Rue de la Paix, 75001 PARIS",
        "SIRET: 40483304800022",
        "",
        f"Date d'emission: {current_date}",
        "Date d'echeance: " + current_date, # Date echeance suspecte car immediate
        "--------------------------------------------------",
        "DESCRIPTION DES PRESTATIONS:",
        "- Frais de recouvrement exceptionnels       :14 500.00 EUR",
        "- Ajustement honoraires                     : 2 000.00 EUR",
        "--------------------------------------------------",
        "Total HT                                  :16 500.00 EUR",
        "TVA (20%)                                 : 3 300.00 EUR",
        "--------------------------------------------------",
        "TOTAL TTC A PAYER                         :19 800.00 EUR"
    ])
    print(f"Generated {filename_fake_invoice.name}")
    
    # 3. Generation: Valid quote (DEVIS)
    filename_valid_quote = output_dir / f"devis_valid_{query}_{siren}.pdf"
    create_pdf(filename_valid_quote, [
        "PROPOSITION COMMERCIALE / DEVIS N° D-2026-05-554",
        "--------------------------------------------------",
        f"EMETTEUR:",
        f"Raison Sociale: {nom}",
        f"SIRET: {siret}",
        f"Adresse: {adresse}",
        "",
        "POUR LE CLIENT:",
        "Nom: COMMUNE DE LYON",
        "Adresse: Place de la Comedie, 69001 LYON",
        "",
        f"Date d'emission: {current_date}",
        "Duree de validite du devis: 60 jours",
        "--------------------------------------------------",
        "DETAILS DE L'OFFRE:",
        "- Etude de faisabilite technique            : 1 800.00 EUR",
        "- Deploiement phase 1                       : 3 200.00 EUR",
        "- Formation des equipes (2 jours)           : " + ("1 500.00 EUR (Exonere de TVA)"),
        "--------------------------------------------------",
        "Total HT                                  : 6 500.00 EUR",
        "TVA applicables                           : 1 000.00 EUR",
        "--------------------------------------------------",
        "TOTAL DEVIS TTC                           : 7 500.00 EUR",
        "",
        "Bon pour accord le:",
        "Signature et Cachet du client:"
    ])
    print(f"Generated {filename_valid_quote.name}")

    # 4. Generation: Valid SIRET but wrong legal name
    filename_wrong_name_invoice = output_dir / f"facture_wrong_name_valid_siret_{query}_{siren}.pdf"
    create_pdf(filename_wrong_name_invoice, [
        "FACTURE N° F-2026-04-10145",
        "--------------------------------------------------",
        f"EMETTEUR:",
        "Raison Sociale: ALPHA GLOBAL ADVISORY",
        f"SIRET: {siret}",
        f"Adresse: {adresse}",
        "",
        "CLIENT:",
        "Nom: SARL DUPONT & CO",
        "Adresse: 12 Rue de la Paix, 75001 PARIS",
        "SIRET: 40483304800022",
        "",
        f"Date d'emission: {current_date}",
        "Date d'echeance: " + (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d'),
        "--------------------------------------------------",
        "DESCRIPTION DES PRESTATIONS:",
        "- Audit interne                             : 2 000.00 EUR",
        "- Rapport de synthese                       :   600.00 EUR",
        "--------------------------------------------------",
        "Total HT                                  : 2 600.00 EUR",
        "TVA (20%)                                 :   520.00 EUR",
        "--------------------------------------------------",
        "TOTAL TTC A PAYER                         : 3 120.00 EUR"
    ])
    print(f"Generated {filename_wrong_name_invoice.name}")

    # 5. Generation: Valid SIRET but wrong address
    filename_wrong_address_invoice = output_dir / f"facture_wrong_address_valid_siret_{query}_{siren}.pdf"
    create_pdf(filename_wrong_address_invoice, [
        "FACTURE N° F-2026-04-10146",
        "--------------------------------------------------",
        f"EMETTEUR:",
        f"Raison Sociale: {nom}",
        f"SIRET: {siret}",
        "Adresse: 99 AVENUE DES FAUSSES DONNEES 13001 MARSEILLE",
        "",
        "CLIENT:",
        "Nom: SARL DUPONT & CO",
        "Adresse: 12 Rue de la Paix, 75001 PARIS",
        "SIRET: 40483304800022",
        "",
        f"Date d'emission: {current_date}",
        "Date d'echeance: " + (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d'),
        "--------------------------------------------------",
        "DESCRIPTION DES PRESTATIONS:",
        "- Supervision projet                        : 1 800.00 EUR",
        "- Support prioritaire                        :   700.00 EUR",
        "--------------------------------------------------",
        "Total HT                                  : 2 500.00 EUR",
        "TVA (20%)                                 :   500.00 EUR",
        "--------------------------------------------------",
        "TOTAL TTC A PAYER                         : 3 000.00 EUR"
    ])
    print(f"Generated {filename_wrong_address_invoice.name}")

generate_task = PythonOperator(
    task_id='fetch_and_generate',
    python_callable=fetch_data_and_generate_pdfs,
    provide_context=True,
    dag=dag,
)
