import { useState, useEffect } from 'react';
import './ConnectorsPage.css';

const API_BASE = 'http://localhost:3001';

interface ConnectorStatus {
  connector_id: string;
  connector_type: string;
  label: string;
  status: string;
  last_sync: string | null;
  last_error: string | null;
  items_synced: number;
}

export function ConnectorsPage() {
  const [connectors, setConnectors] = useState<ConnectorStatus[]>([]);
  const [availableTypes, setAvailableTypes] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState<string | null>(null);
  const [syncMessage, setSyncMessage] = useState('');

  // Form state
  const [showForm, setShowForm] = useState(false);
  const [formType, setFormType] = useState('gmail');
  const [formLabel, setFormLabel] = useState('');
  const [formServer, setFormServer] = useState('imap.gmail.com');
  const [formEmail, setFormEmail] = useState('');
  const [formPassword, setFormPassword] = useState('');
  const [formInterval, setFormInterval] = useState(30);
  const [formError, setFormError] = useState('');
  const [adding, setAdding] = useState(false);

  useEffect(() => {
    loadConnectors();
    loadTypes();
  }, []);

  async function loadConnectors() {
    try {
      const res = await fetch(`${API_BASE}/api/connectors`);
      const data = await res.json();
      setConnectors(data.connectors || []);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }

  async function loadTypes() {
    try {
      const res = await fetch(`${API_BASE}/api/connectors/types`);
      const data = await res.json();
      setAvailableTypes(data.types || []);
    } catch {
      // ignore
    }
  }

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    setFormError('');
    setAdding(true);

    try {
      const res = await fetch(`${API_BASE}/api/connectors`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          type: formType,
          credentials: {
            imap_server: formServer,
            email: formEmail,
            password: formPassword,
          },
          label: formLabel || formEmail,
          sync_interval: formInterval,
        }),
      });

      const data = await res.json();
      if (data.error) {
        setFormError(data.error);
      } else {
        setShowForm(false);
        setFormLabel('');
        setFormEmail('');
        setFormPassword('');
        loadConnectors();
      }
    } catch (err: any) {
      setFormError(err.message || 'Failed to add connector');
    } finally {
      setAdding(false);
    }
  }

  async function handleSync(connectorId: string) {
    setSyncing(connectorId);
    setSyncMessage('Starting sync...');

    try {
      const res = await fetch(`${API_BASE}/api/connectors/${connectorId}/sync`, {
        method: 'POST',
      });

      const reader = res.body?.getReader();
      if (!reader) return;

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const event = JSON.parse(line.slice(6));
              if (event.type === 'progress') {
                setSyncMessage(event.message);
              } else if (event.type === 'complete') {
                setSyncMessage(
                  `Sync complete: ${event.new_items} new emails (${event.total_items} total)`
                );
              } else if (event.type === 'error') {
                setSyncMessage(`Error: ${event.error}`);
              }
            } catch {
              // ignore parse errors
            }
          }
        }
      }
    } catch (err: any) {
      setSyncMessage(`Sync failed: ${err.message}`);
    } finally {
      setSyncing(null);
      loadConnectors();
      setTimeout(() => setSyncMessage(''), 5000);
    }
  }

  async function handleDelete(connectorId: string) {
    if (!confirm('Delete this connector and all its data?')) return;

    try {
      await fetch(`${API_BASE}/api/connectors/${connectorId}`, { method: 'DELETE' });
      loadConnectors();
    } catch {
      // ignore
    }
  }

  function formatDate(iso: string | null): string {
    if (!iso) return 'Never';
    return new Date(iso).toLocaleString();
  }

  function statusBadgeClass(status: string): string {
    switch (status) {
      case 'idle':
      case 'authenticated':
        return 'status-badge status-ok';
      case 'syncing':
        return 'status-badge status-syncing';
      case 'error':
        return 'status-badge status-error';
      default:
        return 'status-badge';
    }
  }

  return (
    <div className="page">
      <div className="page-container">
        <div className="page-hero">
          <h1>Connectors</h1>
          <p className="hero-description">
            Pull data from external sources like email. Connectors download content
            as local files that get indexed alongside your documents.
          </p>
        </div>

        {/* Add Connector */}
        <div className="connectors-section">
          {!showForm ? (
            <div className="add-connector-bar">
              <button
                className="btn btn-primary"
                onClick={() => setShowForm(true)}
                disabled={availableTypes.length === 0}
              >
                Add Connector
              </button>
            </div>
          ) : (
            <form className="connector-form" onSubmit={handleAdd}>
              <h2>Add Email Connector</h2>

              <div className="form-group">
                <label>Type</label>
                <select value={formType} onChange={e => setFormType(e.target.value)}>
                  {availableTypes.map(t => (
                    <option key={t} value={t}>{t}</option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label>Label (optional)</label>
                <input
                  type="text"
                  value={formLabel}
                  onChange={e => setFormLabel(e.target.value)}
                  placeholder="e.g. Work Email"
                />
              </div>

              <div className="form-group">
                <label>IMAP Server</label>
                <input
                  type="text"
                  value={formServer}
                  onChange={e => setFormServer(e.target.value)}
                  placeholder="imap.gmail.com"
                  required
                />
              </div>

              <div className="form-group">
                <label>Email</label>
                <input
                  type="email"
                  value={formEmail}
                  onChange={e => setFormEmail(e.target.value)}
                  placeholder="you@gmail.com"
                  required
                />
              </div>

              <div className="form-group">
                <label>Password / App Password</label>
                <input
                  type="password"
                  value={formPassword}
                  onChange={e => setFormPassword(e.target.value)}
                  placeholder="App password"
                  required
                />
              </div>

              <div className="form-group">
                <label>Sync Interval (minutes)</label>
                <input
                  type="number"
                  value={formInterval}
                  onChange={e => setFormInterval(Number(e.target.value))}
                  min={5}
                  max={1440}
                />
              </div>

              {formError && <div className="form-error">{formError}</div>}

              <div className="form-actions">
                <button type="button" className="btn btn-secondary" onClick={() => setShowForm(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary" disabled={adding}>
                  {adding ? 'Connecting...' : 'Add Connector'}
                </button>
              </div>
            </form>
          )}
        </div>

        {/* Sync status message */}
        {syncMessage && (
          <div className="sync-message">{syncMessage}</div>
        )}

        {/* Connector List */}
        <div className="connectors-section">
          <h2>Connected Sources</h2>

          {loading ? (
            <div className="status-message loading">Loading connectors...</div>
          ) : connectors.length === 0 ? (
            <div className="empty-state">
              <p>No connectors configured yet. Add one above to start syncing external data.</p>
            </div>
          ) : (
            <div className="connector-list">
              {connectors.map(c => (
                <div key={c.connector_id} className="connector-item">
                  <div className="connector-info">
                    <div className="connector-header">
                      <span className="connector-label">{c.label}</span>
                      <span className={statusBadgeClass(c.status)}>{c.status}</span>
                    </div>
                    <div className="connector-meta">
                      <span>{c.connector_type}</span>
                      <span>{c.items_synced} items</span>
                      <span>Last sync: {formatDate(c.last_sync)}</span>
                    </div>
                    {c.last_error && (
                      <div className="connector-error">{c.last_error}</div>
                    )}
                  </div>
                  <div className="connector-actions">
                    <button
                      className="btn-action"
                      onClick={() => handleSync(c.connector_id)}
                      disabled={syncing === c.connector_id}
                    >
                      {syncing === c.connector_id ? 'Syncing...' : 'Sync Now'}
                    </button>
                    <button
                      className="btn-action btn-danger"
                      onClick={() => handleDelete(c.connector_id)}
                    >
                      Delete
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
