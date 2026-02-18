import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Navigation } from './components/Navigation';
import { IndexPage } from './pages/IndexPage';
import { SearchPage } from './pages/SearchPage';
import { ConnectorsPage } from './pages/ConnectorsPage';
import './App.css';

function App() {
  return (
    <BrowserRouter>
      <Navigation />
      <Routes>
        <Route path="/" element={<IndexPage />} />
        <Route path="/search" element={<SearchPage />} />
        <Route path="/connectors" element={<ConnectorsPage />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
