import { NavLink } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export function Navbar() {
  const { user, logout } = useAuth();
  const isAdmin = user?.role === 'admin';

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
        {isAdmin && (
          <>
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
          </>
        )}
      </div>
      {user && (
        <div className="navbar-user">
          <span className="user-badge">
            {isAdmin ? '👑' : '👤'} {user.full_name}
          </span>
          <button className="btn-logout" onClick={logout}>
            Déconnexion
          </button>
        </div>
      )}
    </nav>
  );
}
