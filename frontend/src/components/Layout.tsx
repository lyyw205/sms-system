import { useState } from 'react';
import { Layout as AntLayout, Menu } from 'antd';
import {
  DashboardOutlined,
  CalendarOutlined,
  MessageOutlined,
  ThunderboltOutlined,
  HomeOutlined,
  FileTextOutlined,
} from '@ant-design/icons';
import { useNavigate, useLocation } from 'react-router-dom';

const { Header, Sider, Content } = AntLayout;

interface LayoutProps {
  children: React.ReactNode;
}

const Layout = ({ children }: LayoutProps) => {
  const [collapsed, setCollapsed] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  const menuItems = [
    {
      key: '/',
      icon: <DashboardOutlined />,
      label: '대시보드',
    },
    {
      key: '/reservations',
      icon: <CalendarOutlined />,
      label: '예약 관리',
    },
    {
      key: '/rooms',
      icon: <HomeOutlined />,
      label: '객실 배정',
    },
    {
      key: '/messages',
      icon: <MessageOutlined />,
      label: 'SMS 모니터링',
    },
    {
      key: '/auto-response',
      icon: <ThunderboltOutlined />,
      label: '자동 응답',
    },
    {
      key: '/templates',
      icon: <FileTextOutlined />,
      label: '메시지 관리',
    },
  ];

  return (
    <AntLayout style={{ minHeight: '100vh' }}>
      <Sider collapsible collapsed={collapsed} onCollapse={setCollapsed}>
        <div
          style={{
            height: 32,
            margin: 16,
            background: 'rgba(255, 255, 255, 0.2)',
            borderRadius: 6,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'white',
            fontWeight: 'bold',
          }}
        >
          {collapsed ? 'SMS' : 'SMS 예약 시스템'}
        </div>
        <Menu
          theme="dark"
          selectedKeys={[location.pathname]}
          mode="inline"
          items={menuItems}
          onClick={({ key }) => navigate(key)}
        />
      </Sider>
      <AntLayout>
        <Header style={{ background: '#fff', padding: '0 24px' }}>
          <h2 style={{ margin: 0 }}>SMS 예약 시스템 - Demo Mode</h2>
        </Header>
        <Content style={{ margin: '24px 16px', padding: 24, background: '#fff' }}>
          {children}
        </Content>
      </AntLayout>
    </AntLayout>
  );
};

export default Layout;
