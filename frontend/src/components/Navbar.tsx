import { useEffect, useMemo, useState } from 'react';
import { NavLink } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { listDocuments } from '../api/client';
import type { DocumentResponse } from '../types';

export function Navbar() {
  const { user, logout } = useAuth();
  const isAdmin = user?.role === 'admin';
  const [errorDocs, setErrorDocs] = useState<DocumentResponse[]>([]);
  const [alertsOpen, setAlertsOpen] = useState(false);

  useEffect(() => {
    let isMounted = true;

    const loadErrorDocuments = async () => {
      try {
        const docs = await listDocuments();
        if (!isMounted) {
          return;
        }

        const errors = docs
          .filter((doc) => doc.status === 'error' && doc.error_message)
          .sort((a, b) => new Date(b.upload_at).getTime() - new Date(a.upload_at).getTime());

        setErrorDocs(errors);
      } catch (err) {
        if (isMounted) {
          console.error('Navbar list error:', err);
        }
      }
    };

    void loadErrorDocuments();
    const timer = setInterval(() => {
      void loadErrorDocuments();
    }, 10000);

    return () => {
      isMounted = false;
      clearInterval(timer);
    };
  }, []);

  const errorCount = errorDocs.length;
  const latestErrors = useMemo(() => errorDocs.slice(0, 5), [errorDocs]);

  return (
    <nav className="navbar">
      <NavLink to="/" className="navbar-brand">
        <span className="brand-icon">📄</span>
        DocFlow
      </NavLink>
      <div className="navbar-links">
        <NavLink
          to="/"
          end
          className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
        >
          ⬆️ Upload
        </NavLink>
        <NavLink
          to="/crm"
          className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
        >
          🏢 CRM
        </NavLink>
        <NavLink
          to="/compliance"
          className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
        >
          🛡️ Conformité
        </NavLink>
      </div>
      {user && (
        <div className="navbar-user">
          <div className="navbar-alerts">
            <button
              type="button"
              className={`nav-alert-btn ${alertsOpen ? 'open' : ''}`}
              onClick={() => setAlertsOpen((prev) => !prev)}
              aria-label="Voir les erreurs de traitement"
              aria-expanded={alertsOpen}
            >
              ⚠️
              {errorCount > 0 && <span className="nav-alert-count">{errorCount}</span>}
            </button>

            {alertsOpen && (
              <div className="nav-alert-panel">
                <p className="nav-alert-title">Erreurs de traitement</p>
                {errorCount === 0 ? (
                  <p className="nav-alert-empty">Aucune erreur en cours.</p>
                ) : (
                  <div className="nav-alert-list">
                    {latestErrors.map((doc) => (
                      <button
                        key={doc.id}
                        type="button"
                        className="nav-alert-item"
                        onClick={() => setAlertsOpen(false)}
                      >
                        <span className="nav-alert-file">{doc.original_filename}</span>
                        <span className="nav-alert-message">{doc.error_message}</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>

          <span className="user-badge">
            {isAdmin ? '👑' : '👤'} {user.full_name}
          </span>
          <button className="btn btn-ghost btn-xs btn-danger" onClick={logout}>
            Déconnexion
          </button>
        </div>
      )}
    </nav>
  );
}
