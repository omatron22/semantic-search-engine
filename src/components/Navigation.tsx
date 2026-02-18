import { Link, useLocation } from 'react-router-dom';
import './Navigation.css';

export function Navigation() {
  const location = useLocation();
  
  return (
    <nav className="navigation">
      <div className="nav-container">
        <div className="nav-links">
          <Link 
            to="/" 
            className={`nav-link ${location.pathname === '/' ? 'active' : ''}`}
          >
            Index
          </Link>
          <Link
            to="/search"
            className={`nav-link ${location.pathname === '/search' ? 'active' : ''}`}
          >
            Search
          </Link>
          <Link
            to="/connectors"
            className={`nav-link ${location.pathname === '/connectors' ? 'active' : ''}`}
          >
            Connectors
          </Link>
        </div>
      </div>
    </nav>
  );
}
