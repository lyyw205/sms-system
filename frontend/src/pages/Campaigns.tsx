import { useEffect, useState } from 'react';
import { Table, Tag, Button, Typography } from 'antd';
import { ReloadOutlined, HistoryOutlined } from '@ant-design/icons';
import { campaignsAPI } from '../services/api';

const { Title } = Typography;

const Campaigns = () => {
  const [history, setHistory] = useState<any[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  useEffect(() => {
    loadHistory();
  }, []);

  const loadHistory = async () => {
    setHistoryLoading(true);
    try {
      const response = await campaignsAPI.getHistory();
      setHistory(response.data);
    } catch (error) {
      console.error('Failed to load history:', error);
    } finally {
      setHistoryLoading(false);
    }
  };

  const historyColumns = [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
    {
      title: '타입', dataIndex: 'campaign_type', key: 'campaign_type',
      render: (v: string) => {
        const map: Record<string, { color: string; label: string }> = {
          room_guide: { color: 'blue', label: '객실안내' },
          party_guide: { color: 'purple', label: '파티안내' },
          tag_based: { color: 'orange', label: '태그발송' },
        };
        const info = map[v] || { color: 'default', label: v };
        return <Tag color={info.color}>{info.label}</Tag>;
      },
    },
    {
      title: '태그', dataIndex: 'target_tag', key: 'target_tag',
      render: (v: string) => v || '-',
    },
    { title: '대상', dataIndex: 'target_count', key: 'target_count' },
    {
      title: '성공', dataIndex: 'sent_count', key: 'sent_count',
      render: (v: number) => <span style={{ color: '#52c41a' }}>{v}</span>,
    },
    {
      title: '실패', dataIndex: 'failed_count', key: 'failed_count',
      render: (v: number) => v > 0 ? <span style={{ color: '#ff4d4f' }}>{v}</span> : '0',
    },
    {
      title: '발송일시', dataIndex: 'sent_at', key: 'sent_at',
      render: (v: string) => v ? new Date(v).toLocaleString('ko-KR') : '-',
    },
  ];

  return (
    <div>
      <Title level={3}><HistoryOutlined /> 발송 이력</Title>
      <Button
        onClick={loadHistory}
        icon={<ReloadOutlined />}
        style={{ marginBottom: 16 }}
      >
        새로고침
      </Button>
      <Table
        dataSource={history}
        columns={historyColumns}
        loading={historyLoading}
        rowKey="id"
        pagination={{ pageSize: 10 }}
        size="small"
      />
    </div>
  );
};

export default Campaigns;
