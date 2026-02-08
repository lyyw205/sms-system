import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { ConfigProvider } from 'antd';
import koKR from 'antd/locale/ko_KR';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import Reservations from './pages/Reservations';
import Messages from './pages/Messages';
import AutoResponse from './pages/AutoResponse';
import Campaigns from './pages/Campaigns';
import Scheduler from './pages/Scheduler';
import RoomAssignment from './pages/RoomAssignment';

function App() {
  return (
    <ConfigProvider locale={koKR}>
      <Router>
        <Layout>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/reservations" element={<Reservations />} />
            <Route path="/rooms" element={<RoomAssignment />} />
            <Route path="/messages" element={<Messages />} />
            <Route path="/auto-response" element={<AutoResponse />} />
            <Route path="/campaigns" element={<Campaigns />} />
            <Route path="/scheduler" element={<Scheduler />} />
          </Routes>
        </Layout>
      </Router>
    </ConfigProvider>
  );
}

export default App;
