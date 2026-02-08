import { useEffect, useState } from 'react';
import { Card, Row, Col, Statistic, Table, Tag } from 'antd';
import {
  CalendarOutlined,
  MessageOutlined,
  RiseOutlined,
  SendOutlined,
} from '@ant-design/icons';
import { PieChart, Pie, Cell, ResponsiveContainer, Legend, Tooltip } from 'recharts';
import { dashboardAPI } from '../services/api';

const Dashboard = () => {
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadStats();
  }, []);

  const loadStats = async () => {
    try {
      const response = await dashboardAPI.getStats();
      setStats(response.data);
    } catch (error) {
      console.error('Failed to load stats:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading || !stats) {
    return <div>Loading...</div>;
  }

  // Prepare chart data
  const responseTypeData = [
    { name: '룰 기반', value: stats.auto_response.rule_responses, color: '#52c41a' },
    { name: 'LLM', value: stats.auto_response.llm_responses, color: '#1890ff' },
    { name: '수동', value: stats.auto_response.manual_responses, color: '#faad14' },
  ];

  const genderData = [
    { name: '남성', value: stats.gender_stats?.male_count || 0, color: '#1890ff' },
    { name: '여성', value: stats.gender_stats?.female_count || 0, color: '#eb2f96' },
  ];

  const reservationColumns = [
    {
      title: '고객명',
      dataIndex: 'customer_name',
      key: 'customer_name',
    },
    {
      title: '전화번호',
      dataIndex: 'phone',
      key: 'phone',
    },
    {
      title: '예약 일시',
      key: 'datetime',
      render: (record: any) => `${record.date} ${record.time}`,
    },
    {
      title: '상태',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => {
        const color =
          status === 'confirmed' ? 'green' : status === 'pending' ? 'blue' : 'red';
        return <Tag color={color}>{status}</Tag>;
      },
    },
  ];

  const messageColumns = [
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
      title: '메시지',
      dataIndex: 'message',
      key: 'message',
    },
    {
      title: '시간',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (time: string) => new Date(time).toLocaleString('ko-KR'),
    },
  ];

  return (
    <div>
      <h1>대시보드</h1>

      <Row gutter={16} style={{ marginTop: 24 }}>
        <Col span={6}>
          <Card>
            <Statistic
              title="전체 예약"
              value={stats.totals.reservations}
              prefix={<CalendarOutlined />}
              valueStyle={{ color: '#3f8600' }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="전체 메시지"
              value={stats.totals.messages}
              prefix={<MessageOutlined />}
              valueStyle={{ color: '#1890ff' }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="자동 응답률"
              value={stats.auto_response.auto_response_rate}
              suffix="%"
              prefix={<RiseOutlined />}
              valueStyle={{ color: '#cf1322' }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="캠페인 발송"
              value={stats.campaigns?.total_sent || 0}
              suffix="건"
              prefix={<SendOutlined />}
              valueStyle={{ color: '#722ed1' }}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={16} style={{ marginTop: 24 }}>
        <Col span={8}>
          <Card title="응답 유형 분포">
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={responseTypeData}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={(entry) => `${entry.name}: ${entry.value}`}
                  outerRadius={80}
                  fill="#8884d8"
                  dataKey="value"
                >
                  {responseTypeData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </Card>
        </Col>
        <Col span={8}>
          <Card title="오늘 성비 현황">
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={genderData}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={(entry) => `${entry.name}: ${entry.value}명`}
                  outerRadius={80}
                  fill="#8884d8"
                  dataKey="value"
                >
                  {genderData.map((entry, index) => (
                    <Cell key={`gender-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </Card>
        </Col>
        <Col span={8}>
          <Card title="예약 상태">
            <div style={{ fontSize: 16, lineHeight: 2 }}>
              <div>
                <Tag color="blue">대기중</Tag> {stats.reservations_by_status.pending || 0}건
              </div>
              <div>
                <Tag color="green">확정</Tag> {stats.reservations_by_status.confirmed || 0}건
              </div>
              <div>
                <Tag color="red">취소</Tag> {stats.reservations_by_status.cancelled || 0}건
              </div>
              <div>
                <Tag color="default">완료</Tag> {stats.reservations_by_status.completed || 0}건
              </div>
            </div>
          </Card>
        </Col>
      </Row>

      <Row gutter={16} style={{ marginTop: 24 }}>
        <Col span={12}>
          <Card title="최근 예약 (5개)">
            <Table
              dataSource={stats.recent_reservations}
              columns={reservationColumns}
              pagination={false}
              rowKey="id"
            />
          </Card>
        </Col>
        <Col span={12}>
          <Card title="최근 SMS (5개)">
            <Table
              dataSource={stats.recent_messages}
              columns={messageColumns}
              pagination={false}
              rowKey="id"
            />
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default Dashboard;
