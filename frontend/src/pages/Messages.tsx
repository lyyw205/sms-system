import { useEffect, useState } from 'react';
import { Table, Tag, Button, Space, Tabs, Card, message as antMessage } from 'antd';
import { ReloadOutlined, CheckCircleOutlined } from '@ant-design/icons';
import SMSSimulator from '../components/SMSSimulator';
import { messagesAPI, autoResponseAPI } from '../services/api';

const Messages = () => {
  const [messages, setMessages] = useState([]);
  const [reviewQueue, setReviewQueue] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadMessages();
    loadReviewQueue();
  }, []);

  const loadMessages = async () => {
    setLoading(true);
    try {
      const response = await messagesAPI.getAll({ limit: 100 });
      setMessages(response.data);
    } catch (error) {
      console.error('Failed to load messages:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadReviewQueue = async () => {
    try {
      const response = await messagesAPI.getReviewQueue();
      setReviewQueue(response.data);
    } catch (error) {
      console.error('Failed to load review queue:', error);
    }
  };

  const handleGenerateResponse = async (messageId: number) => {
    try {
      await autoResponseAPI.generate(messageId);
      antMessage.success('자동 응답 생성 완료');
      loadMessages();
      loadReviewQueue();
    } catch (error) {
      antMessage.error('자동 응답 생성 실패');
    }
  };

  const columns = [
    {
      title: '방향',
      dataIndex: 'direction',
      key: 'direction',
      render: (direction: string) => (
        <Tag color={direction === 'inbound' ? 'blue' : 'green'}>
          {direction === 'inbound' ? '수신' : '발신'}
        </Tag>
      ),
    },
    {
      title: '발신자',
      dataIndex: 'from_',
      key: 'from_',
    },
    {
      title: '수신자',
      dataIndex: 'to',
      key: 'to',
    },
    {
      title: '메시지',
      dataIndex: 'message',
      key: 'message',
      ellipsis: true,
    },
    {
      title: '자동 응답',
      dataIndex: 'auto_response',
      key: 'auto_response',
      ellipsis: true,
      render: (text: string) => text || '-',
    },
    {
      title: '신뢰도',
      dataIndex: 'auto_response_confidence',
      key: 'confidence',
      render: (conf: number) => (conf ? `${(conf * 100).toFixed(0)}%` : '-'),
    },
    {
      title: '출처',
      dataIndex: 'response_source',
      key: 'source',
      render: (source: string) => {
        if (!source) return '-';
        const color = source === 'rule' ? 'green' : source === 'llm' ? 'blue' : 'orange';
        return <Tag color={color}>{source}</Tag>;
      },
    },
    {
      title: '시간',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (time: string) => new Date(time).toLocaleString('ko-KR'),
    },
  ];

  const reviewColumns = [
    ...columns,
    {
      title: '작업',
      key: 'action',
      render: (record: any) => (
        <Space>
          <Button
            size="small"
            icon={<CheckCircleOutlined />}
            onClick={() => handleGenerateResponse(record.id)}
          >
            재생성
          </Button>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <h1>SMS 모니터링</h1>

      <SMSSimulator
        onSent={() => {
          loadMessages();
          loadReviewQueue();
        }}
      />

      <Tabs
        defaultActiveKey="1"
        items={[
          {
            key: '1',
            label: '전체 메시지',
            children: (
              <Card
                extra={
                  <Button icon={<ReloadOutlined />} onClick={loadMessages}>
                    새로고침
                  </Button>
                }
              >
                <Table
                  dataSource={messages}
                  columns={columns}
                  loading={loading}
                  rowKey="id"
                  pagination={{ pageSize: 20 }}
                />
              </Card>
            ),
          },
          {
            key: '2',
            label: `검토 대기 (${reviewQueue.length})`,
            children: (
              <Card
                extra={
                  <Button icon={<ReloadOutlined />} onClick={loadReviewQueue}>
                    새로고침
                  </Button>
                }
              >
                <Table
                  dataSource={reviewQueue}
                  columns={reviewColumns}
                  rowKey="id"
                  pagination={{ pageSize: 20 }}
                />
              </Card>
            ),
          },
        ]}
      />
    </div>
  );
};

export default Messages;
