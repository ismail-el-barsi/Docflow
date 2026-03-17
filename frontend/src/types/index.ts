// Interfaces TypeScript — miroir des schemas Pydantic

export type UserRole = 'admin' | 'user';

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: User;
}


export type DocumentType = 'facture' | 'devis' | 'attestation' | 'autre';

export type ProcessingStatus =
  | 'uploaded'
  | 'processing'
  | 'extracted'
  | 'curated'
  | 'error';

export interface DocumentResponse {
  id: string;
  filename: string;
  original_filename: string;
  status: ProcessingStatus;
  document_type: DocumentType | null;
  upload_at: string;
  error_message: string | null;
  uploaded_by: string | null;
}

export interface MonetaryAmount {
  ht: number | null;
  tva: number | null;
  ttc: number | null;
  currency: string;
}

export interface ExtractionResult {
  siren: string | null;
  siret: string | null;
  emetteur_nom: string | null;
  emetteur_adresse: string | null;
  destinataire_nom: string | null;
  destinataire_adresse: string | null;
  montants: MonetaryAmount;
  date_emission: string | null;
  date_echeance: string | null;
  numero_document: string | null;
  raw_text: string;
}

export type AlertType =
  | 'siret_mismatch'
  | 'amount_inconsistency'
  | 'date_incoherence'
  | 'siren_format_invalid';

export type AlertSeverity = 'critique' | 'haute' | 'moyenne' | 'faible';

export interface InconsistencyAlert {
  id: string;
  alert_type: AlertType;
  severity: AlertSeverity;
  description: string;
  document_ids: string[];
  field_in_conflict: string | null;
  value_a: string | null;
  value_b: string | null;
  suggestion: string | null;
}

export interface SupplierSummary {
  siren: string;
  nom: string;
  nombre_documents: number;
  total_ttc: number;
  a_des_alertes: boolean;
  types_documents: string[];
}

export interface ComplianceDashboard {
  total_documents: number;
  documents_conformes: number;
  documents_non_conformes: number;
  taux_conformite: number;
  alertes_critiques: number;
  alertes_hautes: number;
  alertes_moyennes: number;
  alertes_totales: number;
}

export interface GoldRecord {
  document_id: string;
  original_filename: string;
  document_type: DocumentType;
  extraction: ExtractionResult;
  alerts: InconsistencyAlert[];
  is_compliant: boolean;
  curated_at: string;
}
