import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { ConfigProvider } from 'antd';
import koKR from 'antd/locale/ko_KR';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import Reservations from './pages/Reservations';
import Messages from './pages/Messages';
import AutoResponse from './pages/AutoResponse';
import RoomAssignment from './pages/RoomAssignment';
import RoomManagement from './pages/RoomManagement';
import Templates from './pages/Templates';

function App() {
  return (
    <ConfigProvider locale={koKR}>
      <Router>
        <Layout>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/reservations" element={<Reservations />} />
            <Route path="/rooms" element={<RoomAssignment />} />
            <Route path="/rooms/manage" element={<RoomManagement />} />
            <Route path="/messages" element={<Messages />} />
            <Route path="/auto-response" element={<AutoResponse />} />
            <Route path="/templates" element={<Templates />} />
          </Routes>
        </Layout>
      </Router>
    </ConfigProvider>
  );
}

export default App;
