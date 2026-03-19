import { useCallback, useEffect, useRef, useState } from 'react';
import {
  uploadDocuments,
  listDocuments,
  getExtraction,
  deleteDocument,
  getApiErrorMessage,
} from '../api/client';
import type { DocumentResponse, ExtractionResult } from '../types';
import { useAuth } from '../context/AuthContext';

const STATUS_LABELS: Record<string, string> = {
  uploaded: '📦 Uploadé',
  processing: '⚙️ Traitement…',
  extracted: '🔍 Extrait',
  curated: '✅ Curé',
  error: '❌ Erreur',
};

const TYPE_LABELS: Record<string, string> = {
  facture: 'Facture',
  devis: 'Devis',
  attestation: 'Attestation',
  autre: 'Autre',
};

const ACCEPTED_MIME_TYPES = new Set([
  'application/pdf',
  'application/msword',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
]);

const ACCEPTED_EXTENSIONS = ['.pdf', '.doc', '.docx'];
const INPUT_ACCEPT = '.pdf,.doc,.docx,image/*';

function isAcceptedUploadFile(file: File): boolean {
  if (file.type.startsWith('image/')) {
    return true;
  }

  if (ACCEPTED_MIME_TYPES.has(file.type)) {
    return true;
  }

  const lowerName = file.name.toLowerCase();
  return ACCEPTED_EXTENSIONS.some((ext) => lowerName.endsWith(ext));
}

export function UploadPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === 'admin';
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [documents, setDocuments] = useState<DocumentResponse[]>([]);
  const [uploadedFiles, setUploadedFiles] = useState<string[]>([]);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [selectedDoc, setSelectedDoc] = useState<DocumentResponse | null>(null);
  const [extraction, setExtraction] = useState<ExtractionResult | null>(null);
  const [loadingExtraction, setLoadingExtraction] = useState(false);
  
  const inputRef = useRef<HTMLInputElement>(null);

  // Polling for documents not yet in final state
  useEffect(() => {
    const needsPolling = documents.some(
      (d) => !['curated', 'error'].includes(d.status)
    );

    if (needsPolling) {
      const timer = setInterval(refreshDocuments, 3000);
      return () => clearInterval(timer);
    }
  }, [documents]);

  // Initial load
  useEffect(() => {
    refreshDocuments();
  }, []);

  const handleFiles = async (files: FileList | File[]) => {
    const candidateFiles = Array.from(files).filter(isAcceptedUploadFile);
    if (candidateFiles.length === 0) {
      setUploadError('Format non supporté. Merci d\'envoyer des PDF, DOC/DOCX ou images.');
      return;
    }

    setUploadError(null);
    setUploading(true);
    try {
      const result = await uploadDocuments(candidateFiles);
      setUploadedFiles(result.map((d) => d.original_filename));
      await refreshDocuments();
    } catch (err) {
      console.error('Upload error:', err);
      setUploadError(
        getApiErrorMessage(
          err,
          'Erreur lors de l\'upload. Vérifiez votre configuration (clé API, format du fichier).'
        )
      );
    } finally {
      setUploading(false);
    }
  };

  const refreshDocuments = async () => {
    setLoading(true);
    try {
      const docs = await listDocuments();
      setDocuments(docs);
    } catch (err) {
      console.error('List error:', err);
    } finally {
      setLoading(false);
    }
  };

  const openDetails = async (doc: DocumentResponse) => {
    if (!['extracted', 'curated'].includes(doc.status)) return;
    setSelectedDoc(doc);
    setLoadingExtraction(true);
    try {
      const result = await getExtraction(doc.id);
      setExtraction(result);
    } catch (err) {
      console.error('Extraction error:', err);
    } finally {
      setLoadingExtraction(false);
    }
  };

  const closeDetails = () => {
    setSelectedDoc(null);
    setExtraction(null);
  };

  const handleDelete = async (id: string) => {
    //if (!confirm('Êtes-vous sûr de vouloir supprimer ce document à tous les niveaux ?')) return;
    try {
      await deleteDocument(id);
      setDocuments((prev) => prev.filter((d) => d.id !== id));
    } catch (err) {
      console.error('Delete error:', err);
      alert('Erreur lors de la suppression');
    }
  };

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    if (e.dataTransfer.files) handleFiles(e.dataTransfer.files);
  }, [handleFiles]);

  const onDragOver = (e: React.DragEvent) => { e.preventDefault(); setDragging(true); };
  const onDragLeave = () => setDragging(false);

  return (
    <div className="animate-slide-up">
      <div className="page-header">
        <h1>Traitement de Documents</h1>
        <p>Uploadez vos pièces comptables — elles seront classifiées, extraites et analysées automatiquement.</p>
      </div>

      {uploadError && (
        <div
          className="card animate-slide-up"
          style={{
            marginBottom: '1rem',
            borderColor: 'rgba(255,77,109,0.4)',
            background: 'rgba(255,77,109,0.08)',
            position: 'relative',
            paddingRight: '3rem',
          }}
          role="alert"
        >
          <button
            className="modal-close"
            onClick={() => setUploadError(null)}
            style={{ position: 'absolute', top: '0.6rem', right: '0.9rem', fontSize: '1.2rem' }}
            aria-label="Fermer l'alerte"
          >
            &times;
          </button>
          <p style={{ color: 'var(--color-danger)', fontWeight: 700, marginBottom: '0.2rem' }}>
            Erreur d'upload
          </p>
          <p className="text-sm" style={{ color: 'var(--color-text)' }}>
            {uploadError}
          </p>
        </div>
      )}

      {/* Drop Zone */}
      <div
        id="upload-dropzone"
        className={`drop-zone mb-4 ${dragging ? 'dragging' : ''}`}
        onClick={() => inputRef.current?.click()}
        onDrop={onDrop}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
      >
        <input
          ref={inputRef}
          type="file"
          multiple
          accept={INPUT_ACCEPT}
          style={{ display: 'none' }}
          onChange={(e) => {
            if (e.target.files) {
              void handleFiles(e.target.files);
            }
            // Permet de re-sélectionner le même fichier et de retrigger l'événement.
            e.target.value = '';
          }}
        />

        {uploading ? (
          <>
            <span className="drop-zone-icon">⏳</span>
            <h2 className="loading-text">Upload en cours…</h2>
            <p>Vos fichiers sont en cours de transfert vers la zone Bronze</p>
            <div className="progress-bar center">
              <div className="progress-fill" style={{ width: '100%' }} />
            </div>
          </>
        ) : (
          <>
            <span className="drop-zone-icon">☁️</span>
            <h2>Déposez vos fichiers ici</h2>
            <p>ou cliquez pour sélectionner plusieurs fichiers — Formats acceptés : PDF, DOC, DOCX, images</p>
            <div className="mt-5">
              <button id="upload-btn" className="btn btn-primary">
                📂 Choisir des fichiers
              </button>
            </div>
          </>
        )}
      </div>

      {/* Upload feedback */}
      {uploadedFiles.length > 0 && (
        <div className="card card-success animate-slide-up mb-4">
          <button 
            className="modal-close card-dismiss" 
            onClick={() => setUploadedFiles([])}
          >
            &times;
          </button>
          
          <p className="section-title text-accent">
            ✨ {uploadedFiles.length} document(s) enregistré(s)
          </p>
          
          <div className="flex flex-wrap gap-1 mt-2">
            {uploadedFiles.map((f) => (
              <span key={f} className="badge badge-faible badge-normal">{f}</span>
            ))}
          </div>
          
          <p className="text-sm text-muted mt-2">
            Les fichiers sont maintenant en sécurité dans les différentes zones de traitement
            (Bronze, Silver & Gold).
          </p>
        </div>
      )}

      {/* Document list */}
      <div className="toolbar justify-between mb-2">
        <p className="section-title">📋 Documents traités ({documents.length})</p>
        <button id="refresh-btn" className="btn btn-ghost" onClick={refreshDocuments} disabled={loading}>
          {loading ? <span className="spinner spinner-sm" /> : '🔄'} Rafraîchir
        </button>
      </div>

      {documents.length === 0 ? (
        <div className="empty-state">
          <span className="empty-state-icon">📭</span>
          <h3>Aucun document encore</h3>
          <p>Uploadez vos premiers documents pour démarrer le traitement</p>
        </div>
      ) : (
        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>Fichier</th>
                {isAdmin && <th>Uploadé par</th>}
                <th>Type</th>
                <th>Statut</th>
                <th>Pipeline</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {documents.sort((a, b) => new Date(b.upload_at).getTime() - new Date(a.upload_at).getTime()).map((doc) => (
                <tr key={doc.id}>
                  <td>
                    <div className="flex-col">
                      <span style={{ fontWeight: 600 }}>{doc.original_filename}</span>
                      <span className="text-muted" style={{ fontSize: '0.7rem' }}>{new Date(doc.upload_at).toLocaleString('fr-FR')}</span>
                    </div>
                  </td>
                  {isAdmin && (
                    <td>
                      <span className="text-sm text-muted">{doc.uploaded_by ?? '—'}</span>
                    </td>
                  )}
                  <td>
                    {doc.document_type ? (
                      <span className={`badge badge-${doc.document_type}`}>
                        {TYPE_LABELS[doc.document_type]}
                      </span>
                    ) : (
                      <span className="text-muted text-sm">—</span>
                    )}
                  </td>
                  <td>
                    <span className={`badge badge-${doc.status}`}>
                      {STATUS_LABELS[doc.status] ?? doc.status}
                    </span>
                  </td>
                  <td>
                    <div className="pipeline-steps">
                      <span className={`pipeline-step ${['extracted','curated'].includes(doc.status) ? 'done' : doc.status === 'uploaded' ? 'active' : ''}`}>Bronze</span>
                      <span className="pipeline-step-sep">→</span>
                      <span className={`pipeline-step ${['curated'].includes(doc.status) ? 'done' : doc.status === 'processing' || doc.status === 'extracted' ? 'active' : ''}`}>Silver</span>
                      <span className="pipeline-step-sep">→</span>
                      <span className={`pipeline-step ${doc.status === 'curated' ? 'done' : ''}`}>Gold</span>
                    </div>
                  </td>
                  <td>
                    <div className="flex gap-1">
                      {doc.status === 'error' && doc.error_message && (
                        <button
                          className="btn btn-ghost"
                          style={{ padding: '0.25rem 0.5rem', fontSize: '0.75rem', color: 'var(--color-danger)' }}
                          onClick={() => setUploadError(doc.error_message)}
                        >
                          ⚠️ Détail
                        </button>
                      )}
                      <button 
                        className="btn btn-ghost btn-xs" 
                        disabled={!['extracted', 'curated'].includes(doc.status)}
                        onClick={() => openDetails(doc)}
                      >
                        👁️ Voir
                      </button>
                      <button 
                        className="btn btn-ghost btn-xs btn-danger" 
                        onClick={() => handleDelete(doc.id)}
                      >
                        🗑️
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Details Modal */}
      {selectedDoc && (
        <div className="modal-overlay" onClick={closeDetails}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div className="flex items-center gap-2">
                <span className={`badge badge-${selectedDoc.document_type ?? 'autre'}`}>
                  {TYPE_LABELS[selectedDoc.document_type ?? 'autre']}
                </span>
                <h2 className="text-lg font-bold">{selectedDoc.original_filename}</h2>
              </div>
              <button className="modal-close" onClick={closeDetails}>&times;</button>
            </div>
            {isAdmin && (
              <div style={{ padding: '0.75rem 1.5rem', borderBottom: '1px solid var(--color-border)', display: 'flex', gap: '2rem', background: 'rgba(255,255,255,0.02)' }}>
                <div>
                  <span className="text-sm text-muted">Uploadé par </span>
                  <span className="text-sm" style={{ fontWeight: 600 }}>{selectedDoc.uploaded_by ?? '—'}</span>
                </div>
                <div>
                  <span className="text-sm text-muted">Date d'upload </span>
                  <span className="text-sm" style={{ fontWeight: 600 }}>{new Date(selectedDoc.upload_at).toLocaleString('fr-FR')}</span>
                </div>
              </div>
            )}
            <div className="modal-body">
              {loadingExtraction ? (
                <div className="flex items-center justify-center gap-2 p-4">
                  <div className="spinner" />
                  <span>Chargement des données extraites…</span>
                </div>
              ) : extraction ? (
                <div className="flex-col gap-2">
                  <div className="grid-2">
                    <div className="card-glass">
                      <p className="text-sm text-muted mb-1">ÉMETTEUR</p>
                      <p className="font-bold">{extraction.emetteur_nom || 'Inconnu'}</p>
                      <p className="text-sm text-muted">{extraction.emetteur_adresse || '—'}</p>
                      <div className="mt-2 flex items-center gap-1">
                        <span className="text-sm">SIREN :</span>
                        <code className="code-inline">{extraction.siren || '—'}</code>
                      </div>
                    </div>
                    <div className="card-glass">
                      <p className="text-sm text-muted mb-1">DESTINATAIRE</p>
                      <p className="font-bold">{extraction.destinataire_nom || 'Inconnu'}</p>
                      <p className="text-sm text-muted">{extraction.destinataire_adresse || '—'}</p>
                      <div className="mt-2 flex items-center gap-1">
                        <span className="text-sm">SIRET :</span>
                        <code className="code-inline">{extraction.siret || '—'}</code>
                      </div>
                    </div>
                  </div>

                  <div className="stat-grid mt-5 mb-3">
                    <div className="stat-card">
                      <span className="stat-label">Total TTC</span>
                      <span className="stat-value text-2xl">{extraction.montants.ttc?.toLocaleString('fr-FR')} {extraction.montants.currency}</span>
                    </div>
                    <div className="stat-card">
                      <span className="stat-label">HT / TVA</span>
                      <span className="stat-value subtle text-base">{extraction.montants.ht?.toLocaleString('fr-FR')} / {extraction.montants.tva?.toLocaleString('fr-FR')}</span>
                    </div>
                    <div className="stat-card">
                      <span className="stat-label">Date émission</span>
                      <span className="stat-value subtle text-lg">{extraction.date_emission || '—'}</span>
                    </div>
                    <div className="stat-card">
                      <span className="stat-label">N° Document</span>
                      <span className="stat-value subtle text-lg">{extraction.numero_document || '—'}</span>
                    </div>
                  </div>

                  <div>
                    <p className="text-sm text-muted mb-1">TEXTE BRUT (OCR)</p>
                    <pre className="code-block">
                      {extraction.raw_text}
                    </pre>
                  </div>
                </div>
              ) : (
                <p>Impossible de charger les données.</p>
              )}
            </div>
            <div className="modal-footer">
              <button className="btn btn-ghost w-full" onClick={closeDetails}>Fermer</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
