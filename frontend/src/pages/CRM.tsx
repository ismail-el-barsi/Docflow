import { useEffect, useState } from 'react';
import { getCrmSuppliers, getSupplierDocuments } from '../api/client';
import type { GoldRecord, GroupType, SupplierSummary } from '../types';

// ─── Constantes d'affichage ──────────────────────────────────────────────────

const TYPE_ICONS: Record<string, string> = {
  facture: '🧾',
  devis: '📋',
  attestation: '📜',
  autre: '📄',
};

const GROUP_META: Record<GroupType, { icon: string; label: string; badgeClass: string }> = {
  siren:   { icon: '🏢', label: 'SIREN',   badgeClass: 'badge-curated' },
  nom:     { icon: '🔤', label: 'Nom',     badgeClass: 'badge-moyenne' },
  inconnu: { icon: '❓', label: 'Inconnu', badgeClass: 'badge-haute'   },
};

// ─── Composant principal ─────────────────────────────────────────────────────

export function CrmPage() {
  const [suppliers, setSuppliers] = useState<SupplierSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [groupFilter, setGroupFilter] = useState<GroupType | 'all'>('all');
  const [selectedSupplier, setSelectedSupplier] = useState<SupplierSummary | null>(null);
  const [supplierDocs, setSupplierDocs] = useState<GoldRecord[]>([]);
  const [loadingDocs, setLoadingDocs] = useState(false);

  useEffect(() => {
    getCrmSuppliers()
      .then(setSuppliers)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const openSupplier = async (supplier: SupplierSummary) => {
    setSelectedSupplier(supplier);
    setLoadingDocs(true);
    setSupplierDocs([]);
    try {
      const docs = await getSupplierDocuments(supplier.supplier_key);
      setSupplierDocs(docs);
    } catch (err) {
      console.error('Error fetching supplier docs:', err);
    } finally {
      setLoadingDocs(false);
    }
  };

  const closeSupplier = () => {
    setSelectedSupplier(null);
    setSupplierDocs([]);
  };

  // Filtrage : texte + type de groupe
  const filtered = suppliers.filter((s) => {
    const matchText =
      s.nom.toLowerCase().includes(search.toLowerCase()) ||
      (s.siren ?? '').includes(search);
    const matchGroup = groupFilter === 'all' || s.group_type === groupFilter;
    return matchText && matchGroup;
  });

  const exportCsv = () => {
    const header = 'Clé,Groupe,SIREN,Nom,Documents,Total TTC (€),Alertes,Types\n';
    const rows = filtered
      .map(
        (s) =>
          `"${s.supplier_key}","${s.group_type}","${s.siren ?? ''}","${s.nom}",${s.nombre_documents},${s.total_ttc},${s.a_des_alertes ? 'Oui' : 'Non'},"${s.types_documents.join('; ')}"`
      )
      .join('\n');
    const blob = new Blob([header + rows], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'crm_fournisseurs.csv';
    a.click();
    URL.revokeObjectURL(url);
  };

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', padding: '4rem', justifyContent: 'center' }}>
        <div className="spinner" />
        <span className="loading-text">Chargement des fournisseurs…</span>
      </div>
    );
  }

  return (
    <div className="animate-slide-up">
      <div className="page-header">
        <h1>CRM Fournisseurs</h1>
        <p>
          Fournisseurs groupés par <strong>SIREN</strong> si disponible, par <strong>nom d'émetteur</strong> sinon, ou dans un groupe unique <strong>Inconnu</strong>.
        </p>
      </div>

      {/* KPIs */}
      <div className="stat-grid">
        <div className="stat-card">
          <span className="stat-icon">🏢</span>
          <span className="stat-value">{suppliers.filter((s) => s.group_type === 'siren').length}</span>
          <span className="stat-label">Par SIREN</span>
        </div>
        <div className="stat-card">
          <span className="stat-icon">🔤</span>
          <span className="stat-value">{suppliers.filter((s) => s.group_type === 'nom').length}</span>
          <span className="stat-label">Par Nom</span>
        </div>
        <div className="stat-card">
          <span className="stat-icon">📄</span>
          <span className="stat-value">{suppliers.reduce((s, x) => s + x.nombre_documents, 0)}</span>
          <span className="stat-label">Documents</span>
        </div>
        <div className="stat-card">
          <span className="stat-icon">⚠️</span>
          <span className="stat-value" style={{ color: 'var(--color-warning)' }}>
            {suppliers.filter((s) => s.a_des_alertes).length}
          </span>
          <span className="stat-label">Avec alertes</span>
        </div>
      </div>

      {/* Actions */}
      <div style={{ display: 'flex', gap: '1rem', marginBottom: '1.5rem', alignItems: 'center', flexWrap: 'wrap' }}>
        <input
          id="supplier-search"
          type="text"
          placeholder="🔍 Rechercher par nom ou SIREN…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{
            flex: 1,
            minWidth: '200px',
            background: 'var(--color-surface)',
            border: '1px solid var(--color-border)',
            borderRadius: 'var(--radius-sm)',
            padding: '0.625rem 1rem',
            color: 'var(--color-text)',
            fontSize: '0.9rem',
            fontFamily: 'inherit',
            outline: 'none',
          }}
        />

        {/* Filtre de groupe */}
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          {(['all', 'siren', 'nom', 'inconnu'] as const).map((g) => (
            <button
              key={g}
              id={`filter-group-${g}`}
              className={`btn ${groupFilter === g ? 'btn-primary' : 'btn-ghost'}`}
              onClick={() => setGroupFilter(g)}
              style={{ fontSize: '0.8rem', padding: '0.4rem 0.75rem' }}
            >
              {g === 'all' ? '📋 Tous' : `${GROUP_META[g].icon} ${GROUP_META[g].label}`}
            </button>
          ))}
        </div>

        <button id="export-csv-btn" className="btn btn-ghost" onClick={exportCsv}>
          📥 Export CSV
        </button>
      </div>

      {/* Suppliers Grid */}
      {filtered.length === 0 ? (
        <div className="empty-state">
          <span className="empty-state-icon">🏭</span>
          <h3>Aucun fournisseur trouvé</h3>
          <p>Uploader des documents pour voir apparaître les fournisseurs</p>
        </div>
      ) : (
        <div className="suppliers-grid">
          {filtered.map((s) => {
            const meta = GROUP_META[s.group_type];
            return (
              <div
                key={s.supplier_key}
                className={`supplier-card ${s.a_des_alertes ? 'has-alerts' : ''}`}
                onClick={() => openSupplier(s)}
                style={{ cursor: 'pointer' }}
              >
                {/* En-tête : nom + badge de groupe */}
                <div>
                  <div className="flex items-center gap-1" style={{ marginBottom: '0.25rem' }}>
                    <span className="supplier-name">{s.nom}</span>
                    {s.a_des_alertes && (
                      <span title="Alertes détectées" style={{ fontSize: '1rem' }}>⚠️</span>
                    )}
                  </div>

                  {/* Identifiant légal ou indicateur de groupe */}
                  <div className="supplier-siren" style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                    <span className={`badge ${meta.badgeClass}`} style={{ fontSize: '0.7rem' }}>
                      {meta.icon} {meta.label}
                    </span>
                    {s.siren ? (
                      <span className="font-mono" style={{ fontSize: '0.78rem' }}>SIREN : {s.siren}</span>
                    ) : s.group_type === 'nom' ? (
                      <span style={{ fontSize: '0.78rem', opacity: 0.7 }}>SIREN non extrait</span>
                    ) : (
                      <span style={{ fontSize: '0.78rem', opacity: 0.7 }}>Ni SIREN ni nom</span>
                    )}
                  </div>
                </div>

                <div className="supplier-amount">
                  {s.total_ttc.toLocaleString('fr-FR', { maximumFractionDigits: 2 })} €
                </div>

                <div className="flex gap-1" style={{ flexWrap: 'wrap' }}>
                  {s.types_documents.map((t) => (
                    <span key={t} className={`badge badge-${t}`}>
                      {TYPE_ICONS[t]} {t}
                    </span>
                  ))}
                </div>

                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted">{s.nombre_documents} document(s)</span>
                  {s.a_des_alertes ? (
                    <span className="badge badge-haute">⚠️ Alertes</span>
                  ) : (
                    <span className="badge badge-curated">✅ Conforme</span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Modal : historique des documents du fournisseur */}
      {selectedSupplier && (
        <div className="modal-overlay" onClick={closeSupplier}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div className="flex items-center gap-2" style={{ flexWrap: 'wrap' }}>
                <h2 style={{ fontSize: '1.2rem', fontWeight: 700 }}>{selectedSupplier.nom}</h2>
                <span className={`badge ${GROUP_META[selectedSupplier.group_type].badgeClass}`} style={{ fontSize: '0.75rem' }}>
                  {GROUP_META[selectedSupplier.group_type].icon} {GROUP_META[selectedSupplier.group_type].label}
                </span>
                {selectedSupplier.siren && (
                  <span className="text-sm text-muted font-mono">SIREN : {selectedSupplier.siren}</span>
                )}
              </div>
              <button className="modal-close" onClick={closeSupplier}>&times;</button>
            </div>

            <div className="modal-body">
              {/* KPIs fournisseur */}
              <div className="stat-grid" style={{ marginBottom: '2rem' }}>
                <div className="stat-card">
                  <span className="stat-label">Total Cumulé</span>
                  <span className="stat-value" style={{ fontSize: '1.5rem' }}>
                    {selectedSupplier.total_ttc.toLocaleString('fr-FR')} €
                  </span>
                </div>
                <div className="stat-card">
                  <span className="stat-label">Documents</span>
                  <span className="stat-value" style={{ fontSize: '1.5rem' }}>
                    {selectedSupplier.nombre_documents}
                  </span>
                </div>
                <div className="stat-card">
                  <span className="stat-label">Conformité</span>
                  <span
                    className={`badge ${selectedSupplier.a_des_alertes ? 'badge-haute' : 'badge-curated'}`}
                    style={{ marginTop: '0.5rem' }}
                  >
                    {selectedSupplier.a_des_alertes ? '⚠️ Alertes actives' : '✅ Dossier conforme'}
                  </span>
                </div>
              </div>

              <p className="section-title">📄 Historique des documents (du plus récent au plus ancien)</p>

              {loadingDocs ? (
                <div className="flex items-center justify-center p-8 gap-2">
                  <div className="spinner" />
                  <span>Chargement de l'historique…</span>
                </div>
              ) : supplierDocs.length === 0 ? (
                <div className="empty-state" style={{ padding: '2rem' }}>
                  <span className="empty-state-icon">📭</span>
                  <p>Aucun document trouvé pour ce fournisseur.</p>
                </div>
              ) : (
                <div className="table-container">
                  <table>
                    <thead>
                      <tr>
                        <th>Date traitement</th>
                        <th>Date émission</th>
                        <th>Type</th>
                        <th>N° Document</th>
                        <th>Montant TTC</th>
                        <th>Fichier</th>
                        <th>Statut</th>
                      </tr>
                    </thead>
                    <tbody>
                      {supplierDocs.map((doc) => (
                        <tr key={doc.document_id}>
                          <td className="text-sm">
                            {new Date(doc.curated_at).toLocaleDateString('fr-FR')}
                          </td>
                          <td className="text-sm">
                            {doc.extraction.date_emission
                              ? doc.extraction.date_emission
                              : <span style={{ opacity: 0.4 }}>—</span>}
                          </td>
                          <td>
                            <span className={`badge badge-${doc.document_type}`}>
                              {TYPE_ICONS[doc.document_type]} {doc.document_type}
                            </span>
                          </td>
                          <td className="font-mono text-sm">
                            {doc.extraction.numero_document || <span style={{ opacity: 0.4 }}>—</span>}
                          </td>
                          <td style={{ fontWeight: 600 }}>
                            {doc.extraction.montants.ttc != null
                              ? `${Number(doc.extraction.montants.ttc).toLocaleString('fr-FR')} €`
                              : <span style={{ opacity: 0.4 }}>—</span>}
                          </td>
                          <td className="text-sm" style={{ maxWidth: '180px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            {doc.original_filename}
                          </td>
                          <td>
                            {doc.alerts.length > 0 ? (
                              <span className="badge badge-haute" title={`${doc.alerts.length} alerte(s)`}>
                                ⚠️ {doc.alerts.length}
                              </span>
                            ) : (
                              <span className="badge badge-curated">✅ OK</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            <div className="modal-header" style={{ top: 'auto', bottom: 0, borderTop: '1px solid var(--color-border)', borderBottom: 'none' }}>
              <button className="btn btn-ghost w-full" onClick={closeSupplier}>Fermer</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
