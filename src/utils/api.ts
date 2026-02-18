// API utility functions

const API_BASE = "http://localhost:3001";

export interface IndexProgress {
  current: number;
  total: number;
  currentFile: string;
  status: string;
}

export interface SearchResult {
  file_path: string;
  text: string;
  _distance: number;
  file_size?: number;
  modified_date?: string;
  word_count?: number;
}

export interface ConnectorStatus {
  connector_id: string;
  connector_type: string;
  label: string;
  status: string;
  last_sync: string | null;
  last_error: string | null;
  items_synced: number;
}

export interface AddConnectorParams {
  type: string;
  credentials: Record<string, string>;
  label?: string;
  sync_interval?: number;
}

export const api = {
  // Health check
  async health(): Promise<{ status: string; message: string }> {
    const response = await fetch(`${API_BASE}/health`);
    return response.json();
  },

  // Index folder with progress updates
  async indexFolder(
    folderPath: string,
    onProgress?: (progress: IndexProgress) => void
  ): Promise<{ success: boolean; message: string }> {
    const response = await fetch(`${API_BASE}/api/index`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ folderPath })
    });
    return response.json();
  },

  // Search documents
  async search(query: string, limit: number = 10): Promise<SearchResult[]> {
    const response = await fetch(`${API_BASE}/api/search`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, limit })
    });
    const data = await response.json();
    return data.results;
  },

  // Connectors
  async listConnectors(): Promise<ConnectorStatus[]> {
    const response = await fetch(`${API_BASE}/api/connectors`);
    const data = await response.json();
    return data.connectors || [];
  },

  async getConnectorTypes(): Promise<string[]> {
    const response = await fetch(`${API_BASE}/api/connectors/types`);
    const data = await response.json();
    return data.types || [];
  },

  async addConnector(params: AddConnectorParams): Promise<{ success: boolean; connector?: ConnectorStatus; error?: string }> {
    const response = await fetch(`${API_BASE}/api/connectors`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(params),
    });
    return response.json();
  },

  async deleteConnector(connectorId: string): Promise<{ success: boolean }> {
    const response = await fetch(`${API_BASE}/api/connectors/${connectorId}`, {
      method: "DELETE",
    });
    return response.json();
  },

  async getConnectorStatus(connectorId: string): Promise<ConnectorStatus> {
    const response = await fetch(`${API_BASE}/api/connectors/${connectorId}/status`);
    return response.json();
  },
};
